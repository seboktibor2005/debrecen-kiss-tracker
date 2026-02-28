import streamlit as st
import requests
import pdfplumber
import pandas as pd
import re
import io
from datetime import datetime, timedelta

# Set up the webpage tab and layout (Wide layout fits 4 columns better)
st.set_page_config(page_title="KISS Tracker", page_icon="🚆", layout="wide")

st.title("🚆 Debrecen & Karcag KISS Train Tracker")
st.write("Fetching the latest schedule directly from the MÁV website...")

# Helper function to do the time math safely
def adjust_train_time(time_string, add_start_mins=0, sub_end_mins=0):
    try:
        # Split "07:25 - 10:23" into start and end parts
        start_str, end_str = time_string.split("-")
        start_time = datetime.strptime(start_str.strip(), "%H:%M")
        end_time = datetime.strptime(end_str.strip(), "%H:%M")
        
        # Apply the math
        if add_start_mins:
            start_time += timedelta(minutes=add_start_mins)
        if sub_end_mins:
            end_time -= timedelta(minutes=sub_end_mins)
            
        return f"{start_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')}"
    except Exception:
        # If the format is weird, just return the original string
        return time_string

@st.cache_data(ttl=3600)
def get_schedule():
    url = "https://www.mavcsoport.hu/sites/default/files/upload/page/kiss_100_vonal.pdf"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return None, f"MÁV website blocked the request. Status: {response.status_code}"
    except Exception as e:
        return None, f"Connection error: {e}"
        
    pdf_file = io.BytesIO(response.content)
    all_tables = []
    
    try:
        with pdfplumber.open(pdf_file) as pdf:
            for page in pdf.pages:
                table = page.extract_table()
                if table:
                    df = pd.DataFrame(table[1:], columns=table[0])
                    all_tables.append(df)
    except Exception as e:
        return None, f"Error reading PDF: {e}"
            
    if not all_tables:
        return None, "No tables found in the PDF."
        
    df = pd.concat(all_tables, ignore_index=True)
    
    new_headers = {}
    date_columns = []
    for col in df.columns:
        col_str = str(col).strip()
        reversed_str = col_str[::-1]
        if reversed_str[:3] in [f"{i:02d}." for i in range(1, 13)]:
            new_headers[col] = reversed_str
            date_columns.append(reversed_str)
    df.rename(columns=new_headers, inplace=True)

    target_routes = ["Budapest-Nyugati - Debrecen", "Debrecen - Budapest-Nyugati"]
    final_data = []
    current_route = "Unknown"
    
    for index, row in df.iterrows():
        row_text = str(row.iloc[0]).strip()
        if pd.isna(row.iloc[0]) or row_text in ['None', 'nan', '']:
            if len(row) > 1:
                row_text = str(row.iloc[1]).strip()
        if not row_text or row_text in ['None', 'nan']:
            continue
            
        if "-" in row_text and not any(char.isdigit() for char in row_text):
            current_route = row_text
            continue
            
        time_match = re.search(r"(\d{2}:\d{2})\s*[-]?\s*(\d{2}:\d{2})", row_text)
        if time_match and current_route in target_routes:
            time_val = f"{time_match.group(1)} - {time_match.group(2)}"
            
            for date_col in date_columns:
                if date_col in row:
                    cell_val = str(row[date_col]).strip()
                    if cell_val in ['1', '1.0', '1.00', '1,0']:
                        final_data.append({"Date": date_col, "Route": current_route, "Time": time_val})

    clean_df = pd.DataFrame(final_data)
    if not clean_df.empty:
        clean_df = clean_df.sort_values(by=["Date", "Time"])
        return clean_df, "Success"
    return None, "No Debrecen KISS trains found for these dates."

# --- The UI drawing part ---
with st.spinner("Downloading and parsing PDF... this takes a few seconds..."):
    train_data, message = get_schedule()

if train_data is not None:
    st.success(f"Found {len(train_data)} trains!")
    
    # 1. Prepare the Budapest Data
    df_bp_to_deb = train_data[train_data["Route"] == "Budapest-Nyugati - Debrecen"].drop(columns=["Route"]).copy()
    df_deb_to_bp = train_data[train_data["Route"] == "Debrecen - Budapest-Nyugati"].drop(columns=["Route"]).copy()
    
    # 2. Prepare the Karcag Data (using copies of the Budapest data)
    df_karcag_to_deb = df_bp_to_deb.copy()
    df_deb_to_karcag = df_deb_to_bp.copy()
    
    # Karcag -> Debrecen: Add 2 hours 12 mins (132 minutes) to START time
    df_karcag_to_deb["Time"] = df_karcag_to_deb["Time"].apply(lambda t: adjust_train_time(t, add_start_mins=132))
    
    # Debrecen -> Karcag: Subtract 2 hours 11 mins (131 minutes) from END time
    df_deb_to_karcag["Time"] = df_deb_to_karcag["Time"].apply(lambda t: adjust_train_time(t, sub_end_mins=131))

    # 3. Draw the layout with 4 columns
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.subheader("Karcag ➔ Debrecen")
        st.dataframe(df_karcag_to_deb, use_container_width=True, hide_index=True)
        
    with col2:
        st.subheader("Debrecen ➔ Karcag")
        st.dataframe(df_deb_to_karcag, use_container_width=True, hide_index=True)
        
    with col3:
        st.subheader("Budapest ➔ Debrecen")
        st.dataframe(df_bp_to_deb, use_container_width=True, hide_index=True)
        
    with col4:
        st.subheader("Debrecen ➔ Budapest")
        st.dataframe(df_deb_to_bp, use_container_width=True, hide_index=True)

else:
    st.error(message)

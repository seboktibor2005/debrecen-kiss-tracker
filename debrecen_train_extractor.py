import streamlit as st
import requests
import pdfplumber
import pandas as pd
import re
import io

# Set up the webpage tab
st.set_page_config(page_title="KISS Tracker", page_icon="🚆")

# Draw the title on the screen
st.title("🚆 Debrecen KISS Train Tracker")
st.write("Fetching the latest schedule directly from the MÁV website...")

@st.cache_data(ttl=3600) # Caches the data for an hour so it loads fast
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
        clean_df = clean_df.sort_values(by=["Date", "Route", "Time"])
        return clean_df, "Success"
    return None, "No Debrecen KISS trains found for these dates."

# --- The UI drawing part ---
with st.spinner("Downloading and parsing PDF... this takes a few seconds..."):
    train_data, message = get_schedule()

if train_data is not None:
    st.success(f"Found {len(train_data)} trains!")
    # Draw the interactive table
    st.dataframe(train_data, use_container_width=True, hide_index=True)
else:
    st.error(message)

import requests
import pdfplumber
import pandas as pd
import re
import io

# You just put your string link here!
MAV_LINK = "https://www.mavcsoport.hu/sites/default/files/upload/page/kiss_100_vonal.pdf"


def get_debrecen_schedule(pdf_url):
    # The "dirty work" of getting the file into memory is hidden in here
    response = requests.get(pdf_url, headers={'User-Agent': 'Mozilla/5.0'})
    pdf_file = io.BytesIO(response.content)

    # 1. EXTRACT TABLE
    all_tables = []
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            table = page.extract_table()
            if table:
                df = pd.DataFrame(table[1:], columns=table[0])
                all_tables.append(df)

    if not all_tables:
        return "Could not extract tables."

    df = pd.concat(all_tables, ignore_index=True)

    # 2. FIX HEADERS
    new_headers = {}
    date_columns = []
    for col in df.columns:
        col_str = str(col).strip()
        reversed_str = col_str[::-1]
        if reversed_str[:3] in [f"{i:02d}." for i in range(1, 13)]:
            new_headers[col] = reversed_str
            date_columns.append(reversed_str)
    df.rename(columns=new_headers, inplace=True)

    # 3. SCAN FOR DEBRECEN
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
                cell_val = str(row[date_col]).strip()
                if cell_val in ['1', '1.0', '1.00', '1,0']:
                    final_data.append({"Date": date_col, "Route": current_route, "Time": time_val})

    # 4. EXPORT
    clean_df = pd.DataFrame(final_data)
    if not clean_df.empty:
        clean_df = clean_df.sort_values(by=["Date", "Route", "Time"])
        clean_df.to_excel("Daily_Debrecen_KISS.xlsx", index=False)
        return "Success! Excel file created."
    else:
        return "No trains found."


# --- All you have to do to run the program is pass the string! ---
print(get_debrecen_schedule(MAV_LINK))
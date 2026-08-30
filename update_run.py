import requests
import pandas as pd
import os
from app import local_df

API_URL = "https://script.google.com/macros/s/AKfycbxsWKDPtAAex8imwHWMVg4TSV_s-yjCHINEw5PCoxJ4Kdq51sijcAG1InXrL3YMe1oM/exec"
LOCAL_DATA_FILE = "Key.csv"

def fetch_and_update_from_api():
    """Fetch fresh data from Google Apps Script API and update local cache/file."""
    global local_df
    print("Fetching fresh data from API...")
    try:
        response = requests.get(API_URL)
        if response.status_code == 200:
            json_data = response.json()
            if json_data.get('status') == 'success':
                raw_data = json_data.get('data', [])
                
                if len(raw_data) > 1:
                    headers = raw_data[0]
                    rows = raw_data[1:]
                    
                    df = pd.DataFrame(rows, columns=headers)
                    df.columns = df.columns.str.strip()
                    
                    if 'EMAIL' in df.columns and 'DOB' in df.columns:
                        df['EMAIL'] = df['EMAIL'].astype(str).str.strip().str.lower()
                        
                        # Chuyển đổi định dạng ISO date sang DD/MM/YYYY
                        try:
                            parsed_dates = pd.to_datetime(df['DOB'], errors='coerce', utc=True)
                            parsed_dates = parsed_dates.dt.tz_convert('Asia/Ho_Chi_Minh')
                            formatted_dates = parsed_dates.dt.strftime('%d/%m/%Y')
                            df['DOB'] = formatted_dates.fillna(df['DOB'].astype(str).str.strip())
                        except Exception as e:
                            print("Lỗi parse ngày tháng:", e)
                            df['DOB'] = df['DOB'].astype(str).str.strip()
                    
                    # # Cập nhật cache in-memory
                    local_df = df
                    
                    # Lưu lại xuống file local để dùng cho lần khởi động sau
                    try:
                        local_df.to_csv(LOCAL_DATA_FILE, index=False)
                        print("Saved fresh data to local CSV.")
                    except Exception as e:
                        print("Error saving to local file:", e)
                        
                    return True
    except Exception as e:
        print("Error fetching from Google Sheets API:", e)
        
    return False

if __name__ == "__main__":
    fetch_and_update_from_api()
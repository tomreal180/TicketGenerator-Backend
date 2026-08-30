import requests
import pandas as pd
import os
import app

API_URL = "https://script.google.com/macros/s/AKfycbwRXwpc6RBPZG3i4w9v4kO9Vm2YG_PNKdspI1Ybni2f_x3iMsdbUbW3qkGm9giF-gDQ2g/exec"
LOCAL_DATA_FILE = "Key.csv"

def fetch_and_update_from_api():
    """Fetch fresh data from Google Apps Script API and update local cache/file."""
    print("Fetching fresh data from API...")
    try:
        response = requests.post(API_URL,
                                 headers={'Content-Type': 'text/plain;charset=utf-8'},
                                 allow_redirects=True,
                                 json={"action": "getKey"})
        
        if response.status_code == 200:
            json_data = response.json()
            if json_data.get('success'):
                raw_data = json_data.get('data', [])
                print(f"Fetched {len(raw_data)} records from API.")
                
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
                    
                    # Cập nhật cache in-memory do app.py sở hữu.
                    app.local_df = df
                    
                    # Lưu lại xuống file local để dùng cho lần khởi động sau
                    try:
                        app.local_df.to_csv(LOCAL_DATA_FILE, index=False)
                        print("Saved fresh data to local CSV.")
                    except Exception as e:
                        print("Error saving to local file:", e)
                        
                    return True
    except Exception as e:
        print("Error fetching from Google Sheets API:", e)
        
    return False

if __name__ == "__main__":
    fetch_and_update_from_api()
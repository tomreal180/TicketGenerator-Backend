from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import pandas as pd
import requests
import os
from ticket_generator import generate_ticket_in_memory

app = Flask(__name__)
CORS(app)

API_URL = "https://script.google.com/macros/s/AKfycbxsWKDPtAAex8imwHWMVg4TSV_s-yjCHINEw5PCoxJ4Kdq51sijcAG1InXrL3YMe1oM/exec"
LOCAL_DATA_FILE = "Key.csv"

# Global dataframe to hold our local cache
local_df = pd.DataFrame()

def load_local_data():
    """Load data from the local CSV file into memory."""
    global local_df
    if os.path.exists(LOCAL_DATA_FILE):
        try:
            df = pd.read_csv(LOCAL_DATA_FILE)
            df.columns = df.columns.str.strip()
            if 'EMAIL' in df.columns and 'DOB' in df.columns:
                df['EMAIL'] = df['EMAIL'].astype(str).str.strip().str.lower()
                # If DOB from CSV is already DD/MM/YYYY, just strip
                df['DOB'] = df['DOB'].astype(str).str.strip()
            local_df = df
            print(f"Loaded {len(local_df)} records from local cache.")
        except Exception as e:
            print("Error loading local data:", e)

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
                    
                    # Cập nhật cache in-memory
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

# Initialize local data on startup
load_local_data()

@app.route('/api/generate-ticket', methods=['POST'])
def generate_ticket():
    data = request.json
    if not data:
        return jsonify({"error": "No JSON provided"}), 400
        
    email = data.get('email', '').strip().lower()
    dob = data.get('dob', '').strip()
    
    if not email or not dob:
        return jsonify({"error": "Vui lòng nhập Email và Ngày sinh"}), 400
        
    # Bước 1: Tìm trong data local (memory/csv) trước
    match = local_df[(local_df['EMAIL'] == email) & (local_df['DOB'] == dob)]
    
    # Bước 2: Nếu không tìm thấy, gọi API để lấy data mới và tìm lại
    if match.empty:
        success = fetch_and_update_from_api()
        if success:
            match = local_df[(local_df['EMAIL'] == email) & (local_df['DOB'] == dob)]
        else:
            return jsonify({"error": "Không thể kết nối đến máy chủ dữ liệu. Vui lòng thử lại sau."}), 500
            
    # Bước 3: Nếu vẫn không có, trả về lỗi 404
    if match.empty:
        return jsonify({"error": "Email hoặc ngày sinh không có trong hệ thống!"}), 404
        
    user_record = match.iloc[0]
    
    id_val = str(user_record.get('ID', ''))
    name = str(user_record.get('Name', ''))
    key = str(user_record.get('KEY', ''))
    ticket_type = str(user_record.get('TYPE', ''))
    date_val = str(user_record.get('DATE', ''))
    
    try:
        pdf_stream = generate_ticket_in_memory(id_val, name, ticket_type, key, date_val)
        
        safe_name = name.replace(" ", "_")
        filename = f"ticket_SIVICAMP2026_{id_val}_{safe_name}.pdf"
        
        return send_file(
            pdf_stream,
            as_attachment=True,
            download_name=filename,
            mimetype='application/pdf'
        )
    except Exception as e:
        print("Error generating ticket:", e)
        return jsonify({"error": "Có lỗi xảy ra khi tạo vé. Vui lòng thử lại sau."}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import pandas as pd
import os
from ticket_generator import generate_ticket_in_memory

app = Flask(__name__)

# Khởi tạo bộ đếm chống Spam (10 requests / 1 phút)
limiter = Limiter(
    get_remote_address,
    app=app,
    storage_uri="memory://"
)

# Cấu hình bảo mật CORS
if os.environ.get('RENDER'):
    # Môi trường Production (Render): CHỈ cho phép tên miền Vercel của bạn
    CORS(app, origins=["https://ticket-generator-frontend-alpha.vercel.app"])
else:
    # Môi trường Local (Máy tính của bạn): Cho phép tự do để dễ test
    CORS(app)

# Chỉ bật Swagger (Tài liệu API) khi chạy ở Local, tắt trên Render
if not os.environ.get('RENDER'):
    from flasgger import Swagger
    Swagger(app)

# API_URL = "https://script.google.com/macros/s/AKfycbxsWKDPtAAex8imwHWMVg4TSV_s-yjCHINEw5PCoxJ4Kdq51sijcAG1InXrL3YMe1oM/exec"
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
                # If DOB from CSV is already DD/MM/YYYY, just strip, also replace . and - with /
                df['DOB'] = df['DOB'].astype(str).str.strip().str.replace('.', '/').str.replace('-', '/')
            local_df = df
            print(f"Loaded {len(local_df)} records from local cache.")
        except Exception as e:
            print("Error loading local data:", e)


# Initialize local data on startup
load_local_data()

@app.route('/api/generate-ticket', methods=['POST'])
@limiter.limit("10 per minute")
def generate_ticket():
    """
    Tạo vé PDF dựa trên Email và Ngày sinh (DOB).
    ---
    tags:
      - Ticket API
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            email:
              type: string
              example: "quan.lm.tran@gmail.com"
            dob:
              type: string
              example: "21/03/2002"
    responses:
      200:
        description: Trả về file PDF của vé
        content:
          application/pdf:
            schema:
              type: string
              format: binary
      400:
        description: Thiếu Email hoặc Ngày sinh
      404:
        description: Không tìm thấy user trong hệ thống
      500:
        description: Lỗi hệ thống
    """
    data = request.json
    if not data:
        return jsonify({"error": "No JSON provided"}), 400
        
    email = data.get('email', '').strip().lower()
    dob = data.get('dob', '').strip().replace('.', '/').replace('-', '/')
    
    if not email or not dob:
        return jsonify({"error": "Vui lòng nhập Email và Ngày sinh"}), 400
        
    # Bước 1: Tìm trong data local (memory/csv) trước
    match = local_df[(local_df['EMAIL'] == email) & (local_df['DOB'] == dob)]
    
    # # Bước 2: Nếu không tìm thấy, gọi API để lấy data mới và tìm lại
    # if match.empty:
    #     success = fetch_and_update_from_api()
    #     if success:
    #         match = local_df[(local_df['EMAIL'] == email) & (local_df['DOB'] == dob)]
    #     else:
    #         return jsonify({"error": "Không thể kết nối đến máy chủ dữ liệu. Vui lòng thử lại sau."}), 500
            
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

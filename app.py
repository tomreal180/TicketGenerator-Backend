from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import pandas as pd
import os

# Tự động nạp biến môi trường từ file .env (nếu có)
load_dotenv()
import requests
import hmac
import hashlib
from ticket_generator import generate_ticket_in_memory

def generate_ticket_signature(ticket_id: str, secret_key: str) -> str:
    """Tạo chữ ký HMAC-SHA256 giống hệt Google App Script"""
    signature = hmac.new(
        key=secret_key.encode('utf-8'),
        msg=ticket_id.encode('utf-8'),
        digestmod=hashlib.sha256
    )
    return signature.hexdigest()

app = Flask(__name__)

# Khởi tạo Swagger (CHỈ CHẠY Ở LOCAL, KHÔNG CHẠY TRÊN RENDER)
if not os.environ.get('RENDER'):
    try:
        # from dotenv import load_dotenv
        # load_dotenv()
        from flasgger import Swagger
        swagger_config = {
            "headers": [],
            "specs": [
                {
                    "endpoint": 'apispec_1',
                    "route": '/apispec_1.json',
                    "rule_filter": lambda rule: True,
                    "model_filter": lambda tag: True,
                }
            ],
            "static_url_path": "/flasgger_static",
            "swagger_ui": True,
            "specs_route": "/apidocs/"
        }

        swagger_template = {
          "swagger": "2.0",
          "info": {
            "title": "SiviCamp API",
            "description": "API Docs cho tính năng Lấy vé và Điểm danh",
            "version": "1.0.0"
          }
        }
        swagger = Swagger(app, config=swagger_config, template=swagger_template)
    except ImportError:
        pass

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
    ticket_type = str(user_record.get('TYPE', ''))
    date_val = str(user_record.get('DATE', ''))
    
    # Tạo nội dung QR Code: ID|Signature để Google App Script (validateTicket) đọc
    shared_secret = os.environ.get('SHARED_SECRET_KEY', 'MY_SUPER_SECRET_KEY')
    signature = generate_ticket_signature(id_val, shared_secret)
    qr_data = f"{id_val}|{signature}"
    
    try:
        pdf_stream = generate_ticket_in_memory(id_val, name, ticket_type, qr_data, date_val)
        
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

# ==============================================================================
# API Điểm danh (Attendance)
# ==============================================================================

# Lấy từ Google reCAPTCHA Admin (Loại V2)
RECAPTCHA_SECRET_KEY = os.environ.get('RECAPTCHA_SECRET_KEY', '6LeIxAcTAAAAAGG-vFI1TnRWxMZNFuojJ4WifJWe') 
# Thay bằng Link Web App của Google App Script
GAS_ATTENDANCE_API_URL = os.environ.get('GAS_API_URL', '')

# Mật khẩu HMAC dùng chung giữa Flask và GAS
SHARED_SECRET_KEY = os.environ.get('SHARED_SECRET_KEY', 'MY_SUPER_SECRET_KEY')
API_ATTENDANCE_ID = "ATTENDANCE_SIVICAMP_2026"

@app.route('/api/attendance', methods=['POST'])
@limiter.limit("5 per minute")
def attendance():
    """
    Ghi nhận điểm danh / đăng ký tham gia sự kiện.
    Nhận token reCAPTCHA từ Frontend, xác thực với Google.
    Nếu hợp lệ, tạo chữ ký số HMAC-SHA256 và gửi sang Google App Script.
    ---
    tags:
      - Attendance API
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - token
          properties:
            token:
              type: string
              description: Token sinh ra từ Widget reCAPTCHA v2 của người dùng.
              example: "03AFcWeA7X... (chuỗi hash rất dài)"
    responses:
      200:
        description: Đăng ký thành công và đã được GAS ghi nhận.
        schema:
          type: object
          properties:
            message:
              type: string
              example: "Đăng ký xem thuyết trình thành công!"
      400:
        description: Yêu cầu không hợp lệ (thiếu token).
        schema:
          type: object
          properties:
            error:
              type: string
              example: "Thiếu mã xác thực CAPTCHA"
      403:
        description: Xác thực reCAPTCHA thất bại (Token hết hạn hoặc do bot gửi).
        schema:
          type: object
          properties:
            error:
              type: string
              example: "CAPTCHA không hợp lệ hoặc đã hết hạn"
      429:
        description: Bị chặn bởi Rate Limiter (Spam quá nhiều).
      500:
        description: Lỗi máy chủ (Không thể kết nối GAS hoặc lỗi hệ thống).
    """
    data = request.get_json()
    if not data or 'token' not in data:
        return jsonify({"error": "Thiếu mã xác thực CAPTCHA"}), 400
        
    captcha_token = data['token']
    quantity = data.get('quantity', 1)
    
    # Ép kiểu và kiểm tra quantity hợp lệ
    try:
        quantity = int(quantity)
        if quantity < 1:
            quantity = 1
    except:
        quantity = 1
    
    # 1. Gọi sang Google để xác thực Token này có phải người thật không
    try:
        verify_response = requests.post(
            url='https://www.google.com/recaptcha/api/siteverify',
            data={
                'secret': RECAPTCHA_SECRET_KEY,
                'response': captcha_token
            },
            timeout=5
        )
        result = verify_response.json()
        if not result.get('success'):
            return jsonify({"error": "CAPTCHA không hợp lệ hoặc đã hết hạn"}), 403
    except Exception as e:
        print("reCAPTCHA Verify Error:", e)
        return jsonify({"error": "Không thể xác thực CAPTCHA lúc này"}), 500
        
    # 2. Nếu Google báo OK, tiến hành gửi sang Google App Script
    if not GAS_ATTENDANCE_API_URL:
        # Chế độ Test (Mock) nếu chưa có link GAS
        return jsonify({"message": "Ghi nhận thành công (Chế độ Test)"}), 200
        
    try:
        # Tạo chữ ký HMAC để chứng minh Flask là người gửi hợp lệ
        signature = generate_ticket_signature(API_ATTENDANCE_ID, SHARED_SECRET_KEY)
        
        gas_response = requests.post(
            url=GAS_ATTENDANCE_API_URL,
            json={
                "action": "attendance",
                "api_id": API_ATTENDANCE_ID,
                "signature": signature,
                "quantity": quantity
            },
            timeout=10 # Thời gian chờ tối đa 10s
        )
        
        if gas_response.status_code == 200:
            try:
                res_data = gas_response.json()
                if res_data.get("success"):
                    return jsonify({"message": "Đăng ký xem thuyết trình thành công!"}), 200
                else:
                    error_msg = res_data.get("message", "Lỗi bị từ chối từ Google Sheet")
                    print("GAS Error Message:", error_msg)
                    return jsonify({"error": f"Bị từ chối: {error_msg}"}), 400
            except ValueError:
                return jsonify({"error": "Google App Script không trả về định dạng JSON hợp lệ"}), 500
        else:
            return jsonify({"error": f"Lỗi HTTP {gas_response.status_code} từ máy chủ Google"}), 500
            
    except Exception as e:
        print("GAS Error:", e)
        return jsonify({"error": "Lỗi kết nối đến hệ thống máy chủ"}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)

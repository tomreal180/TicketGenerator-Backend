import requests
from PIL import Image, ImageDraw, ImageFont
import io
import os

# --- CONFIGURATION ---
TEMPLATE_PATH = "ticket.png"
FONT_PATH = "HelveticaNeueBold.otf"
MAX_LENGTH = 578

QR_POSITION = (390, 1455)
NAME_POSITION = (376, 972)
DATE_POSITION = (376, 1092)
TYPE_POSITION = (376, 1204)
ID_POSITION = (465, 1815)

QR_SIZE = 300
FONT_SIZE = 40
FONT_SIZE_ID = 26

def get_qr_code(data, size=200):
    logoSivicamp = 'https://i.imgur.com/JELhyv8.png'
    url = f"https://quickchart.io/qr?size={size}&finderStyle=circle&finderColor=2e1b7f&text={data}&centerImageUrl={logoSivicamp}"
    response = requests.get(url)
    if response.status_code == 200:
        return Image.open(io.BytesIO(response.content))
    else:
        print(f"Error generating QR for data: {data}")
        return None

def get_optimal_font(text, font_path, initial_size, max_width):
    current_size = initial_size
    font = ImageFont.truetype(font_path, current_size)
    while font.getlength(text) > max_width:
        current_size -= 1
        if current_size < 10:
            break
        font = ImageFont.truetype(font_path, current_size)
    return font

def generate_ticket_in_memory(id, guest_name, ticket_type, qr_data, date):
    template = Image.open(TEMPLATE_PATH).convert("RGBA")
    
    qr_img = get_qr_code(qr_data, size=QR_SIZE)
    if qr_img:
        template.paste(qr_img, QR_POSITION)
    
    draw = ImageDraw.Draw(template)
    try:
        font_name = get_optimal_font(guest_name, FONT_PATH, FONT_SIZE, MAX_LENGTH)
        font_type = ImageFont.truetype(FONT_PATH, FONT_SIZE)
        font_id = ImageFont.truetype(FONT_PATH, FONT_SIZE_ID)
    except IOError:
        print("Font file not found, using default...")
        font_name = ImageFont.load_default()
        font_type = ImageFont.load_default()
        font_id = ImageFont.load_default()

    draw.text(NAME_POSITION, guest_name, font=font_name, fill="#2e1b7f")
    if ticket_type == "FULL EXPERIENCE PASS + KHÁCH SẠN":
        row1 = "FULL EXPERIENCE PASS"
        row2 = "+ KHÁCH SẠN"
        draw.text(TYPE_POSITION, row1, font=font_type, fill="#2e1b7f")
        draw.text((376, 1258), row2, font=font_type, fill="#2e1b7f")
    else:
        draw.text(TYPE_POSITION, ticket_type, font=font_type, fill="#2e1b7f")
        
    draw.text(DATE_POSITION, date, font=font_type, fill="#2e1b7f")
    draw.text(ID_POSITION, id, font=font_id, fill="#2e1b7f", align="center")

    pdf_stream = io.BytesIO()
    template.convert("RGB").save(pdf_stream, format="PDF")
    pdf_stream.seek(0)
    
    return pdf_stream

import os
import gspread
from flask import Flask, request, abort
from oauth2client.service_account import ServiceAccountCredentials

from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi, 
    ReplyMessageRequest, TextMessage
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent
import json

app = Flask(__name__)

# 1. ตั้งค่า LINE API (ดึงค่าจากที่ตั้งไว้ใน Render)
# ต้องตั้งชื่อ NAME ใน Render ให้ตรงกับ os.getenv นะครับ
line_access_token = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
line_channel_secret = os.getenv('LINE_CHANNEL_SECRET')

configuration = Configuration(access_token=line_access_token)
handler = WebhookHandler(line_channel_secret)

# 2. ตั้งค่า Google Sheets
def get_sheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    # ไฟล์ google_key.json ต้องอัปโหลดขึ้น GitHub ไว้ที่โฟลเดอร์หลัก
    google_key_json = os.getenv('GOOGLE_JSON_KEY')
    key_dict = json.loads(google_key_json)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(key_dict, scope)
    client = gspread.authorize(creds)
    # เปลี่ยนชื่อ "Laundry_DB" ให้ตรงกับชื่อไฟล์ Google Sheets ของคุณเป๊ะๆ
    return client.open("laundry-bot").sheet1

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature')
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_id = event.source.user_id # ดึง ID ของลูกค้าที่ทักมา
    user_text = event.message.text.strip() # ดึงข้อความที่ลูกค้าพิมพ์
    
    sheet = get_sheet()
    reply_text = ""

    try:
        # ค้นหา User ID ในคอลัมน์ A (index 1)
        cell = sheet.find(user_id)
        row_data = sheet.row_values(cell.row)
        
        # สมมติลำดับคอลัมน์: A=ID, B=ชื่อเล่น, C=ชื่อจริง, D=สถานะ, E=ราคา
        name = row_data[2] if len(row_data) > 2 else "ลูกค้า"
        status = row_data[3] if len(row_data) > 3 else "ไม่มีข้อมูล"
        price = row_data[4] if len(row_data) > 4 else "0"
        
        if "สถานะ" in user_text:
            reply_text = f"สวัสดีครับคุณ {name} ✨\nขณะนี้ผ้าของคุณ: {status}"
        elif "ยอด" in user_text or "บิล" in user_text or "ราคา" in user_text:
            reply_text = f"คุณ {name} มียอดชำระทั้งหมด {price} บาทครับ 💰"
        else:
            reply_text = f"สวัสดีครับคุณ {name} มีอะไรให้ช่วยไหมครับ?\n- พิมพ์ 'สถานะ' เพื่อเช็คผ้า\n- พิมพ์ 'บิล' เพื่อดูราคา"
            
    except gspread.exceptions.CellNotFound:
        # กรณีไม่พบ User ID ในตาราง จะส่ง ID ให้ลูกค้าเพื่อเอาไปลงทะเบียน
        reply_text = f"ขออภัยครับ ไม่พบข้อมูลสมาชิกของคุณ\nID ของคุณคือ: {user_id}\nกรุณาแจ้งเจ้าหน้าที่เพื่อลงทะเบียนครับ"

    # ส่งข้อความกลับไปหาลูกค้า
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply_text)]
            )
        )

if __name__ == "__main__":
    app.run(port=int(os.environ.get("PORT", 5000)))



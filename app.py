import os
import json
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

app = Flask(__name__)

# 1. ตั้งค่า LINE API (ดึงค่าจาก Environment Variables ใน Render)
line_access_token = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
line_channel_secret = os.getenv('LINE_CHANNEL_SECRET')

# ป้องกัน Error ถ้าลืมใส่ค่าใน Render
configuration = Configuration(access_token=line_access_token)
handler = WebhookHandler(line_channel_secret)

# 2. ตั้งค่า Google Sheets
def get_sheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    # อ่านไฟล์ JSON ตรงๆ จากโฟลเดอร์หลัก
    creds = ServiceAccountCredentials.from_json_keyfile_name("google_key.json", scope)
    client = gspread.authorize(creds)
    return client.open("laundry-bot").sheet1

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature')
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    except Exception as e:
        print(f"Error in callback: {e}")
        abort(500)
    return 'OK'

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_id = event.source.user_id
    user_text = event.message.text.strip()
    
    try:
        sheet = get_sheet()
        cell = sheet.find(user_id)
        row_data = sheet.row_values(cell.row)
        
        # คอลัมน์: A=ID, B=Nick, C=Name, D=Status, E=Price
        name = row_data[2] if len(row_data) > 2 else "ลูกค้า"
        status = row_data[3] if len(row_data) > 3 else "กำลังดำเนินการ"
        price = row_data[4] if len(row_data) > 4 else "0"
        
        if "สถานะ" in user_text:
            reply_text = f"สวัสดีครับคุณ {name} ✨\nขณะนี้ผ้าของคุณ: {status}"
        elif any(word in user_text for word in ["ยอด", "บิล", "ราคา"]):
            reply_text = f"คุณ {name} มียอดชำระทั้งหมด {price} บาทครับ 💰"
        else:
            reply_text = f"สวัสดีครับคุณ {name}\n- พิมพ์ 'สถานะ' เพื่อเช็คผ้า\n- พิมพ์ 'บิล' เพื่อดูราคา"
            
    except gspread.exceptions.CellNotFound:
        # หากไม่เจอ ID ให้บอทส่ง ID จริงมาให้เราก๊อปปี้
        reply_text = f"ไม่พบข้อมูลสมาชิก\nID ของคุณคือ:\n{user_id}\n(ก๊อปปี้รหัสนี้ไปใส่ในช่อง A2 ของ Sheet ครับ)"
    except Exception as e:
        reply_text = "ขออภัย ระบบขัดข้องชั่วคราวครับ"
        print(f"Error: {e}")

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

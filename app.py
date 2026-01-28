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

# 1. ตั้งค่า LINE API
line_access_token = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
line_channel_secret = os.getenv('LINE_CHANNEL_SECRET')

configuration = Configuration(access_token=line_access_token)
handler = WebhookHandler(line_channel_secret)

# 2. ฟังก์ชันต่อ Sheets
def get_sheet():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name("google_key.json", scope)
        client = gspread.authorize(creds)
        return client.open("laundry-bot").sheet1
    except Exception as e:
        return f"ERROR_JSON_OR_AUTH: {str(e)}"

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
    return 'OK'

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_id = event.source.user_id
    user_text = event.message.text.strip()
    reply_text = ""

    # ดึงข้อมูลจาก Sheet
    result = get_sheet()
    
    if isinstance(result, str) and "ERROR" in result:
        reply_text = f"❌ เชื่อมต่อ Google ไม่ได้:\n{result}"
    else:
        try:
            sheet = result
            # แก้ไขจุดที่ทำให้พัง: ใช้ gspread.CellNotFound ตรงๆ หรือครอบ Exception ทั่วไป
            try:
                cell = sheet.find(user_id)
                row_data = sheet.row_values(cell.row)
                
                name = row_data[2] if len(row_data) > 2 else "ลูกค้า"
                status = row_data[3] if len(row_data) > 3 else "ไม่มีข้อมูล"
                price = row_data[4] if len(row_data) > 4 else "0"
                
                if "สถานะ" in user_text:
                    reply_text = f"สวัสดีครับคุณ {name} ✨\nขณะนี้ผ้าของคุณ: {status}"
                else:
                    reply_text = f"สวัสดีครับคุณ {name}\nต้องการเช็ค 'สถานะ' หรือ 'บิล' ครับ?"
            
            except gspread.CellNotFound: # ปรับแก้ตรงนี้ให้ถูกต้องตามเวอร์ชันใหม่
                reply_text = f"🔍 ไม่พบข้อมูล ID นี้ในระบบครับ\nID ของคุณคือ:\n{user_id}"
                
        except Exception as e:
            reply_text = f"⚠️ เกิดข้อผิดพลาดอื่น ๆ:\n{str(e)}"

    # ส่งข้อความกลับ
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

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

# 1. ตั้งค่า LINE API (ดึงจาก Render Environment)
line_access_token = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
line_channel_secret = os.getenv('LINE_CHANNEL_SECRET')

configuration = Configuration(access_token=line_access_token)
handler = WebhookHandler(line_channel_secret)

# 2. ฟังก์ชันเชื่อมต่อ Google Sheets แบบไร้ไฟล์ (ใช้ Environment Variable)
def get_sheet():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        
        # ดึงค่า JSON จาก Render
        json_string = os.getenv("GOOGLE_JSON_KEY")
        if not json_string:
            return "ERROR: ไม่พบ GOOGLE_JSON_KEY ในหน้า Environment ของ Render"

        # แปลงเป็น Dictionary และจัดการรหัสลับให้ถูกต้อง
        info = json.loads(json_string)
        if 'private_key' in info:
            info['private_key'] = info['private_key'].replace('\\n', '\n')
            
        creds = ServiceAccountCredentials.from_json_keyfile_dict(info, scope)
        client = gspread.authorize(creds)
        
        # ตรวจสอบว่าชื่อไฟล์ Google Sheets ตรงกับ "laundry-bot"
        return client.open("laundry-bot").sheet1
    except Exception as e:
        return f"ERROR_AUTH: {str(e)}"

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature')
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    except Exception as e:
        print(f"Callback Error: {e}")
    return 'OK'

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_id = event.source.user_id
    user_text = event.message.text.strip()
    reply_text = ""

    result = get_sheet()
    
    if isinstance(result, str) and "ERROR" in result:
        reply_text = f"❌ ระบบขัดข้อง:\n{result}"
    else:
        try:
            sheet = result
            # ใช้ try ครอบการหาค่า เพื่อดักจับกรณีไม่พบข้อมูล
            try:
                cell = sheet.find(user_id)
                row_data = sheet.row_values(cell.row)
                
                name = row_data[2] if len(row_data) > 2 else "ลูกค้า"
                status = row_data[3] if len(row_data) > 3 else "กำลังดำเนินการ"
                price = row_data[4] if len(row_data) > 4 else "0"
                
                if "สถานะ" in user_text:
                    reply_text = f"สวัสดีครับคุณ {name} ✨\nขณะนี้ผ้าของคุณ: {status}"
                elif any(word in user_text for word in ["ยอด", "บิล", "ราคา"]):
                    reply_text = f"คุณ {name} มียอดชำระทั้งหมด {price} บาทครับ 💰"
                else:
                    reply_text = f"สวัสดีครับคุณ {name}\nต้องการเช็ค 'สถานะ' หรือ 'บิล' ครับ?"
            
            except Exception:
                # ถ้าหาไม่เจอ หรือเกิด error ในการค้นหา ให้ส่ง ID ไปให้ลงทะเบียน
                reply_text = f"🔍 ไม่พบข้อมูลสมาชิกในระบบ\nID ของคุณคือ:\n{user_id}\n(ก๊อปปี้ ID นี้ไปวางในช่อง A2 ของ Google Sheets นะครับ)"
        
        except Exception as e:
            reply_text = f"⚠️ ระบบขัดข้องกะทันหัน:\n{str(e)}"

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


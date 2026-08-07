import os
import requests
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import google.generativeai as genai

# 1. Lấy dữ liệu Commit hôm nay từ GitHub
def get_github_commits():
    username = os.getenv('GH_USERNAME', 'ThanhNhat1908')
    url = f"https://api.github.com/users/{username}/events"
    try:
        res = requests.get(url, timeout=10).json()
        commits = []
        if isinstance(res, list):
            for event in res:
                if event.get('type') == 'PushEvent':
                    for c in event.get('payload', {}).get('commits', []):
                        commits.append(c.get('message', ''))
        return "\n".join(commits) if commits else "Không có commit mới."
    except Exception as e:
        print(f"Lỗi lấy GitHub commits: {e}")
        return "Không có commit mới."

# 2. Lấy note từ Telegram Bot
def get_telegram_note():
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not token:
        return "Không có note bổ sung."
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    try:
        res = requests.get(url, timeout=10).json()
        results = res.get('result', [])
        if results:
            return results[-1]['message'].get('text', '')
    except Exception as e:
        print(f"Lỗi lấy note Telegram: {e}")
    return "Không có note bổ sung."

# 3. Dùng Gemini API sinh nội dung báo cáo chuẩn HTML
def generate_email_body(commits, tg_note):
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        print("Cảnh báo: GEMINI_API_KEY chưa được thiết lập.")
        return f"<p>Gửi anh Anthony,<br><br>Em xin gửi báo cáo tiến độ:<br>Commits: {commits}<br>Note: {tg_note}</p>"

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    prompt = f"""
    Bạn là trợ lý viết email báo cáo công việc hàng ngày cho Nguyễn Thành Nhật gửi cho anh Anthony (anthony@technext.asia).
    Tên dự án: SmartShop Odoo 19 AI Gateway
    
    Dữ liệu công việc thu thập hôm nay:
    - Commits trên GitHub: {commits}
    - Ghi chú từ Telegram (Antigravity/Gemini/Odoo): {tg_note}
    
    Hãy viết nội dung Email bằng TIẾNG VIỆT, sử dụng định dạng HTML (thẻ <p>, <ul>, <li>, <strong>) chính xác theo mẫu sau:

    Gửi anh Anthony,<br><br>
    Em xin gửi anh báo cáo tiến độ công việc của dự án SmartShop Odoo 19 AI Gateway.<br><br>
    <strong>Công việc đã hoàn thành</strong>
    <ul>
      <!-- Liệt kê 3-4 ý chính từ dữ liệu thu thập, diễn đạt chuyên nghiệp -->
    </ul>
    <strong>Công việc đang triển khai</strong>
    <ul>
      <!-- Liệt kê 2-3 ý công việc tiếp theo hoặc đang làm -->
    </ul>
    Em sẽ tiếp tục cập nhật tiến độ khi hoàn thành các hạng mục còn lại.<br><br>
    Em cảm ơn anh đã dành thời gian xem báo cáo và rất mong nhận được góp ý từ anh.<br><br>
    Trân trọng,<br>
    Nguyễn Thành Nhật
    
    LƯU Ý: Chỉ trả về nội dung HTML, không kèm các câu dẫn hay ký tự markdown ```html.
    """
    response = model.generate_content(prompt)
    return response.text.replace("```html", "").replace("```", "").strip()

# 4. Gửi Email HTML qua Gmail SMTP
def send_email(html_content):
    today = datetime.now().strftime("%d/%m/%Y")
    sender_email = os.getenv('EMAIL_USER')
    receiver_email = 'anthony@technext.asia'
    
    if not sender_email or not os.getenv('EMAIL_PASS'):
        print("Cảnh báo: EMAIL_USER hoặc EMAIL_PASS chưa được thiết lập. Bỏ qua bước gửi mail.")
        return

    msg = MIMEMultipart('alternative')
    msg['Subject'] = f"Daily Report - {today} - Nguyễn Thành Nhật"
    msg['From'] = f"Nhật Nguyễn Thành <{sender_email}>"
    msg['To'] = receiver_email

    part = MIMEText(html_content, 'html', 'utf-8')
    msg.attach(part)

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(sender_email, os.getenv('EMAIL_PASS'))
        server.send_message(msg)
    print("Báo cáo đã gửi thành công!")

if __name__ == "__main__":
    commits = get_github_commits()
    tg_note = get_telegram_note()
    html_body = generate_email_body(commits, tg_note)
    send_email(html_body)

import os
import json
import requests
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import google.generativeai as genai

# Nạp .env nếu chạy ở môi trường local
if os.path.exists(".env"):
    for line in open(".env", encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip()
            if k not in os.environ:
                os.environ[k] = v

def log_msg(msg: str):
    try:
        print(msg)
    except Exception:
        print(msg.encode("ascii", "replace").decode("ascii"))

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
        log_msg(f"Lỗi lấy note Telegram: {e}")
    return "Không có note bổ sung."

# 3. Dùng Gemini API sinh nội dung báo cáo chuẩn HTML
def generate_email_body(commits, tg_note):
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        log_msg("Cảnh báo: GEMINI_API_KEY chưa được thiết lập.")
        return f"<p>Gửi anh Anthony,<br><br>Em xin gửi báo cáo tiến độ:<br>Commits: {commits}<br>Note: {tg_note}</p>"

    genai.configure(api_key=api_key)
    
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
      <li>Cập nhật cơ chế Approval Gate chặn các đơn hàng giá trị > 20 triệu VNĐ trên Odoo AI Gateway v3.5.</li>
      <li>Tích hợp Hermes Agent Engine ngầm cho người dùng Telegram Non-Tech.</li>
      <li>Tối ưuPrompt Caching giúp giảm 95% chi phí API Anthropic (chỉ còn ~$0.0016/câu).</li>
    </ul>
    <strong>Công việc đang triển khai</strong>
    <ul>
      <li>Hoàn thiện hệ thống tự động hóa Daily Report qua GitHub Actions và Gmail SMTP.</li>
      <li>Tối ưu hóa các kịch bản tra cứu tồn kho và báo cáo doanh số cho Odoo 19 SaaS.</li>
    </ul>
    Em sẽ tiếp tục cập nhật tiến độ khi hoàn thành các hạng mục còn lại.<br><br>
    Em cảm ơn anh đã dành thời gian xem báo cáo và rất mong nhận được góp ý từ anh.<br><br>
    Trân trọng,<br>
    Nguyễn Thành Nhật
    
    LƯU Ý: Chỉ trả về nội dung HTML, không kèm các câu dẫn hay ký tự markdown ```html.
    """
    
    model_names = ['gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-2.0-flash']
    html_text = ""
    for m in model_names:
        try:
            model = genai.GenerativeModel(m)
            response = model.generate_content(prompt)
            if response and response.text:
                html_text = response.text.replace("```html", "").replace("```", "").strip()
                log_msg(f"✅ Đã tạo nội dung báo cáo thành công từ model: {m}")
                break
        except Exception as ex:
            log_msg(f"⚠️ Thử model {m} chưa thành công: {ex}")

    if not html_text:
        log_msg("Sử dụng nội dung báo cáo HTML dự phòng.")
        html_text = f"""Gửi anh Anthony,<br><br>
Em xin gửi anh báo cáo tiến độ công việc của dự án SmartShop Odoo 19 AI Gateway.<br><br>
<strong>Công việc đã hoàn thành</strong>
<ul>
  <li>Cập nhật cơ chế Approval Gate chặn các đơn hàng giá trị > 20 triệu VNĐ trên Odoo AI Gateway v3.5.</li>
  <li>Tích hợp Hermes Agent Engine ngầm cho người dùng Telegram Non-Tech.</li>
  <li>Tối ưu Prompt Caching giúp giảm 95% chi phí API Anthropic.</li>
</ul>
<strong>Công việc đang triển khai</strong>
<ul>
  <li>Tự động hóa Daily Report qua GitHub Actions và Gmail SMTP.</li>
  <li>Tối ưu hóa các kịch bản tra cứu tồn kho cho Odoo 19 SaaS.</li>
</ul>
Em sẽ tiếp tục cập nhật tiến độ khi hoàn thành các hạng mục còn lại.<br><br>
Em cảm ơn anh đã dành thời gian xem báo cáo và rất mong nhận được góp ý từ anh.<br><br>
Trân trọng,<br>
Nguyễn Thành Nhật"""

    return html_text

# 4. Gửi Email HTML qua Gmail SMTP (Có hỗ trợ đính kèm File)
def send_email(html_content, attachment_paths=None):
    from email.mime.application import MIMEApplication
    today = datetime.now().strftime("%d/%m/%Y")
    sender_email = os.getenv('EMAIL_USER') or 'nguyenthanhnhat19824@gmail.com'
    receiver_email = 'anthony@technext.asia'
    
    if not os.getenv('EMAIL_PASS'):
        log_msg("Cảnh báo: EMAIL_PASS chưa được thiết lập. Bỏ qua bước gửi mail.")
        return False

    msg = MIMEMultipart()
    msg['Subject'] = f"Daily Report - {today} - Nguyễn Thành Nhật"
    msg['From'] = f"Nhật Nguyễn Thành <{sender_email}>"
    msg['To'] = receiver_email

    part = MIMEText(html_content, 'html', 'utf-8')
    msg.attach(part)

    # Đính kèm danh sách file nếu có
    if attachment_paths:
        for path in attachment_paths:
            if os.path.exists(path):
                try:
                    with open(path, "rb") as f:
                        fname = os.path.basename(path)
                        attachment = MIMEApplication(f.read(), Name=fname)
                        attachment['Content-Disposition'] = f'attachment; filename="{fname}"'
                        msg.attach(attachment)
                        log_msg(f"📎 Đã đính kèm file: {fname}")
                except Exception as ex:
                    log_msg(f"Lỗi đính kèm file {path}: {ex}")

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(sender_email, os.getenv('EMAIL_PASS'))
        server.send_message(msg)
    log_msg("✅ Báo cáo đã gửi thành công!")
    return True


# 5. Gửi bản xem trước (Preview) sang Telegram Manager
def send_telegram_preview(html_content):
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    mgr_id = os.getenv('ADMIN_CHAT_ID') or '6553206564'
    if not token:
        log_msg("Cảnh báo: Không tìm thấy TELEGRAM_BOT_TOKEN.")
        return False

    import sys
    ts = int(datetime.now().timestamp())

    # Lưu pending report
    pending_file = "scratch/pending_report.json"
    os.makedirs("scratch", exist_ok=True)
    report_data = {
        "ts": ts,
        "html_content": html_content,
        "attachments": [],
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    with open(pending_file, "w", encoding="utf-8") as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2)

    # Tạo tin nhắn preview gọn
    preview_msg = f"""📋 **XEM TRƯỚC BÁO CÁO DAILY REPORT ({datetime.now().strftime('%d/%m/%Y')})**

Anh Anthony thân mến, dưới đây là bản thảo báo cáo tiến độ hôm nay:

---
{html_content[:350]}...
---

👉 **Vui lòng chọn hành động bên dưới:**"""

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "📩 GỬI MAIL NGAY", "callback_data": f"rpt_send_{ts}"},
                {"text": "📎 ĐÍNH KÈM FILE", "callback_data": f"rpt_att_{ts}"}
            ],
            [
                {"text": "❌ HỦY BÁO CÁO HÔM NAY", "callback_data": f"rpt_can_{ts}"}
            ]
        ]
    }

    try:
        res = requests.post(url, json={"chat_id": mgr_id, "text": preview_msg, "parse_mode": "Markdown", "reply_markup": keyboard}, timeout=10)
        log_msg("📩 Đã gửi bản xem trước báo cáo tới Telegram Manager!")
        return res.ok
    except Exception as e:
        log_msg(f"Lỗi gửi Telegram Preview: {e}")
        return False


if __name__ == "__main__":
    import sys
    commits = get_github_commits()
    tg_note = get_telegram_note()
    html_body = generate_email_body(commits, tg_note)
    
    if "--preview" in sys.argv:
        send_telegram_preview(html_body)
    else:
        send_email(html_body)

"""Kiểm tra cấu hình trước khi test luồng thực tế trên Telegram."""

import os
import sys

# Load .env giống app.py
if os.path.exists(".env"):
    for line in open(".env", encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ[k.strip()] = v.strip()

REQUIRED = {
    "ODOO_URL": "URL Odoo SaaS",
    "ODOO_DB": "Database Odoo",
    "ODOO_USERNAME": "Email đăng nhập Odoo",
    "ODOO_PASSWORD": "Mật khẩu Odoo",
    "ANTHROPIC_API_KEY": "API key Claude AI",
    "TELEGRAM_BOT_TOKEN": "Token Telegram Bot",
    "TELEGRAM_CHAT_ID": "Chat ID Admin (người duyệt)",
}

APPROVAL_REQUIRED = {
    "N8N_APPROVAL_WEBHOOK_URL": "Webhook n8n nhận approval request",
    "N8N_APPROVAL_WEBHOOK_SECRET": "Secret để xác thực webhook callback (HMAC)",
    "N8N_OTP_WEBHOOK_URL": "Webhook n8n gửi OTP email",
}

OPTIONAL = {
    "ADMIN_CHAT_ID": "Chat ID Manager duyệt đơn (mặc định dùng TELEGRAM_CHAT_ID)",
    "CLAUDE_MODEL": "Model Claude (mặc định claude-haiku-4-5)",
}


def check(name, desc, required=True):
    val = os.getenv(name, "")
    if val:
        masked = val[:8] + "..." + val[-4:] if len(val) > 12 else "***"
        print(f"  ✅ {name} = {masked}")
        return True
    else:
        status = "❌ THIẾU" if required else "⚠️ TÙY CHỌN"
        print(f"  {status} {name} — {desc}")
        return not required


def main():
    print("=" * 60)
    print("  KIỂM TRA CẤU HÌNH TRƯỚC KHI TEST TELEGRAM LIVE")
    print("=" * 60)

    print("\n📌 1. CẤU HÌNH CƠ BẢN (bắt buộc):")
    all_ok = True
    for k, desc in REQUIRED.items():
        ok = check(k, desc)
        all_ok = all_ok and ok

    print("\n📌 2. CẤU HÌNH WORKFLOW APPROVE (bắt buộc):")
    for k, desc in APPROVAL_REQUIRED.items():
        ok = check(k, desc)
        all_ok = all_ok and ok

    print("\n📌 3. CẤU HÌNH TÙY CHỌN:")
    for k, desc in OPTIONAL.items():
        check(k, desc, required=False)

    # Kiểm tra ADMIN_CHAT_ID fallback
    admin = os.getenv("ADMIN_CHAT_ID", "")
    if not admin:
        admin = os.getenv("TELEGRAM_CHAT_ID", "")
        if admin:
            print(f"\n  ℹ️ ADMIN_CHAT_ID không set — sẽ dùng TELEGRAM_CHAT_ID = {admin}")

    print("\n" + "=" * 60)
    if all_ok:
        print("  ✅ CẤU HÌNH ĐẦY ĐỦ — SẴN SÀNG TEST TELEGRAM LIVE!")
    else:
        print("  ❌ THIẾU CẤU HÌNH — CẦN BỔ SUNG TRƯỚC KHI TEST!")
        print("\n  Cách sửa: Thêm vào file .env:")
        print("  N8N_APPROVAL_WEBHOOK_SECRET=<secret_của_bạn>")
        print("  ADMIN_CHAT_ID=6553206564")
    print("=" * 60)


if __name__ == "__main__":
    main()
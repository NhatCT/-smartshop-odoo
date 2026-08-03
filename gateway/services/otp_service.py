import time
import random
from gateway.services.notification_service import NotificationService
from gateway.repositories.user_repository import UserRepository
from gateway.repositories.binding_repository import get_bindings, save_bindings

PENDING_OTP_STORE = {}

class OTPService:
    def __init__(self):
        self.notification_service = NotificationService()
        self.user_repo = UserRepository()

    def request_otp(self, telegram_id, email):
        email = email.lower().strip()
        user_info = self.user_repo.get_odoo_user_info(email)
        if not user_info:
            return False, f"❌ Email '{email}' không tồn tại trong hệ thống Odoo 19 SaaS SmartShop!\nVui lòng liên hệ Admin để được tạo tài khoản Odoo."
        
        if not user_info["is_active_odoo"]:
            return False, f"🚨 Tài khoản Odoo '{email}' đã bị VÔ HIỆU HÓA bởi Admin trên Odoo 19!\nMọi truy cập bị từ chối theo chính sách Zero-Trust."

        otp_code = f"{random.randint(100000, 999999)}"
        PENDING_OTP_STORE[str(telegram_id)] = {
            "email": email,
            "otp": otp_code,
            "timestamp": time.time()
        }

        sent = self.notification_service.send_otp_via_n8n(email, otp_code, user_info["full_name"] if user_info else email)
        if sent:
            print(f"\n✅ [OTP EMAIL SENT via n8n]: Telegram ID [{telegram_id}] | Email: {email}")
            return True, (
                f"✉️ **Mã xác thực OTP đã được gửi tới Email:** `{email}`\n\n"
                f"Vui lòng kiểm tra hộp thư của bạn và nhập lệnh xác thực:\n"
                f"`/verify <MÃ_OTP_6_SỐ>`"
            )
        else:
            print(f"\n⚠️ [N8N EMAIL FAILED] - OTP cho {email}: >>> {otp_code} <<<")
            return True, (
                f"🔑 OTP da duoc tao nhung email chua gui duoc (n8n chua kich hoat).\n"
                f"Vui long lien he Admin de lay ma OTP."
            )

    def verify_otp_and_bind(self, telegram_id, user_otp):
        str_id = str(telegram_id)
        user_otp_str = user_otp.strip()

        if "@" in user_otp_str:
            return False, (
                f"⚠️ **CÚ PHÁP CHƯA ĐÚNG!**\n\n"
                f"Để đăng ký email `{user_otp_str}`, bạn hãy gõ lệnh:\n"
                f"`/register {user_otp_str}`\n\n"
                f"Sau khi nhận được **Mã OTP 6 số** qua hòm thư Email, bạn gõ tiếp:\n"
                f"`/verify <MÃ_OTP_6_SỐ>` (ví dụ: `/verify 714959`)."
            )

        pending = PENDING_OTP_STORE.get(str_id)
        if not pending:
            return False, "❌ Không tìm thấy yêu cầu OTP. Vui lòng gõ `/register email@smartshop.com` trước!"
        if pending["otp"] != user_otp_str:
            return False, "❌ Mã OTP không khớp. Vui lòng kiểm tra lại!"

        email = pending["email"]
        bindings = get_bindings()
        bindings[str_id] = email
        save_bindings(bindings)
        del PENDING_OTP_STORE[str_id]

        user_info = self.user_repo.get_odoo_user_info(email)
        role = user_info["role"] if user_info else "viewer"

        return True, (
            f"✅ **XÁC THỰC THÀNH CÔNG!**\n\n"
            f"Tài khoản Odoo: `{email}`\n"
            f"Phân quyền: **{role.upper()}**\n\n"
            f"Bây giờ bạn đã có thể bắt đầu chat với tôi để tra cứu thông tin!"
        )

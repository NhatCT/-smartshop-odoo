import time
import random
from gateway.services.notification_service import NotificationService
from gateway.config.constants import (
    PREDEFINED_EMAIL_NAMES,
    PREDEFINED_EMAIL_ROLES,
    REQUIRES_ADMIN_APPROVAL_EMAILS,
)
from gateway.services.binding_service import get_bindings, save_bindings

PENDING_OTP_STORE = {}
PENDING_APPROVAL_STORE = {}

class OTPService:
    def __init__(self):
        self.notification_service = NotificationService()

    def request_otp(self, telegram_id, email):
        email = email.lower().strip()
        from data_layer.connectors.odoo_rpc import OdooClient
        client = OdooClient()
        try:
            records = client.search_read(
                model="res.users",
                domain=[["login", "=", email], ["active", "in", [True, False]]],
                fields=["id", "name", "login", "active"],
                limit=1
            )
        except Exception:
            records = []

        if not records:
            return False, f"❌ Email '{email}' không tồn tại trong hệ thống Odoo 19 SaaS SmartShop!\nVui lòng liên hệ Admin để được tạo tài khoản Odoo."

        user = records[0]
        if not user.get("active", True):
            return False, f"🚨 Tài khoản Odoo '{email}' đã bị VÔ HIỆU HÓA bởi Admin trên Odoo 19!\nMọi truy cập bị từ chối theo chính sách Zero-Trust."

        employee_name = user.get("name", email)

        otp_code = f"{random.randint(100000, 999999)}"
        PENDING_OTP_STORE[str(telegram_id)] = {
            "email": email,
            "otp": otp_code,
            "timestamp": time.time()
        }

        sent = self.notification_service.send_otp_via_n8n(email, otp_code, employee_name)
        if sent:
            print(f"\n✅ [OTP EMAIL SENT via n8n]: Telegram ID [{telegram_id}] | Email: {email}")
            return True, (
                f"✉️ **Mã xác thực OTP đã được gửi tới Email:** `{email}`\n\n"
                f"Vui lòng kiểm tra hộp thư của bạn và nhập lệnh xác thực:\n"
                f"`/verify <MÃ_OTP_6_SỐ>`"
            )
        else:
            print(f"[N8N EMAIL FAILED] OTP delivery failed for {email}")
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
        if str_id in PENDING_OTP_STORE:
            del PENDING_OTP_STORE[str_id]

        from gateway.services.permission_service import PermissionService
        perm_svc = PermissionService()
        user_info = perm_svc.process_incoming_request(telegram_id)
        role = user_info.get("official_role", "viewer") if isinstance(user_info, dict) else "viewer"

        return True, (
            f"✅ **XÁC THỰC THÀNH CÔNG!**\n\n"
            f"Tài khoản Odoo: `{email}`\n"
            f"Phân quyền: **{role.upper()}**\n\n"
            f"Bây giờ bạn đã có thể bắt đầu chat với tôi để tra cứu thông tin!"
        )

    def approve_pending_registration(self, telegram_id, approver_name="admin"):
        str_id = str(telegram_id)
        pending = PENDING_APPROVAL_STORE.get(str_id)
        if not pending:
            return False, "❌ Không có yêu cầu chờ duyệt nào cho tài khoản này."

        email = pending["email"]
        bindings = get_bindings()
        bindings[str_id] = email
        save_bindings(bindings)
        del PENDING_APPROVAL_STORE[str_id]

        return True, (
            f"✅ Tài khoản `{email}` đã được **{approver_name.upper()}** phê duyệt và kích hoạt."
        )

    def reject_pending_registration(self, telegram_id, approver_name="admin"):
        str_id = str(telegram_id)
        pending = PENDING_APPROVAL_STORE.get(str_id)
        if not pending:
            return False, "❌ Không có yêu cầu chờ duyệt nào cho tài khoản này."

        email = pending["email"]
        del PENDING_APPROVAL_STORE[str_id]
        return True, (
            f"❌ Tài khoản `{email}` đã bị **{approver_name.upper()}** từ chối."
        )

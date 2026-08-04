import time
import random
from gateway.services.notification_service import NotificationService
from gateway.services.binding_service import get_bindings, save_bindings

PENDING_OTP_STORE = {}
PENDING_APPROVAL_STORE = {}
OTP_TTL_SECONDS = 300  # OTP có hiệu lực trong 5 phút

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
                domain=["|", ["login", "=ilike", email], ["email", "=ilike", email]],
                fields=["id", "name", "login", "active"],
                limit=1
            )
        except Exception as e:
            print(f"[OTPService] Error searching res.users: {e}")
            records = []

        if not records:
            return False, f"❌ Email '{email}' không tồn tại trong hệ thống Odoo 19 SaaS SmartShop!\nVui lòng liên hệ Admin để được tạo tài khoản Odoo."

        user = records[0]
        if not user.get("active", True):
            return False, f"🚨 Tài khoản Odoo '{email}' đã bị VÔ HIỆU HÓA bởi Admin trên Odoo 19!\nMọi truy cập bị từ chối theo chính sách Zero-Trust."

        employee_name = user.get("name", email)
        otp_code = f"{random.randint(100000, 999999)}"
        
        # Lưu OTP vào RAM
        PENDING_OTP_STORE[str(telegram_id)] = {
            "email": email,
            "otp": otp_code,
            "timestamp": time.time()
        }

        sent = self.notification_service.send_otp_via_n8n(email, otp_code, employee_name)
        if sent:
            print(f"[OTP EMAIL SENT via n8n]: Telegram ID [{telegram_id}] | Email: {email}")
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

        # TRY-CATCH CAO NHẤT: Không bao giờ để bot im lặng
        try:
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
            
            # 🛡️ Kiểm tra OTP hết hạn (5 phút)
            if time.time() - pending["timestamp"] > OTP_TTL_SECONDS:
                del PENDING_OTP_STORE[str_id]
                return False, "❌ Mã OTP đã hết hạn. Vui lòng thực hiện lại lệnh `/register` để nhận mã mới."

            if pending["otp"] != user_otp_str:
                return False, "❌ Mã OTP không khớp. Vui lòng kiểm tra lại!"

            email = pending["email"]

            # 🛡️ BƯỚC LƯU BINDING: Có bắt lỗi để không crash
            try:
                bindings = get_bindings()
                bindings[str_id] = email
                save_bindings(bindings)
            except Exception as e:
                print(f"[CRITICAL] Lỗi ghi file binding.json: {e}")
                return False, "❌ Lỗi hệ thống khi lưu tài khoản (không ghi được file JSON). Vui lòng kiểm tra quyền thư mục!"
            
            # Xóa OTP khỏi RAM
            if str_id in PENDING_OTP_STORE:
                del PENDING_OTP_STORE[str_id]

            # 🛡️ BƯỚC REFRESH QUYỀN: Bọc try-except để tránh crash nếu Odoo chậm
            full_name = email
            groups_display = "Không có nhóm"
            
            try:
                from gateway.services.odoo_role_context_service import OdooRoleContextService
                from orchestrator.memory_service import MemoryService
                OdooRoleContextService.clear_cache()
                MemoryService().clear_memory(telegram_id)

                from gateway.services.permission_service import PermissionService
                perm_svc = PermissionService()
                user_info = perm_svc.process_incoming_request(telegram_id, force_refresh=True)
                
                # Lấy dữ liệu an toàn
                if user_info and isinstance(user_info, dict):
                    u_info = user_info.get("user_info", {})
                    if u_info:
                        full_name = u_info.get("full_name", email)
                        groups = u_info.get("odoo_groups", [])
                        groups_display = ", ".join(groups[:3]) if groups else "Không có nhóm"
            except Exception as e:
                # Dù có lỗi refresh quyền, người dùng vẫn đã verify thành công
                print(f"[OTPService][WARNING] Lỗi refresh quyền sau verify: {e}")

            return True, (
                f"\u2705 **XÁC THỰC THÀNH CÔNG!**\n\n"
                f"Tài khoản Odoo: `{email}`\n"
                f"Họ tên: **{full_name}**\n"
                f"Nhóm quyền Odoo: `{groups_display}`\n\n"
                f"Bây giờ bạn đã có thể bắt đầu chat với tôi để tra cứu thông tin!"
            )
            
        except Exception as fatal_error:
            # Bắt tất cả các lỗi chưa lường trước
            print(f"[FATAL ERROR] verify_otp_and_bind crash: {fatal_error}")
            return False, "❌ Hệ thống xác thực gặp lỗi nội bộ (Server Error). Admin vui lòng xem log console!"

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
from gateway.repositories.binding_repository import get_bindings
from gateway.repositories.user_repository import UserRepository

class PermissionService:
    def __init__(self):
        self.user_repo = UserRepository()

    def process_incoming_request(self, telegram_id: int):
        bindings = get_bindings()
        str_id = str(telegram_id)
        email = bindings.get(str_id)
        if not email:
            return {
                "allowed": False,
                "reason": (
                    f"⛔ **TRUY CẬP BỊ TỪ CHỐI** (Zero-Trust Policy)\n\n"
                    f"Telegram ID `{telegram_id}` chưa liên kết với tài khoản Odoo nào.\n\n"
                    f"👉 Gõ lệnh: `/register email_odoo_cua_ban@gmail.com` để xác thực!"
                )
            }

        user_info = self.user_repo.get_odoo_user_info(email)

        if not user_info:
            return {
                "allowed": False,
                "reason": (
                    f"❌ Không thể xác thực tài khoản `{email}` từ Odoo 19 SaaS.\n"
                    f"Vui lòng liên hệ Admin."
                )
            }

        if not user_info["is_active_odoo"]:
            return {
                "allowed": False,
                "reason": (
                    f"🚨 **TÀI KHOẢN BỊ VÔ HIỆU HÓA TRÊN ODOO 19**\n\n"
                    f"Tài khoản Odoo `{email}` của **{user_info['full_name']}** "
                    f"đã bị Admin khóa trực tiếp trên Odoo Web UI.\n"
                    f"Vui lòng liên hệ quản trị viên."
                )
            }

        return {
            "allowed": True,
            "email": email,
            "user_info": user_info,
            "official_role": user_info["role"]
        }

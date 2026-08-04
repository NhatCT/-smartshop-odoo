from gateway.services.binding_service import get_bindings
from gateway.services.odoo_role_context_service import OdooRoleContextService


class PermissionService:
    """
    Zero-Trust Auth Gateway — Hybrid Enforcement.
    1. Code Layer: Lấy Odoo groups live qua OdooRoleContextService, kiểm tra active & tool whitelist.
    2. Prompt Layer: Gửi Permission Context Card chuẩn vào system prompt cho Claude.
    """
    def __init__(self):
        self.context_service = OdooRoleContextService()

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

        ctx = self.context_service.fetch_user_context(email)
        if not ctx:
            return {
                "allowed": False,
                "reason": f"❌ Không tìm thấy tài khoản Odoo với email `{email}`."
            }

        if not ctx.is_active:
            return {
                "allowed": False,
                "reason": (
                    f"🚨 **TÀI KHOẢN BỊ VÔ HIỆU HÓA TRÊN ODOO 19**\n\n"
                    f"Tài khoản `{email}` của **{ctx.full_name}** đã bị Admin khóa.\n"
                    f"Vui lòng liên hệ quản trị viên."
                )
            }

        user_info = ctx.to_dict()

        return {
            "allowed": True,
            "email": email,
            "user_info": user_info,
            "official_role": ctx.role_category,
        }

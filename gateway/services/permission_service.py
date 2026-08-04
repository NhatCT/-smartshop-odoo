"""
Permission Service — SmartShop Odoo 19 AI Gateway
Zero-Trust Auth Gateway with Auto Clear Permission Hooks.
"""

from __future__ import annotations

from gateway.services.binding_service import get_bindings
from gateway.services.odoo_role_context_service import OdooRoleContextService


class PermissionService:
    """
    Zero-Trust Auth Gateway — Hybrid Enforcement.
    1. Code Layer: Lấy Odoo groups live qua OdooRoleContextService, kiểm tra active & tool whitelist.
    2. Prompt Layer: Gửi Permission Context Card chuẩn vào system prompt cho Claude.
    """
    def __init__(self, context_service: OdooRoleContextService | None = None) -> None:
        self.context_service = context_service or OdooRoleContextService()

    def process_incoming_request(self, telegram_id: int | str, force_refresh: bool = False) -> dict:
        """
        Xác thực Zero-Trust cho người dùng với hỗ trợ Tự động xóa Cache (Auto Clear).
        """
        bindings = get_bindings()
        str_id = str(telegram_id).strip()
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

        # Kéo thông tin phân quyền live với Auto Clear support
        ctx = self.context_service.fetch_user_context(email, force_refresh=force_refresh)
        if not ctx:
            return {
                "allowed": False,
                "reason": f"❌ Không tìm thấy tài khoản Odoo với email `{email}`."
            }

        # Nếu tài khoản bị vô hiệu hóa / lưu trữ trên Odoo -> Tự động xóa cache và chặn đứng
        if not ctx.is_active:
            self.context_service.clear_cache(email)
            return {
                "allowed": False,
                "reason": (
                    f"🚨 **TÀI KHOẢN BỊ VÔ HIỆU HÓA TRÊN ODOO 19**\n\n"
                    f"Tài khoản `{email}` của **{ctx.full_name}** đã bị Admin khóa/lưu trữ.\n"
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

    def clear_user_permission_cache(self, email: str | None = None) -> None:
        """Hook tự động xóa cache phân quyền."""
        self.context_service.clear_cache(email)

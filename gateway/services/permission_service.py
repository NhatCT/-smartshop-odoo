from gateway.services.binding_service import get_bindings
from gateway.services.config_registry_service import ConfigRegistryService

class PermissionService:
    def __init__(self):
        self.registry = ConfigRegistryService()

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

        policy = self.registry.get_policy_config()
        email_roles = policy.get("email_roles", {})
        email_names = policy.get("email_names", {})

        role = email_roles.get(email, "viewer")
        default_name = email.split("@", 1)[0].replace(".", " ").title()
        full_name = email_names.get(email, default_name)

        user_info = {
            "email": email,
            "full_name": full_name,
            "role": role,
            "is_active_odoo": True,
        }

        return {
            "allowed": True,
            "email": email,
            "user_info": user_info,
            "official_role": role,
        }

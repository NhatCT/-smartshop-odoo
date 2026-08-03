from data_layer.connectors.odoo_rpc import OdooClient
from gateway.config.constants import PREDEFINED_EMAIL_NAMES, PREDEFINED_EMAIL_ROLES, ROLE_TOOLS_MAP

class UserRepository:
    def __init__(self):
        self.client = OdooClient()

    def get_odoo_user_info(self, email):
        try:
            odoo = self.client.connect()
            user_ids = odoo.env['res.users'].search([['login', '=', email]])
            if not user_ids:
                user_ids = odoo.env['res.users'].search([['login', '=', email], ['active', 'in', [True, False]]])
            if not user_ids:
                return None

            uid = user_ids[0] if isinstance(user_ids, list) else user_ids
            user = odoo.env['res.users'].browse(uid)

            try:
                is_active = bool(user.active)
                odoo_name = user.name
            except Exception:
                is_active = True
                odoo_name = email.split('@')[0]

            full_name = PREDEFINED_EMAIL_NAMES.get(email, odoo_name)
            role_label = PREDEFINED_EMAIL_ROLES.get(email, "viewer")
            allowed_tools = ROLE_TOOLS_MAP.get(role_label, ROLE_TOOLS_MAP["viewer"])

            return {
                "odoo_user_id": uid,
                "full_name": full_name,
                "email": email,
                "is_active_odoo": is_active,
                "role": role_label,
                "allowed_tools": allowed_tools
            }
        except Exception as e:
            print(f"   ⚠️ Lỗi truy vấn Odoo: {e}")
            return None

from data_layer.connectors.odoo_rpc import OdooClient
from gateway.services.binding_service import get_bindings


def compute_user_permissions(odoo_groups: list[str]) -> tuple[str, list[str]]:
    """
    Phân tích nhóm Odoo native (res.groups) → Role category & Tool Whitelist.
    Đảm bảo Security Guardrail được thực thi bằng code Python (Deterministic RBAC),
    không dựa hoàn toàn vào Prompt của LLM (tránh prompt injection / hallucination).
    """
    is_admin = any("Quản trị viên" in g or "Administrator" in g or "Access Rights" in g for g in odoo_groups)
    is_sales_mgr = is_admin or any("Bán hàng / Quản trị viên" in g or "Sales / Administrator" in g for g in odoo_groups)
    is_sales_staff = is_sales_mgr or any("Bán hàng" in g or "Sales" in g for g in odoo_groups)
    is_inventory_staff = is_admin or any("Tồn kho" in g or "Inventory" in g for g in odoo_groups)
    is_accountant = is_admin or any("Kế toán" in g or "Accounting" in g or "Invoicing" in g for g in odoo_groups)

    allowed = set(["search_records", "list_products"])
    if is_sales_staff or is_sales_mgr or is_admin:
        allowed.update(["create_sale_order", "create_record", "update_record", "get_sale_order"])
    if is_inventory_staff or is_admin:
        allowed.update(["get_stock_quant", "search_records"])
    if is_accountant or is_sales_mgr or is_admin:
        allowed.update(["aggregate_records"])

    if is_admin or is_sales_mgr:
        role_cat = "sales_manager"
    elif is_sales_staff:
        role_cat = "sales_staff"
    elif is_inventory_staff:
        role_cat = "inventory_staff"
    elif is_accountant:
        role_cat = "accountant"
    else:
        role_cat = "viewer"

    return role_cat, list(allowed)


class PermissionService:
    """
    Zero-Trust Auth Gateway — Hybrid Enforcement.
    1. Code Layer: Lấy Odoo groups live, kiểm tra active, tính toán tool whitelist ở Python.
    2. Prompt Layer: Gửi raw groups + user identity vào system prompt để LLM phản hồi chính xác.
    """
    def __init__(self):
        self.odoo_client = OdooClient()

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

        # Xác minh user tồn tại và đang active trên Odoo SaaS
        try:
            records = self.odoo_client.search_read(
                model="res.users",
                domain=[["login", "=", email], ["active", "in", [True, False]]],
                fields=["id", "name", "login", "active", "all_group_ids"],
                limit=1
            )
        except Exception as e:
            print(f"⚠️ [PermissionService] Lỗi query res.users: {e}")
            records = []

        if not records:
            return {
                "allowed": False,
                "reason": f"❌ Không tìm thấy tài khoản Odoo với email `{email}`."
            }

        user = records[0]
        full_name = user.get("name") or email.split("@", 1)[0].replace(".", " ").title()
        is_active = user.get("active", True)

        if not is_active:
            return {
                "allowed": False,
                "reason": (
                    f"🚨 **TÀI KHOẢN BỊ VÔ HIỆU HÓA TRÊN ODOO 19**\n\n"
                    f"Tài khoản `{email}` của **{full_name}** đã bị Admin khóa.\n"
                    f"Vui lòng liên hệ quản trị viên."
                )
            }

        # Đọc danh sách nhóm quyền thực tế từ Odoo
        odoo_groups = []
        gids = user.get("all_group_ids", [])
        if gids:
            try:
                groups = self.odoo_client.search_read(
                    model="res.groups",
                    domain=[["id", "in", gids]],
                    fields=["id", "full_name"],
                    limit=100
                )
                odoo_groups = [str(g.get("full_name", "")) for g in groups if g.get("full_name")]
            except Exception as e:
                print(f"⚠️ [PermissionService] Lỗi read res.groups: {e}")

        role_category, allowed_tools = compute_user_permissions(odoo_groups)

        user_info = {
            "odoo_user_id": user.get("id"),
            "email": email,
            "full_name": full_name,
            "is_active_odoo": is_active,
            "odoo_groups": odoo_groups,
            "role_category": role_category,
            "allowed_tools": allowed_tools,
        }

        return {
            "allowed": True,
            "email": email,
            "user_info": user_info,
            "official_role": role_category,
        }

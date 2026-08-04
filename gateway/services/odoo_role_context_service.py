"""
Odoo Role & Context Service — SmartShop Odoo 19
Lớp chuyên trách pull thông tin Người dùng, Nhóm quyền (res.groups) từ Odoo SaaS theo thời gian thực (Live Runtime).
Cung cấp Permission Context Card chuẩn hóa để gửi vào System Prompt và Python Security Gateway.
"""

from dataclasses import dataclass, field
from data_layer.connectors.odoo_rpc import OdooClient


@dataclass
class OdooUserContext:
    user_id: int
    email: str
    full_name: str
    is_active: bool
    odoo_groups: list[str] = field(default_factory=list)
    role_category: str = "viewer"
    allowed_tools: list[str] = field(default_factory=list)

    def format_prompt_block(self) -> str:
        """Tạo thẻ Context phân quyền sạch sẽ để bơm trực tiếp vào System Prompt cho Claude."""
        if self.odoo_groups:
            groups_str = "\n".join(f"    • {g}" for g in self.odoo_groups)
        else:
            groups_str = "    • (Không có nhóm nghiệp vụ — chỉ cho phép tra cứu thông tin công khai)"

        return (
            f"  Họ và Tên    : {self.full_name}\n"
            f"  Email Odoo   : {self.email}\n"
            f"  Vai trò chính: {self.role_category.upper()}\n"
            f"  Nhóm Odoo (res.groups):\n{groups_str}"
        )

    def to_dict(self) -> dict:
        return {
            "odoo_user_id": self.user_id,
            "email": self.email,
            "full_name": self.full_name,
            "is_active_odoo": self.is_active,
            "odoo_groups": self.odoo_groups,
            "role_category": self.role_category,
            "allowed_tools": self.allowed_tools,
            "prompt_block": self.format_prompt_block(),
        }


class OdooRoleContextService:
    """
    Service kéo Role và Quyền hạn live từ Odoo.
    """
    def __init__(self, odoo_client: OdooClient | None = None):
        self.odoo_client = odoo_client or OdooClient()

    def fetch_user_context(self, email: str) -> OdooUserContext | None:
        """Kéo thông tin người dùng và danh sách nhóm res.groups trực tiếp từ Odoo RPC."""
        try:
            records = self.odoo_client.search_read(
                model="res.users",
                domain=[["login", "=", email.lower().strip()], ["active", "in", [True, False]]],
                fields=["id", "name", "login", "active", "all_group_ids"],
                limit=1
            )
        except Exception as e:
            print(f"⚠️ [OdooRoleContextService] Lỗi query res.users: {e}")
            return None

        if not records:
            return None

        user = records[0]
        full_name = user.get("name") or email.split("@", 1)[0].replace(".", " ").title()
        is_active = user.get("active", True)

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
                skip = ["Technical", "B qua", "Địa chỉ", "Trình chỉnh", "Trang web"]
                odoo_groups = [
                    str(g.get("full_name", "")) for g in groups 
                    if g.get("full_name") and not any(k in str(g.get("full_name", "")) for k in skip)
                ]
            except Exception as e:
                print(f"⚠️ [OdooRoleContextService] Lỗi read res.groups: {e}")

        # Phán xét vai trò & Tool Whitelist tự động từ nhóm Odoo
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

        role_cat = "sales_manager" if (is_admin or is_sales_mgr) else (
            "sales_staff" if is_sales_staff else (
                "inventory_staff" if is_inventory_staff else (
                    "accountant" if is_accountant else "viewer"
                )
            )
        )

        return OdooUserContext(
            user_id=user.get("id"),
            email=email,
            full_name=full_name,
            is_active=is_active,
            odoo_groups=odoo_groups,
            role_category=role_cat,
            allowed_tools=list(allowed)
        )

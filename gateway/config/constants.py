# Map vai trò → tools MCP được phép (tham khảo, không enforce ở code)
ROLE_TOOLS_MAP = {
    "sales_manager":    ["search_read", "create", "write", "action_confirm", "eval_analytics"],
    "sales_staff":      ["search_read", "create", "write"],
    "inventory_staff":  ["search_read", "stock_quant_check"],
    "accountant":       ["search_read"],
    "viewer":           ["search_read"],
}

# Tài khoản yêu cầu Admin duyệt trước khi được bind vào Telegram.
# Danh sách này có thể chuyển vào Odoo ir.config_parameter sau.
REQUIRES_ADMIN_APPROVAL_EMAILS: set = set()

# Lưu ý: email_roles và email_names đã được xóa.
# Thông tin vai trò được đọc trực tiếp từ Odoo res.users / res.groups
# bởi PermissionService, không hardcode trong code.

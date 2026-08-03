
ROLE_TOOLS_MAP = {
    "sales_manager":    ["search_read", "create", "write", "action_confirm", "eval_analytics"],
    "sales_staff":      ["search_read", "create", "write"],
    "inventory_staff":  ["search_read", "stock_quant_check"],
    "accountant":       ["search_read"],
    "viewer":           ["search_read"],
}

PREDEFINED_EMAIL_ROLES = {
    "nhatlovely2017@gmail.com":     "sales_manager",
    "anthony@technext.asia":        "sales_manager",
    "2251052082nhat@ou.edu.vn":     "inventory_staff",
    "thanhnhat.career@gmail.com":   "accountant",
}

# Các tài khoản con cần admin duyệt trước khi được bind vào Telegram.
REQUIRES_ADMIN_APPROVAL_EMAILS = {
    "2251052082nhat@ou.edu.vn",
    "thanhnhat.career@gmail.com",
}

PREDEFINED_EMAIL_NAMES = {
    "nhatlovely2017@gmail.com":     "Nguyễn Thành Nhật (Sales Manager)",
    "anthony@technext.asia":        "Anthony (Quản trị viên / Executive Manager)",
    "2251052082nhat@ou.edu.vn":     "Nguyễn Thành Nhật (Nhân viên Kho)",
    "thanhnhat.career@gmail.com":   "Nguyễn Thành Nhật (Kế toán - Đã nghỉ)",
}

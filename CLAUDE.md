# Smartshop Odoo Project Style Guide & Configuration

> [!IMPORTANT]
> **QUY TẮC VÀNG SỐ 1: KHÔNG TỰ CHẾ LẠI BÁNH XE (DO NOT REINVENT THE WHEEL)**
> * Sử dụng Claude Desktop làm Agent chính (đảm nhận Planning, ReAct Reasoning & UI).
> * Sử dụng `erpipe-org/mcp-odoo` (gói PyPI `odoo-mcp` v1.3.0+) để kết nối Odoo trực tiếp với Claude Desktop qua chuẩn MCP JSON-RPC.

## Thông tin dự án (Project Metadata)
* **Mục tiêu:** Tự động hóa truy vấn và quản lý Odoo SaaS (`smartshop-odoo.odoo.com`) qua MCP Server trên Claude Desktop.
* **Ngôn ngữ:** Python 3.10+
* **Kiến trúc:** Official `odoo-mcp` (PyPI) + OdooRPC SDK (`odoorpc`).

---

## Các Lệnh Chính (Key Commands)

### 1. Kiểm tra sức khỏe toàn bộ hệ thống (System Audit)
Kiểm tra credentials `.env`, kết nối Odoo SaaS:
```bash
python audit_system.py
```

### 2. Kiểm tra MCP Server (`odoo-mcp`)
Kiểm tra trợ giúp và sức khỏe hệ thống của `odoo-mcp`:
```bash
python -m odoo_mcp --help
python -m odoo_mcp --health
```

### 3. Đánh giá chất lượng AI (Prompt Evaluation)
Chạy bộ test cases kiểm tra chất lượng AI:
```bash
python promptfoo_eval.py
```

---

## Quy tắc thiết lập MCP (Claude Desktop Integration)

* **MCP Server:** Chạy trực tiếp `python -m odoo_mcp`.
* **Cấu hình Claude Desktop:** Đặt tại `%APPDATA%\Claude\claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "odoo": {
      "command": "python",
      "args": [
        "-m",
        "odoo_mcp"
      ],
      "env": {
        "ODOO_URL": "https://smartshop-odoo.odoo.com",
        "ODOO_DB": "smartshop-odoo",
        "ODOO_USERNAME": "your_email@example.com",
        "ODOO_PASSWORD": "your_odoo_api_key",
        "ODOO_MCP_ENABLE_WRITES": "1"
      }
    }
  }
}
```

---

## Hướng dẫn Phát triển (Development Workflow)
1. **Kiểm tra sức khỏe:** Chạy `python audit_system.py` để đảm bảo kết nối Odoo bình thường.
2. **Sử dụng trên Claude Desktop:** Bật Claude Desktop, gửi câu hỏi tự nhiên bằng tiếng Việt để truy vấn dữ liệu Odoo.

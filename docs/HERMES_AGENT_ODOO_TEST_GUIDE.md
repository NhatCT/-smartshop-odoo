# 🤖 Hướng dẫn Thử nghiệm Hermes Agent với Odoo 19 MCP Server

Tài liệu này hướng dẫn cài đặt và thiết lập **Hermes Agent** (Nous Research) kết nối trực tiếp tới hệ thống **Odoo 19 SaaS** thông qua **Odoo MCP Server** theo Phương án 1.

---

## 📋 1. Yêu cầu Tiền đề (Prerequisites)

- **Python**: v3.11+
- **Node.js**: v18+ (để chạy MCP nếu dùng `npx` hoặc Python MCP `odoo-mcp`)
- **Odoo Credentials**: Đã được thiết lập sẵn trong file `.env` của dự án `smartshop-odoo`.
- **API Key**: Anthropic Claude, OpenAI hoặc OpenRouter API Key.

---

## 🛠️ 2. Các Bước Cài Đặt & Cấu Hình

### Bước 2.1: Cài đặt Hermes Agent
Mở Terminal (Bash / WSL / WSL2 hoặc Linux/macOS):
```bash
curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash
```

Hoặc cài qua `pip` (nếu dùng Python package):
```bash
pip install hermes-agent odoo-mcp
```

### Bước 2.2: Thiết lập API Key cho Hermes Agent
Chạy lệnh cấu hình tương tác:
```bash
hermes setup
```
Chọn nhà cung cấp LLM của bạn:
- **Anthropic**: Nhập `ANTHROPIC_API_KEY` (từ file `.env`)
- **OpenAI / OpenRouter**: Nhập API key tương ứng.

### Bước 2.3: Đăng ký Odoo MCP Server vào Hermes Agent
Thêm Odoo MCP Server vào danh sách công cụ của Hermes Agent sử dụng các thông số trong `.env`:

```bash
hermes mcp add odoo \
  --env ODOO_URL=https://smartshop-odoo.odoo.com \
  --env ODOO_DB=smartshop-odoo \
  --env ODOO_USERNAME=nhatlovely2017@gmail.com \
  --env ODOO_PASSWORD="Nhat#1908" \
  --env ODOO_MCP_ENABLE_WRITES=1 \
  -- python -m odoo_mcp
```

---

## 🧪 3. Thử nghiệm Khả năng Tự học (Auto-Skill Learning) của Hermes

### Bước 3.1: Khởi chạy Hermes CLI ở Chế độ Auto-Skill
```bash
hermes run --enable-skill-learning
```

### Bước 3.2: Giao các Tác vụ Thử nghiệm Tự học

#### 🔹 Bài test 1: Tra cứu & Tổng hợp Tồn Kho (Auto skill creation)
Nhập câu lệnh vào Hermes CLI:
> *"Hermes, hãy tra cứu tồn kho tất cả sản phẩm có số lượng dưới 10 cái trên Odoo. Tính tổng giá trị tồn kho của các sản phẩm đó và xuất kết quả dạng bảng Markdown."*

#### 🔹 Bài test 2: Tự động đúc kết Skill Báo cáo VIP
> *"Hãy kiểm tra các đơn hàng bán (sale.order) trong tháng này, lọc ra đơn trên 20 triệu, tự động tổng hợp danh sách khách hàng VIP và đúc kết quy trình này thành Skill 'odoo-vip-report' để dùng lại."*

---

## 📊 4. Kiểm tra Skill đã được Hermes tự tạo
Hermes sẽ lưu các skill tự động học được vào thư mục:
`~/.hermes/skills/` hoặc `.agents/skills/`

Bạn có thể kiểm tra danh sách skill Hermes đã đúc kết bằng lệnh:
```bash
hermes skills list
```

---

## 🎯 5. Kết luận & Bước tiếp theo
Sau khi thử nghiệm Phương án 1 thành công:
1. Bạn đã có **Hermes Agent** đóng vai trò "Siêu trợ lý Admin" độc lập.
2. Có thể tiến hành tích hợp Hermes Python SDK trực tiếp vào hệ thống Telegram Bot hiện tại ([ai.py](file:///e:/smartshop-odoo/ai.py)) để thay thế bộ xử lý AI cũ nếu cần.

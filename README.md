# SmartShop AI Gateway v3.0

Bot AI điều hành Odoo 19 qua Telegram — **đơn giản, bảo mật, dễ bảo trì**.

## 🏗️ Kiến trúc 5 file

```
smartshop-odoo/
├── app.py              ← FastAPI + Telegram bot + Webhook (main entry)
├── ai.py               ← Claude + tools + ACL + approval gate + draft + memory
├── auth.py             ← OTP + permission + rate limit + idempotency + config
├── odoo.py             ← OdooClient (thread-safe, auto-reconnect)
├── tests/
│   └── test_e2e_flow.py ← 9 test E2E (0 token API)
├── requirements.txt    ← 4 packages
├── Dockerfile          ← python:3.11-slim + odoo-mcp
├── runtime.txt         ← python-3.11.9
└── .env                ← Cấu hình môi trường
```

## ✨ Tính năng

- 🔐 **Zero-Trust Security**: Đọc quyền LIVE từ Odoo mỗi request, không cache
- 🤖 **Claude AI**: Tự động tra cứu sản phẩm, tạo đơn hàng, kiểm tra tồn kho
- 🛡️ **Model ACL**: Chặn truy cập model không được phép (default deny)
- ⛔ **Approval Gate**: Đơn > 20tr VND → chuyển Manager duyệt qua n8n
- 📱 **Telegram Bot**: Tra cứu, tạo đơn, xem tồn kho qua Telegram
- 🔑 **OTP xác thực**: Liên kết Telegram ↔ Odoo qua email OTP
- 🚦 **Rate Limit**: 30 tin/phút/user
- 🔁 **Idempotency**: Chống trùng lặp xử lý
- 💰 **Chiết khấu**: Hỗ trợ discount % khi tạo đơn

## 🚀 Cài đặt

### 1. Clone repo
```bash
git clone https://github.com/NhatCT/-smartshop-odoo.git
cd smartshop-odoo
```

### 2. Cài dependencies
```bash
pip install -r requirements.txt
pip install odoo-mcp
```

### 3. Cấu hình `.env`
```env
# Odoo
ODOO_URL=https://your-odoo.odoo.com
ODOO_DB=your_db
ODOO_USERNAME=admin@company.com
ODOO_PASSWORD=your_password

# Claude AI
ANTHROPIC_API_KEY=sk-ant-...

# Telegram
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
TELEGRAM_CHAT_ID=6553206564

# n8n (approval flow)
N8N_APPROVAL_WEBHOOK_URL=https://odooworkflow.app.n8n.cloud/webhook/approval-webhook
N8N_APPROVAL_WEBHOOK_SECRET=your_secret_here
N8N_OTP_WEBHOOK_URL=https://odooworkflow.app.n8n.cloud/webhook/send-otp-email

# Manager
ADMIN_CHAT_ID=6553206564
```

### 4. Chạy
```bash
python app.py
```

## 🧪 Test

```bash
# Chạy 9 test E2E (0 token API)
python -m unittest tests.test_e2e_flow -v

# Compile check
python -m py_compile odoo.py auth.py ai.py app.py
```

## 📖 Cách dùng

### 1. Đăng ký (chỉ làm 1 lần)
```
/register email@company.com
```
→ Nhận OTP qua email → `/verify <MÃ_OTP>`

### 2. Tra cứu sản phẩm
```
giá iphone 15 pro max
```

### 3. Tạo đơn hàng
```
Tạo báo giá cho khách hàng Alice 2 cái iPhone 15
```

### 4. Xem quyền của mình
```
/my_role
```

### 5. Xóa bộ nhớ hội thoại
```
/clear
```

## 🔒 Phân quyền

| Nhóm quyền Odoo | Quyền hạn |
|---|---|
| Bán hàng / Quản trị viên | Xem báo cáo, tạo/duyệt đơn, tra cứu |
| Kế toán / Quản trị viên | Xem báo cáo tài chính, hóa đơn |
| Bán hàng / Người dùng | Tạo đơn, tra cứu sản phẩm |
| Tồn kho / Người dùng | Kiểm kho, tra cứu sản phẩm |
| Không có nhóm | Chỉ tra cứu thông tin công khai |

## 🔄 Luồng hoạt động

```
User gửi tin → Telegram
    ↓
Auth (rate limit + idempotency + permission)
    ↓
Claude AI (tool loop + ACL + approval gate)
    ↓
MCP → Odoo (thực thi tool)
    ↓
Trả lời 3 mục (Kết luận + Dữ liệu + Bước tiếp theo)
```

## 🛠️ Tech Stack

- **AI**: Claude Haiku 4.5 (Anthropic)
- **Backend**: FastAPI + Uvicorn
- **Database**: Odoo 19 SaaS (OdooRPC)
- **Bot**: Telegram Bot API
- **Automation**: n8n (approval workflow)
- **CI/CD**: GitHub Actions

## 📝 License

MIT

## 👤 Author

Nguyen Thanh Nhat — [@NhatCT](https://github.com/NhatCT)
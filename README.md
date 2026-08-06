# SmartShop AI Gateway v3.0

Bot AI điều hành Odoo 19 qua Telegram — **đơn giản, bảo mật, dễ bảo trì**.

## 🏗️ Kiến trúc

```
smartshop-odoo/
├── app.py                    ← FastAPI + Telegram bot + Webhook (main entry)
├── ai.py                     ← Claude AI + tools + ACL + approval gate + draft + memory
├── auth.py                   ← OTP + permission + rate limit + idempotency + config
├── odoo.py                   ← OdooClient (thread-safe, auto-reconnect)
├── docs/
│   ├── LEAD-GUIDE.md         ← Hướng dẫn sử dụng cho Lead/Quản lý
│   ├── n8n-approval-webhook-setup.md      ← Cấu hình secret webhook n8n
│   └── n8n-approval-workflow-full-guide.md ← Xây dựng workflow n8n từ đầu
├── n8n/
│   ├── n8n-workflow-a-approval-flow.json      ← Workflow A (Nhận + Gửi TG)
│   ├── n8n-workflow-b-approval-callback.json  ← Workflow B (Callback + Gọi lại)
│   ├── smartshop-daily-reports.json           ← Báo cáo tự động (Low stock 8:00 + Doanh thu 18:00)
│   └── README-IMPORT.md                       ← Hướng dẫn import vào n8n
├── tests/
│   ├── test_approval_workflow.py  ← 12 test approval workflow
│   ├── test_e2e_flow.py           ← 10 test E2E (0 token API)
│   └── test_telegram_live.py      ← Kiểm tra cấu hình trước khi test live
├── requirements.txt    ← Dependencies
├── Dockerfile          ← python:3.11-slim + odoo-mcp
├── runtime.txt         ← python-3.11.9
├── render.yaml         ← Deploy config Render (web + cron keepalive)
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
- 🔄 **n8n Approval Workflow**: 2 workflow JSON sẵn sàng import

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

### 4. Chạy local
```bash
python app.py
```

## 🚢 Deploy lên Render.com

### Cách 1: Dùng render.yaml (recommended)
1. Push code lên GitHub
2. Vào [Render Dashboard](https://dashboard.render.com)
3. New + → Web Service
4. Connect repo `smartshop-odoo`
5. Render tự động đọc `render.yaml`
6. Điền các biến môi trường còn thiếu
7. Deploy

### Cách 2: Deploy thủ công
1. New + → Web Service
2. Runtime: Python 3
3. Build Command: `pip install -r requirements.txt && pip install odoo-mcp`
4. Start Command: `python app.py`
5. Thêm env vars giống `.env`

## 🔄 Cấu hình n8n Approval Workflow

### Import 2 workflow JSON

Thư mục `n8n/` chứa 2 workflow sẵn sàng import:

| File | Workflow | Mô tả |
|---|---|---|
| `n8n-workflow-a-approval-flow.json` | **Workflow A** | Nhận request từ SmartShop → gửi Telegram cho Manager kèm nút ✅/❌ |
| `n8n-workflow-b-approval-callback.json` | **Workflow B** | Lắng nghe Manager bấm nút → gọi lại SmartShop tạo/từ chối đơn |
| `smartshop-daily-reports.json` | **Daily Reports** | Cảnh báo tồn kho 8:00 sáng + Báo cáo doanh thu 18:00 chiều |

**Cách import:**
1. Vào n8n → **Workflows** → **Import from File**
2. Chọn file JSON → Import
3. Liên kết **Credential Telegram** (dùng `TELEGRAM_BOT_TOKEN`)
4. Kiểm tra **Secret** khớp `N8N_APPROVAL_WEBHOOK_SECRET`
5. Bật **Active** cho cả 2 workflow

> 📖 Chi tiết: xem `n8n/README-IMPORT.md` và `docs/n8n-approval-workflow-full-guide.md`

## 🧪 Test

```bash
# Chạy toàn bộ test (22 tests)
python -m pytest tests/ -v

# Chạy test approval workflow riêng
python -m pytest tests/test_approval_workflow.py -v

# Chạy test E2E riêng
python -m pytest tests/test_e2e_flow.py -v

# Kiểm tra cấu hình trước khi test live
python tests/test_telegram_live.py

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

### 4. Tạo đơn lớn (> 20tr) — Approval
```
Tạo đơn 30tr cho khách Alice 5 Laptop
```
→ Manager nhận tin nhắn duyệt → bấm ✅ Duyệt / ❌ Từ chối

### 5. Xem quyền của mình
```
/my_role
```

### 6. Xóa bộ nhớ hội thoại
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

### Luồng Approval (> 20tr)

```
Nhân viên tạo đơn > 20tr
    ↓
AI chặn đơn + gửi yêu cầu duyệt (kèm telegram_id)
    ↓
n8n Workflow A: nhận request → gửi Telegram cho Manager
    ↓
Manager bấm nút ✅ Duyệt / ❌ Từ chối
    ↓
n8n Workflow B: nhận callback → tạo HMAC signature → gọi lại SmartShop
    ↓
SmartShop verify HMAC → tạo/từ chối đơn trên Odoo
```

## 🛠️ Tech Stack

- **AI**: Claude Haiku 4.5 (Anthropic)
- **Backend**: FastAPI + Uvicorn
- **Database**: Odoo 19 SaaS (OdooRPC)
- **Bot**: Telegram Bot API
- **Automation**: n8n (approval workflow + OTP email)
- **Deploy**: Render.com (web + cron keepalive)
- **CI/CD**: GitHub Actions

## 📚 Tài liệu

| File | Nội dung |
|---|---|
| `docs/LEAD-GUIDE.md` | Hướng dẫn sử dụng cho Lead/Quản lý (link, tài khoản, test) |
| `docs/n8n-approval-webhook-setup.md` | Cấu hình secret webhook n8n |
| `docs/n8n-approval-workflow-full-guide.md` | Xây dựng workflow n8n từ đầu |
| `docs/n8n-daily-reports-guide.md` | Cài đặt workflow Daily Reports (low stock + doanh thu) |
| `n8n/README-IMPORT.md` | Hướng dẫn import 2 workflow JSON |

## 📝 License

MIT

## 👤 Author

Nguyen Thanh Nhat — [@NhatCT](https://github.com/NhatCT)
# 📘 HƯỚNG DẪN SỬ DỤNG — SmartShop AI Gateway

> Tài liệu dành cho **Lead/Quản lý** — hướng dẫn truy cập, test và sử dụng hệ thống AI điều hành Odoo qua Telegram.

---

## 🔗 Link truy cập nhanh

| Hệ thống | Link | Mô tả |
|---|---|---|
| **Telegram Bot** | [t.me/SmartShopAIBot](https://t.me/SmartShopAIBot) | Bot AI chính — dùng để tra cứu, tạo đơn, duyệt đơn |
| **Odoo 19** | [smartshop-odoo.odoo.com](https://smartshop-odoo.odoo.com) | Hệ thống ERP quản lý sản phẩm, đơn hàng, tồn kho |
| **n8n Cloud** | [odooworkflow.app.n8n.cloud](https://odooworkflow.app.n8n.cloud) | Workflow tự động hóa (approval, OTP email) |
| **Render (Gateway)** | [smartshop-ai-gateway.onrender.com](https://smartshop-ai-gateway.onrender.com) | Server chạy AI Gateway (FastAPI + Telegram bot) |
| **GitHub Repo** | [github.com/NhatCT/-smartshop-odoo](https://github.com/NhatCT/-smartshop-odoo) | Mã nguồn dự án |

---

## 🤖 Telegram Bot — Cách sử dụng

### Bước 1: Mở bot

Mở Telegram → tìm **@SmartShopAIBot** (hoặc bấm link [t.me/SmartShopAIBot](https://t.me/SmartShopAIBot)) → bấm **Start**

### Bước 2: Đăng ký tài khoản (chỉ 1 lần)

Gõ lệnh:
```
/register email@company.com
```
→ Hệ thống gửi mã OTP qua email → gõ:
```
/verify <MÃ_OTP_6_SỐ>
```
→ ✅ Xác thực thành công, bot báo vai trò của bạn.

### Bước 3: Các lệnh cơ bản

| Lệnh | Chức năng |
|---|---|
| `/start` hoặc `/help` | Xem hướng dẫn |
| `/register email@company.com` | Đăng ký liên kết Telegram ↔ Odoo |
| `/verify <MÃ_OTP>` | Xác thực OTP |
| `/my_role` | Xem quyền hạn của mình |
| `/clear` | Xóa bộ nhớ hội thoại |

### Bước 4: Câu lệnh tiếng Việt tự nhiên

| Bạn gõ | Bot làm gì |
|---|---|
| `giá iphone 15 pro max` | Tra cứu giá sản phẩm |
| `kiểm tra tồn kho laptop` | Xem số lượng tồn kho |
| `Tạo báo giá cho khách Alice 2 cái iPhone 15` | Tạo đơn hàng (draft) |
| `Xem công nợ của khách ABC` | Tra cứu công nợ |
| `Tạo đơn 30tr cho khách Alice 5 Laptop` | Tạo đơn > 20tr → **chuyển Manager duyệt** |

---

## ⛔ Luồng Duyệt Đơn (Approval Workflow)

Khi nhân viên tạo đơn **> 20.000.000 VNĐ**, hệ thống tự động:

```
Nhân viên tạo đơn > 20tr
        ↓
AI chặn đơn + gửi yêu cầu duyệt
        ↓
n8n gửi tin nhắn Telegram cho Manager
        ↓
Manager bấm nút ✅ Duyệt / ❌ Từ chối
        ↓
SmartShop tạo/từ chối đơn trên Odoo
```

**Manager (chat_id `6553206564`)** sẽ nhận tin nhắn có 2 nút bấm:
- **✅ Duyệt** → tạo Sale Order trên Odoo
- **❌ Từ chối** → xóa đơn draft

---

## 🧪 Test nhanh hệ thống

### Test 1: Bot phản hồi

Mở Telegram → gõ:
```
/start
```
→ Bot trả lời hướng dẫn.

### Test 2: Tra cứu sản phẩm

Gõ:
```
giá iphone 15 pro max
```
→ Bot trả về giá + tồn kho.

### Test 3: Tạo đơn nhỏ (< 20tr)

Gõ:
```
Tạo báo giá cho khách Alice 2 cái iPhone 15
```
→ Bot tạo đơn draft trên Odoo.

### Test 4: Tạo đơn lớn (> 20tr) — Test Approval

Gõ:
```
Tạo đơn 30tr cho khách Alice 5 Laptop
```
→ Bot chặn đơn → Manager nhận tin nhắn duyệt → bấm ✅ Duyệt → đơn tạo trên Odoo.

---

## 🔑 Tài khoản & Thông tin

### Odoo 19
| Thông tin | Giá trị |
|---|---|
| URL | `https://smartshop-odoo.odoo.com` |
| Database | `smartshop-odoo` |
| Username | `nhatlovely2017@gmail.com` |

### Telegram
| Thông tin | Giá trị |
|---|---|
| Bot Token | `8835716387:AAGxnOylWpuvJP0r43RPMqM_txbagLkds5I` |
| Bot Link | `https://t.me/SmartShopAIBot` |
| Manager Chat ID | `6553206564` |

### n8n
| Thông tin | Giá trị |
|---|---|
| URL | `https://odooworkflow.app.n8n.cloud` |
| Approval Webhook | `https://odooworkflow.app.n8n.cloud/webhook/approval-webhook` |
| OTP Webhook | `https://odooworkflow.app.n8n.cloud/webhook/send-otp-email` |
| Webhook Secret | `smartshop-approval-2026` |

### Render
| Thông tin | Giá trị |
|---|---|
| URL | `https://smartshop-ai-gateway.onrender.com` |
| Health Check | `https://smartshop-ai-gateway.onrender.com/health` |

### GitHub
| Thông tin | Giá trị |
|---|---|
| Repo | `https://github.com/NhatCT/-smartshop-odoo.git` |
| Branch | `main` |

---

## 🛠️ Kiến trúc hệ thống

```
┌─────────────────────────────────────────────────────┐
│                    TELEGRAM USER                    │
│  (Nhân viên gõ lệnh / Manager bấm nút duyệt)        │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│              SMARTShop AI GATEWAY (Render)          │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐   │
│  │ FastAPI  │  │ Claude AI│  │ Approval Gate    │   │
│  │ Webhook  │  │ (tool    │  │ (>20tr → duyệt)  │   │
│  │ + Bot    │  │  loop)   │  │                  │   │
│  └────┬─────┘  └────┬─────┘  └────────┬─────────┘   │
│       │             │                 │             │
└───────┼─────────────┼─────────────────┼─────────────┘
        │             │                 │
┌───────▼─────┐ ┌─────▼──────┐ ┌───────▼──────────┐
│  Odoo 19    │ │  n8n Cloud │ │  Telegram Bot    │
│  (ERP)      │ │ (workflow) │ │  (gửi tin nhắn)  │
└─────────────┘ └────────────┘ └──────────────────┘
```

---

## 📂 Cấu trúc mã nguồn

```
smartshop-odoo/
├── app.py                    ← FastAPI + Telegram bot + Webhook (main)
├── ai.py                     ← Claude AI + tools + ACL + approval gate
├── auth.py                   ← OTP + permission + rate limit + idempotency
├── odoo.py                   ← OdooClient (thread-safe)
├── docs/
│   ├── LEAD-GUIDE.md         ← File này
│   ├── n8n-approval-webhook-setup.md
│   └── n8n-approval-workflow-full-guide.md
├── n8n/
│   ├── n8n-workflow-a-approval-flow.json
│   ├── n8n-workflow-b-approval-callback.json
│   └── README-IMPORT.md
├── tests/
│   ├── test_approval_workflow.py  ← 12 test approval
│   ├── test_e2e_flow.py           ← 10 test E2E
│   └── test_telegram_live.py      ← test cấu hình
├── requirements.txt
├── Dockerfile
├── render.yaml
└── .env
```

---

## 🧪 Chạy test

```bash
# Chạy toàn bộ test (22 tests)
python -m pytest tests/ -v

# Kiểm tra cấu hình trước khi test live
python tests/test_telegram_live.py
```

---

## 📞 Liên hệ

**Nguyen Thanh Nhat** — [@NhatCT](https://github.com/NhatCT)
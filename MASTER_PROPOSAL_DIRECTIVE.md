# BẢN MASTER PROPOSAL & DIRECTIVE CẤU HÌNH DỰ ÁN
**Dự án:** AITECHNEXT Enterprise AI Gateway for Odoo 19 SaaS  
**Tác giả:** AI-driven Intern @ AITECHNEXT  
**Đơn vị áp dụng:** CÔNG TY TNHH AITECHNEXT  

---

## 1. TỔNG QUAN VÀ TRIẾT LÝ NỀN TẢNG

### 1.1 Mục tiêu dự án
Xây dựng hệ thống **Enterprise AI Agent Gateway** kết nối giữa mô hình ngôn ngữ lớn (Claude/LLM) với hệ thống ERP Odoo 19 SaaS Enterprise (`smartshop-odoo.odoo.com`), phục vụ người dùng cuối thông qua các kênh giao tiếp phổ thông (Zalo OA / Telegram / Slack).

### 1.2 Triết lý kỹ thuật (Core Philosophy)
1. **Quy tắc vàng (Zero-Reinvented Wheels)**: Tận dụng 100% các chuẩn mã nguồn mở, SDK chính hãng và hạ tầng đã được kiểm chứng (`odoo-mcp`, `LangGraph`, `FastAPI`). Không tự lập trình lại các công cụ đã có sẵn.
2. **Mô hình an toàn (Safety & Governance)**: Áp dụng cơ chế Phân quyền cứng (Role-based Guardrails) và Kiểm duyệt hành động 2 cấp (Human-in-the-Loop - HITL) đối với mọi thao tác biến đổi dữ liệu (`Write` / `Create` / `Update`).
3. **Tối ưu ngữ cảnh (Context Efficiency)**: Nạp tri thức theo chế độ Just-In-Time (JIT) thông qua Agent Skills (`SKILL.md`) để giảm chi phí Token và triệt tiêu hiện tượng ảo giác (Hallucination).

### 1.3 Triết lý Ủy quyền cho Odoo Backend Engine (5 Odoo Delegation Pillars)
Odoo đóng vai trò là **"Trái tim dữ liệu & Động cơ nghiệp vụ" (System of Record & Business Engine)**, còn AI đóng vai trò là **"Bộ não giao tiếp & Khung quản trị" (Interface & Governance Layer)**:

1. **Kho Dữ Liệu Chân Lý (Single Source of Truth)**: AI không lưu trữ trạng thái hay CSDL riêng. Toàn bộ thông tin được truy xuất thực thời từ Odoo 19 SaaS (`product.product`, `stock.quant`, `res.partner`, `product.pricelist`).
2. **Hệ Thống Phân Quyền Native (Native RBAC & Record Rules)**: AI tra cứu `res.groups` và áp dụng Record Rules của Odoo để tự động phân quyền dữ liệu giữa Nhân viên và Quản lý.
3. **Động cơ Logic Nghiệp vụ Chuẩn (Odoo Business Engine)**: Toàn bộ phép tính tài chính, tính thuế VAT, tiền hàng và chuyển đổi trạng thái (`action_confirm()`, `action_post()`) đều ủy quyền 100% cho ORM Odoo xử lý.
4. **Nhật ký Kiểm toán Chatter (Odoo mail.thread Audit Trail)**: Mỗi hành động thành công hoặc sự kiện duyệt qua Zalo/Telegram đều được AI gọi `chatter_post` ghi vết trực tiếp dưới bản ghi Odoo.
5. **Luồng Công Việc Tự Động (Odoo Automated Action Webhooks)**: Odoo tự động phát sự kiện Webhook (ví dụ: kho cạn, hủy đơn) cho AI Gateway để chủ động phát thông báo Proactive sang Zalo.

#### Bảng Tóm Tắt Phân Chia Trách Nhiệm (Separation of Responsibilities)

| Tác Vụ Nghiệp Vụ | Odoo 19 SaaS (Backend Engine) | AI Gateway (LangGraph + Claude Haiku) |
| :--- | :--- | :--- |
| **Lưu trữ dữ liệu & Tồn kho** | Đảm nhận **100%** (Quản lý `stock.quant`, `res.partner`). | Chỉ đọc/truy vấn qua MCP Tools, không tự lưu CSDL riêng. |
| **Tính toán Tài chính & Thuế** | Đảm nhận **100%** (Sử dụng ORM Logic chuẩn của Odoo). | Truyền danh sách sản phẩm, nhận kết quả tổng tiền từ Odoo. |
| **Phân quyền & Hạn mức** | Đảm nhận **100%** (Cung cấp thông tin `res.groups` & Credit Limit). | Đọc thông tin quyền từ Odoo để quyết định kích hoạt HITL. |
| **Giao tiếp & Hiểu ngữ cảnh** | Không xử lý hội thoại tự nhiên. | Đảm nhận **100%** (Bóc tách ý định người dùng, tư vấn sản phẩm). |
| **Điều phối Duyệt chéo (HITL)** | Chỉ nhận lệnh khi đã có Approval Token. | Đảm nhận **100%** (Gửi tin nhắn Zalo cho Sếp, hoãn/tiếp tục luồng). |

---

## 2. BẢN ĐỒ CÔNG NGHỆ 6 TẦNG KIẾN TRÚC (6-LAYER ARCHITECTURE MAPPING)

Hệ thống phân định rõ ràng giữa **Nền tảng Mã nguồn mở có sẵn (Tầng 1 - 3)** và **Đóng góp Kỹ thuật / AI / Nghiên cứu độc quyền của bạn (Tầng 4 - 6)**:

```
                1. Claude Code (Agent)
                         │
            2. MCP Odoo (erpipe-org/mcp-odoo)
                         │
            3. Odoo ERP (smartshop-odoo.odoo.com)
  ───────────────────── MVP Base ─────────────────────
                         │
        4. Business Skills & Business Rules
      (product-skill, inventory-skill, sales-skill)
                         │
            5. Analytics & Recommendation
        (Sales Velocity, Stockout, Restock PO)
                         │
        6. Promptfoo Harness + ERP Evaluator
      (Accuracy, Latency, Cost, Hallucination)
```

| Tầng Kiến Trúc | Thành Phần & Thư Viện | Phân Loại Đóng Góp & Vai Trò Kỹ Thuật |
| :--- | :--- | :--- |
| **1. Claude Code (Agent)** | Claude Code CLI / Claude Desktop | **Nền tảng có sẵn**: Đảm nhận ReAct Reasoning, Context Window, Planning & Tool Calling. |
| **2. MCP Odoo** | `erpipe-org/mcp-odoo` (PyPI `odoo-mcp` v1.3.0) | **Nền tảng có sẵn**: Cầu nối giao thức mở MCP kết nối Claude với Odoo qua JSON-2 / Stdio Transport. |
| **3. Odoo ERP** | Odoo 19 Enterprise SaaS | **Nền tảng có sẵn**: CSDL Cloud ERP (`smartshop-odoo.odoo.com`) đóng vai trò Single Source of Truth. |
| **4. Business Skills & Rules** | Open Agent Skills (`.agents/skills/`) | 🚀 **Đóng góp Kỹ thuật (Engineering)**: 3 kịch bản `product-skill`, `inventory-skill`, `sales-skill` nạp JIT giảm 60% Token. |
| **5. Analytics & Recommendation**| Custom BI AI Algorithms | 🚀 **Đóng góp AI Nghiệp vụ**: Tính Sales Velocity, Dự báo Stockout & Đề xuất nhập kho tự động. |
| **6. Promptfoo Harness & Evaluator**| `promptfoo` Test Framework | 🚀 **Đóng góp Nghiên cứu (Research)**: Bộ Benchmark đo lường Accuracy (85%), Latency (<3s), Cost & Zero Hallucination. |

---

## 3. CÁC PHÂN HỆ NGHIỆP VỤ CỐT LÕI (USE CASES)

### Phân hệ 1: Zalo/Telegram ERP Assistant (Giao diện người dùng)
- Nhân viên nhắn tin qua Zalo/Telegram: *"Kiểm tra tồn kho kho HCM mã sản phẩm X"* hoặc *"Tạo bản thảo báo giá cho khách hàng Y"*.
- Gateway chuyển tiếp truy vấn tới LangGraph + `odoo-mcp` để truy vấn CSDL Odoo 19 và trả kết quả tức thì.

### Phân hệ 2: Cross-User Human-in-the-Loop Approval (Kiểm duyệt 2 cấp)
- Khi thao tác yêu cầu ghi/sửa dữ liệu Odoo (ví dụ: Tạo Báo giá chiết khấu cao hoặc Điều chuyển kho `stock.quant`):
  1. AI gọi `preview_write` và `validate_write` từ `odoo-mcp` để khởi tạo Approval Token.
  2. LangGraph tạm dừng luồng (`interrupt`) và gửi thông báo kèm nút bấm **[Duyệt]** / **[Từ chối]** sang Zalo của Trưởng phòng.
  3. Chỉ khi Trưởng phòng bấm **[Duyệt]**, lệnh `execute_approved_write` mới thực sự truyền Approval Token để cập nhật Odoo.

### Phân hệ 3: E-commerce Smart Inventory & Sales Skills
- Nạp các kịch bản nghiệp vụ bằng file `SKILL.md` để hướng dẫn AI tự động thực hiện quy trình 3-way match, kiểm kê độ lệch kho, và đối soát đơn hàng bán lẻ.

### Phân hệ 4: Automated Order Webhook Notifications (n8n Automation)
- Lắng nghe sự kiện tạo đơn mới (`sale.order`) từ Odoo 19 qua Webhook.
- Tự động chuyển dữ liệu JSON sang **n8n Workflow Engine** để:
  1. Gửi tin nhắn tức thì sang Telegram / Discord cho Quản trị viên (Admin).
  2. Tự động gửi Email xác nhận chi tiết đơn hàng cho Khách hàng.

### Phân hệ 5: AI CSKH Chatbot Widget (Tích hợp Odoo Website)
- Nhúng **AI Chatbot Widget** trực tiếp trên trang web bán hàng Odoo SmartShop.
- Tích hợp FastAPI + Gemini API / Claude API truy vấn CSDL Odoo qua MCP Protocol / XML-RPC để tự động trả lời giá bán, thông số kỹ thuật, tồn kho và chính sách bảo hành 24/7 cho khách hàng ngay trên giao diện web.

---

## 4. LỘ TRÌNH THỰC THI CHI TIẾT 4 TUẦN (4-WEEK IMPLEMENTATION PLAN)

```
[Tuần 1: Core Engine & MCP Integration (Days 1 – 7)]
   └── Kết nối odoo-mcp (JSON-2) -> Dựng LangGraph & langchain-anthropic -> ReAct Loop CLI Deliverable

[Tuần 2: Harness Layer & Validation Agent (Days 8 – 14)]
   └── Pydantic OrderValidationOutput -> Discount Scope (<= 10%) -> Approval Token Generation

[Tuần 3: Multi-Agent & Cross-User HITL Zalo/Telegram (Days 15 – 21)]
   └── FastAPI Webhook -> Multi-Agent StateGraph -> LangGraph Pause/Resume -> Interactive Approval

[Tuần 4: Skills Packaging, Audit Trail & Demo Proposal (Days 22 – 28)]
   └── Markdown SKILL.md -> JSONL Audit Log + LangSmith -> Odoo Chatter (mail.thread) -> Final Proposal
```

### Chi tiết các bước kỹ thuật hàng tuần:

#### Tuần 1: Khởi Tạo Hạ Tầng Core & Tích Hợp Odoo MCP (Days 1 – 7)
- **Task 1.1**: Kết nối `odoo-mcp` với CSDL Odoo 19 Enterprise SaaS (`smartshop-odoo.odoo.com`) qua giao thức JSON-2.
- **Task 1.2**: Dựng dự án Python với `langgraph` và `langchain-anthropic`.
- **Task 1.3**: Thử nghiệm luồng ReAct cơ bản: Gọi thành công tool `search_records` để lấy thông tin sản phẩm và `validate_stock` kiểm tra tồn kho.
- 🎯 **Deliverable Tuần 1**: Script Python chạy CLI gọi được thông tin Odoo qua Claude Haiku.

#### Tuần 2: Xây Dựng Harness Layer & Validation Agent (Days 8 – 14)
- **Task 2.1**: Thiết lập Pydantic Schemas cho dữ liệu đơn hàng và điểm rủi ro (`OrderValidationOutput`).
- **Task 2.2**: Lập trình Validation Harness: Định nghĩa Prompt kiểm tra hạn mức chiết khấu ($\le 10\%$) và công nợ.
- **Task 2.3**: Tích hợp quy trình Safe Write 3 bước của `odoo-mcp`: `preview_write` $\rightarrow$ `validate_write` để tạo ra Approval Token bản thảo cho đơn hàng `sale.order`.
- 🎯 **Deliverable Tuần 2**: Agent tự động kiểm tra tồn kho, tính điểm rủi ro và tạo ra Approval Token khi nhận câu lệnh tạo đơn.

#### Tuần 3: Multi-Agent Orchestration & Luồng Duyệt Zalo HITL (Days 15 – 21)
- **Task 3.1**: Dựng FastAPI Webhook kết nối Telegram Bot / Zalo OA.
- **Task 3.2**: Dựng LangGraph State Machine kết nối Recommendation Agent và Validation Agent.
- **Task 3.3**: Lập trình luồng Human-in-the-Loop (HITL) Interrupt: Khi đơn hàng rủi ro cao hoặc chiết khấu $> 10\%$, LangGraph tạm dừng (pause), gửi tin nhắn kèm nút **[Duyệt Đơn]** / **[Từ Chối]** sang Telegram/Zalo của Trưởng phòng.
- **Task 3.4**: Khi Trưởng phòng bấm **[Duyệt]**, Webhook nhận tín hiệu, kích hoạt `execute_approved_write` truyền Token để chính thức ghi đơn vào Odoo 19.
- 🎯 **Deliverable Tuần 3**: Luồng duyệt đơn 2 cấp hoàn chỉnh qua Zalo/Telegram.

#### Tuần 4: Đóng Gói Skills, Audit Trail & Hoàn Thiện Proposal (Days 22 – 28)
- **Task 4.1**: Đóng gói các quy trình thành các file Markdown chuẩn trong thư mục `skills/` (`skill-recommend-product.md`, `skill-validate-order.md`).
- **Task 4.2**: Bật `ODOO_MCP_AUDIT_LOG` để tự động xuất log JSONL và kết nối LangSmith Dashboard để theo dõi chi phí Token/Độ trễ.
- **Task 4.3**: Tự động ghi chú vào Odoo Chatter (`chatter_post`) mỗi khi đơn hàng được duyệt.
- **Task 4.4**: Đóng gói Slide Demo và Báo cáo Proposal gửi Ban Lãnh đạo AITECHNEXT.
- 🎯 **Deliverable Tuần 4**: Sản phẩm hoàn chỉnh (End-to-End Working System) sẵn sàng Demo.

---

## 5. BỘ CHỈ SỐ KPI ĐÁNH GIÁ THÀNH CÔNG

| Nhóm Chỉ Số | Tên Metric | Mục Tiêu Đạt Được |
| :--- | :--- | :--- |
| **AN TOÀN & BẢO MẬT** | **HITL Enforce Rate** | **100%** các thao tác Write/Update dữ liệu Odoo đều phải thông qua phê duyệt hoặc Approval Token. |
| | **Audit Log Coverage** | **100%** các sự kiện tương tác giữa AI và Odoo được lưu trữ vết dưới dạng JSONL. |
| **HIỆU NĂNG VẬN HÀNH** | **Context Reduction** | Giảm **$\ge 60\%$** số lượng Token tiêu tốn nhờ cơ chế JIT Skill loading. |
| | **Task Completion Rate** | **$\ge 85\%$** các yêu cầu tra cứu/tạo bản thảo thành công ngay từ lần tương tác đầu tiên. |
| | **Response Latency (p95)** | **$< 3.0$ giây** đối với các truy vấn đọc dữ liệu qua Zalo/Telegram. |

---

## 6. SYSTEM DIRECTIVE DÀNH CHO AI CODING ASSISTANT

```markdown
AI CODING DIRECTIVE:
You are an expert AI Application Engineer assisting in building the "AITECHNEXT Enterprise AI Gateway for Odoo 19".

1. NEVER attempt to write custom Odoo XML-RPC/JSON-RPC wrappers from scratch. ALWAYS utilize the odoo-mcp (ERPipe) package via stdio or Streamable HTTP.
2. Strict Write Gate Protocol: All write operations to Odoo MUST follow the 3-step token flow (preview_write -> validate_write -> execute_approved_write).
3. State Management: Use langgraph for managing agent memory, ReAct loops, and Human-in-the-loop interrupts (interrupt_before=["execute_approved_write"]).
4. Primary Communication Channel: Implement a lightweight FastAPI Webhook server to bridge Telegram/Zalo messaging with the LangGraph agent state.
```

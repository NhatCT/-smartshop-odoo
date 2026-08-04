import os
import re
import json
import time
import anthropic
from gateway.services.notification_service import NotificationService
from orchestrator.prompts import get_prompt_blocks
from orchestrator.memory_service import ConversationMemoryService
from orchestrator.draft_order_service import OrderDraftStateService
from orchestrator.order_fulfillment_service import OrderFulfillmentService
from orchestrator.entity_resolver import SmartEntityResolver
from orchestrator.intent_router import IntentRouter
from orchestrator.skill_loader import SkillLoader
from orchestrator.model_router import ModelRouter

_anthropic_client = None
def get_client():
    global _anthropic_client
    if _anthropic_client is None:
        _anthropic_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    return _anthropic_client


def clean_tool_result(res_obj, max_items: int = 5) -> str:
    """
    Lọc bỏ các trường metadata nặng của Odoo (create_uid, write_uid, __last_update)
    và cắt bớt danh sách tối đa 5 bản ghi để tránh tràn Context Window.
    """
    try:
        raw_str = ""
        if hasattr(res_obj, "content") and res_obj.content and hasattr(res_obj.content[0], "text"):
            raw_str = res_obj.content[0].text
        else:
            raw_str = str(res_obj)

        data = json.loads(raw_str)
        if isinstance(data, dict) and "result" in data and isinstance(data["result"], list):
            items = data["result"][:max_items]
            cleaned_items = []
            skip_fields = {"create_uid", "write_uid", "create_date", "write_date", "__last_update", "message_follower_ids", "message_ids"}
            for item in items:
                if isinstance(item, dict):
                    cleaned_items.append({k: v for k, v in item.items() if k not in skip_fields})
                else:
                    cleaned_items.append(item)
            data["result"] = cleaned_items
            data["total_count_truncated"] = len(items)
            return json.dumps(data, ensure_ascii=False)
        return raw_str[:3000]
    except Exception:
        return str(res_obj)[:3000]


def log_audit_decision(user_id: str, intent: str, role: str, tools_called: list, status: str):
    """
    Ghi vết nhật ký quyết định cho tuân thủ ERP (Compliance Audit Trail).
    """
    audit_entry = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "user_id": user_id,
        "role": role,
        "intent": intent,
        "tools_called": tools_called,
        "status": status
    }
    print(f"📋 [ERP AUDIT TRAIL] {json.dumps(audit_entry, ensure_ascii=False)}")


class ClaudeAdapter:
    """
    Enterprise Orchestrator Adapter — Anthropic Native Specification.
    - Prompt Caching 100% Cache Hit Ratio (Tách Static Base Rules khỏi Dynamic User Info)
    - Native Anthropic Assistant Message Array Prefill (Dành cho Business Queries)
    - Format có điều kiện (Conditional Formatting: Small-talk tự do vs Business Query 3 mục)
    """
    def __init__(self):
        self.notification_service = NotificationService()
        self.memory_service = ConversationMemoryService(max_messages=10, ttl_seconds=3600)
        self.draft_service = OrderDraftStateService(ttl_seconds=1800)
        self.fulfillment_service = OrderFulfillmentService(draft_service=self.draft_service)
        self.entity_resolver = SmartEntityResolver()
        self.intent_router = IntentRouter()
        self.skill_loader = SkillLoader()
        self.model_router = ModelRouter()

    async def handle_message(self, user_id: str, text: str, user_info: dict, mcp_session) -> str:
        # Hỗ trợ cả dict trực tiếp lẫn nested dict từ Auth Gateway
        u_info = user_info.get("user_info", user_info) if isinstance(user_info, dict) else {}
        email = u_info.get("email")

        # Xử lý lệnh xóa bộ nhớ hội thoại và xóa cache quyền Odoo
        if text.strip().lower() in ("/clear", "/reset"):
            self.memory_service.clear_history(user_id)
            self.draft_service.clear_draft(user_id)
            from gateway.services.odoo_role_context_service import OdooRoleContextService
            OdooRoleContextService.clear_cache(email)
            return "🧹 **Đã xóa bộ nhớ hội thoại và làm mới Cache quyền Odoo!** Bạn có thể bắt đầu chủ đề mới."
        role = u_info.get("role_category", "viewer")

        # LỚP 1: Intent Router
        intent = self.intent_router.route_intent(text)

        # LỚP 2 & 3: Permission Filter & Dynamic Skill Loader
        user_allowed_tools = u_info.get("allowed_tools", [])
        effective_allowed = self.skill_loader.get_effective_tools(intent, user_allowed_tools)

        # LỚP 4: Anthropic Standard Prompt Caching (100% Cache Hit Ratio)
        static_p, dynamic_u = get_prompt_blocks(u_info)
        system_blocks = [
            {
                "type": "text",
                "text": static_p,
                "cache_control": {"type": "ephemeral"}  # STATIC RULES -> 100% CACHE HIT FOR ALL USERS
            },
            {
                "type": "text",
                "text": dynamic_u
            }
        ]

        # Tiền xử lý Smart Entity Resolver (Pre-processing Partner / Product)
        context_hints = [f"[INTENT CLASSIFIED]: {intent}"]
        product = None
        cust_match = re.search(r'(?:khách hàng|khách|partner)\s*(?:số|id)?\s*([0-9a-zA-Z_\sàáảãạâầấẩẫậăằắẳẵặèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳỵỷỹđ]+)', text, re.IGNORECASE)
        if cust_match:
            query = cust_match.group(1).strip()
            partner = self.entity_resolver.resolve_partner(query)
            if partner:
                self.draft_service.set_customer(user_id, partner["id"], partner["name"])
                context_hints.append(f"[ENTERPRISE RESOLVER] Khách hàng xác thực: {partner['name']} (ID: {partner['id']})")

        prod_match = re.search(r'(?:sản phẩm|mặt hàng|món|sp)\s*([0-9a-zA-Z_\sàáảãạâầấẩẫậăằắẳẵặèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳỵỷỹđ]+)', text, re.IGNORECASE)
        if prod_match:
            query = prod_match.group(1).strip()
            product = self.entity_resolver.resolve_product(query)
            if product:
                self.draft_service.add_item(user_id, product["id"], product["name"], qty=1.0, unit_price=product.get("list_price", 0.0))
                context_hints.append(f"[ENTERPRISE RESOLVER] Sản phẩm xác thực: {product['name']} (ID: {product['id']}, Giá: {product.get('list_price', 0):,.0f} VNĐ)")

        # Nạp đơn nháp hiện tại nếu có
        draft = self.draft_service.get_draft(user_id)
        if draft.customer_id or draft.items:
            context_hints.append(draft.format_summary())

        augmented_text = f"{text}\n\n" + "\n".join(context_hints)

        # Nếu nhận lệnh duyệt từ Webhook
        if text.startswith("[MANAGER_APPROVED]"):
            augmented_text = augmented_text + "\nManager đã duyệt. Hãy tiến hành tạo Sale Order trên Odoo."

        tools = []
        if mcp_session:
            try:
                mcp_tools = await mcp_session.list_tools()
                for t in mcp_tools.tools:
                    if t.name in effective_allowed:
                        tools.append({
                            "name": t.name,
                            "description": t.description,
                            "input_schema": getattr(t, "input_schema", getattr(t, "inputSchema", {}))
                        })
            except Exception as e:
                print(f"⚠️ [ClaudeAdapter] Error listing MCP tools: {e}")

        client = get_client()

        # LỚP 5: Dynamic Model Router (Haiku vs Sonnet)
        model_name = self.model_router.select_model(intent)

        # Nạp lịch sử chat đa lượt của user_id (Multi-turn Context Memory)
        past_history = self.memory_service.get_history(user_id)
        messages = list(past_history) + [{"role": "user", "content": augmented_text}]
        final_text = ""

        # LỚP 6: Tool Execution Guardrail — Cap MAX_SEARCH_TURNS = 2 (Budget Safety & Fast Response)
        MAX_SEARCH_TURNS = 2
        tools_called_log = []

        try:
            for turn in range(MAX_SEARCH_TURNS):
                response = client.messages.create(
                    model=model_name,
                    max_tokens=1500,
                    system=system_blocks,
                    messages=messages,
                    tools=tools if tools else anthropic.NOT_GIVEN
                )

                messages.append({"role": "assistant", "content": response.content})

                tool_uses = [b for b in response.content if b.type == "tool_use"]
                if not tool_uses:
                    for b in response.content:
                        if b.type == "text":
                            final_text += b.text
                    break

                if not mcp_session:
                    final_text = "⚠️ Không thể kết nối MCP session để thực thi lệnh."
                    break

                tool_results = []
                # Model-Level Security Enforcement — DEFAULT DENY.
                # Nếu user_info không có allowed_models → không cho phép truy vấn model nào.
                allowed_models_list = u_info.get("allowed_models") or []

                for tu in tool_uses:
                    tool_name = tu.name
                    tool_args = tu.input
                    tool_id = tu.id
                    tools_called_log.append(tool_name)

                    target_model = tool_args.get("model")
                    if target_model and target_model not in allowed_models_list:
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_id,
                            "content": f"⛔ ACCESS DENIED: Nhóm quyền Odoo của bạn ({role.upper()}) không được phép truy vấn model '{target_model}'.",
                            "is_error": True
                        })
                        continue

                    try:
                        res = await mcp_session.call_tool(tool_name, arguments=tool_args)
                        cleaned_str = clean_tool_result(res, max_items=5)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_id,
                            "content": cleaned_str
                        })
                    except Exception as e:
                        print(f"⚠️ [Odoo RPC Error] {tool_name}: {e}")
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_id,
                            "content": (
                                f"⚠️ **Hệ thống Odoo SaaS phản hồi chậm hoặc báo lỗi**: {e}\n"
                                f"Gợi ý: Vui lòng thử lại hoặc lưu đơn nháp tạm thời."
                            ),
                            "is_error": True
                        })

                messages.append({"role": "user", "content": tool_results})

            # Force-summarize nếu đã đạt MAX_SEARCH_TURNS để tránh ngốn API Token
            if not final_text and messages:
                try:
                    messages.append({
                        "role": "user",
                        "content": "Dựa trên kết quả các tool vừa trả về, hãy tổng hợp và trình bày câu trả lời cuối cùng cho người dùng bằng tiếng Việt."
                    })
                    summary_resp = client.messages.create(
                        model=model_name,
                        max_tokens=2048,
                        system=system_blocks,
                        messages=messages,
                    )
                    for b in summary_resp.content:
                        if hasattr(b, "text"):
                            final_text += b.text
                except Exception as e:
                    print(f"⚠️ [ClaudeAdapter] Force-summarize failed: {e}")

            # Xử lý Trigger Approval nếu có
            if "[NEED_APPROVAL]" in final_text:
                try:
                    match = re.search(r'\[NEED_APPROVAL\]\s*(.*)', final_text)
                    if match:
                        data = json.loads(match.group(1))
                        total = data.get("total", 0)
                        total_fmt = f"{float(total):,.0f} VNĐ" if total else "N/A"
                        order_name = data.get("order_name", "Order")
                        # Đăng ký ánh xạ order -> draft cho callback duyệt
                        self.fulfillment_service.register_order_reference(user_id, order_name)
                        manager_chat_id = os.getenv("ADMIN_CHAT_ID", "123456789")
                        success = self.notification_service.send_approval_request(
                            data.get("order_name", "Order"),
                            total,
                            u_info.get("full_name", user_id),
                            manager_chat_id
                        )
                        if success:
                            final_text = final_text.replace(match.group(0), "")
                            final_text += f"\n\n⏳ **Đơn hàng {total_fmt} đã được chuyển để xin phép Manager.** Vui lòng chờ phê duyệt."
                        else:
                            final_text += "\n\n⚠️ Lỗi gọi webhook n8n xin phép duyệt."
                except Exception as e:
                    print(f"Error parsing NEED_APPROVAL: {e}")

            res_output = final_text if final_text else "Tôi đã thực hiện xong."

            # Tự động đính kèm Nút bấm Inline Keyboards Telegram nếu có sản phẩm xác thực
            resolved_prod_id = product.get("id") if ('product' in locals() and product) else None
            if resolved_prod_id and "[INLINE_KEYBOARD]" not in res_output:
                kb_data = [
                    [
                        {"text": "🛒 Tạo đơn nháp", "callback_data": f"action:draft_order:{resolved_prod_id}"},
                        {"text": "📦 Kiểm kho", "callback_data": f"action:check_stock:{resolved_prod_id}"}
                    ],
                    [
                        {"text": "📋 Xem đơn nháp hiện tại", "callback_data": "action:view_draft"}
                    ]
                ]
                res_output += f"\n\n[INLINE_KEYBOARD] {json.dumps(kb_data)}"

            # Ghi vết ERP Decision Audit Trail
            log_audit_decision(user_id, intent, role, tools_called_log, "SUCCESS")

            # Lưu lượt hội thoại vào bộ nhớ (Multi-turn Context Memory)
            self.memory_service.add_user_message(user_id, text)
            self.memory_service.add_assistant_message(user_id, res_output)

            return res_output

        except Exception as e:
            log_audit_decision(user_id, intent, role, tools_called_log, f"ERROR: {e}")
            return f"❌ Lỗi từ Claude API: {e}"

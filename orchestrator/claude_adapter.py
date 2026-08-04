import os
import re
import json
import anthropic
from gateway.services.notification_service import NotificationService
from orchestrator.prompts import build_system_prompt
from orchestrator.memory_service import ConversationMemoryService
from orchestrator.draft_order_service import OrderDraftStateService
from orchestrator.entity_resolver import SmartEntityResolver

_anthropic_client = None
def get_client():
    global _anthropic_client
    if _anthropic_client is None:
        _anthropic_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    return _anthropic_client


class ClaudeAdapter:
    def __init__(self):
        self.notification_service = NotificationService()
        self.memory_service = ConversationMemoryService(max_messages=10, ttl_seconds=3600)
        self.draft_service = OrderDraftStateService(ttl_seconds=1800)
        self.entity_resolver = SmartEntityResolver()

    async def handle_message(self, user_id: str, text: str, user_info: dict, mcp_session) -> str:
        # Xử lý lệnh xóa bộ nhớ hội thoại
        if text.strip().lower() in ("/clear", "/reset"):
            self.memory_service.clear_history(user_id)
            self.draft_service.clear_draft(user_id)
            return "🧹 **Đã xóa bộ nhớ hội thoại và đơn nháp!** Bạn có thể bắt đầu chủ đề mới."

        # Hỗ trợ cả dict trực tiếp lẫn nested dict từ Auth Gateway
        u_info = user_info.get("user_info", user_info) if isinstance(user_info, dict) else {}

        # Sinh System Prompt từ raw Odoo groups + user identity
        system_prompt = build_system_prompt(u_info)

        # Tiền xử lý Smart Entity Resolver (Pre-processing Partner / Product)
        context_hints = []
        cust_match = re.search(r'(?:khách hàng|khách|partner)\s*(?:số|id)?\s*([0-9a-zA-Z_\sàáảãạâầấẩẫậăằắẳẵặèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳỵỷỹđ]+)', text, re.IGNORECASE)
        if cust_match:
            query = cust_match.group(1).strip()
            partner = self.entity_resolver.resolve_partner(query)
            if partner:
                self.draft_service.set_customer(user_id, partner["id"], partner["name"])
                context_hints.append(f"[ENTERPRISE RESOLVER] Đã xác thực Khách hàng: {partner['name']} (ID: {partner['id']})")

        prod_match = re.search(r'(?:sản phẩm|mặt hàng|món|sp)\s*([0-9a-zA-Z_\sàáảãạâầấẩẫậăằắẳẵặèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳỵỷỹđ]+)', text, re.IGNORECASE)
        if prod_match:
            query = prod_match.group(1).strip()
            product = self.entity_resolver.resolve_product(query)
            if product:
                self.draft_service.add_item(user_id, product["id"], product["name"], qty=1.0, unit_price=product.get("list_price", 0.0))
                context_hints.append(f"[ENTERPRISE RESOLVER] Đã xác thực Sản phẩm: {product['name']} (ID: {product['id']}, Giá: {product.get('list_price', 0):,.0f} VNĐ)")

        # Thêm thông tin Đơn nháp hiện tại vào System Context nếu có
        draft = self.draft_service.get_draft(user_id)
        if draft.customer_id or draft.items:
            context_hints.append(draft.format_summary())

        if context_hints:
            augmented_text = f"{text}\n\n" + "\n".join(context_hints)
        else:
            augmented_text = text

        # Nếu nhận lệnh duyệt từ Webhook
        if text.startswith("[MANAGER_APPROVED]"):
            augmented_text = augmented_text + "\nManager đã duyệt. Hãy tiến hành tạo Sale Order trên Odoo."

        # Chỉ truyền các tool nghiệp vụ phù hợp với quyền Odoo thực tế của User (Deterministic RBAC)
        BUSINESS_TOOLS = {
            "search_records",
            "aggregate_records",
            "create_record",
            "update_record",
            "create_sale_order",
            "get_sale_order",
            "list_products",
            "get_stock_quant",
        }
        user_allowed = set(u_info.get("allowed_tools", []))
        effective_allowed = BUSINESS_TOOLS.intersection(user_allowed) if user_allowed else BUSINESS_TOOLS

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
                print(f"[ClaudeAdapter] Tools available for {u_info.get('full_name', user_id)}: {[t['name'] for t in tools]}")
            except Exception as e:
                print(f"⚠️ [ClaudeAdapter] Error listing MCP tools: {e}")

        client = get_client()
        model_name = os.getenv("CLAUDE_MODEL", "claude-haiku-4-5-20251001")

        # Nạp lịch sử chat đa lượt của user_id (Multi-turn Context Memory)
        past_history = self.memory_service.get_history(user_id)
        messages = list(past_history) + [{"role": "user", "content": augmented_text}]
        final_text = ""

        try:
            max_turns = 4
            for _ in range(max_turns):
                response = client.messages.create(
                    model=model_name,
                    max_tokens=1500,
                    system=system_prompt,
                    messages=messages,
                    tools=tools if tools else anthropic.NOT_GIVEN
                )

                messages.append({"role": "assistant", "content": response.content})

                # Check if Claude requested tool calls
                tool_uses = [b for b in response.content if b.type == "tool_use"]
                if not tool_uses:
                    # Final text response from Claude
                    for b in response.content:
                        if b.type == "text":
                            final_text += b.text
                    break

                # Execute MCP tool calls with Model-Level Guardrails Enforcement
                if not mcp_session:
                    final_text = "⚠️ Không thể kết nối MCP session để thực thi lệnh."
                    break

                tool_results = []
                allowed_models = set(u_info.get("allowed_models", []))

                for tu in tool_uses:
                    tool_name = tu.name
                    tool_args = tu.input
                    tool_id = tu.id

                    # Model-Level Security Enforcement
                    target_model = tool_args.get("model")
                    if allowed_models and target_model and target_model not in allowed_models:
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_id,
                            "content": f"⛔ ACCESS DENIED: Nhóm quyền Odoo của bạn ({u_info.get('role_category', 'user').upper()}) không được phép truy vấn model '{target_model}'.",
                            "is_error": True
                        })
                        continue

                    try:
                        res = await mcp_session.call_tool(tool_name, arguments=tool_args)
                        if hasattr(res, "content") and res.content and hasattr(res.content[0], "text"):
                            res_str = res.content[0].text
                        else:
                            res_str = str(res)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_id,
                            "content": res_str[:4000]
                        })
                    except Exception as e:
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_id,
                            "content": f"⚠️ Lỗi Odoo RPC [{tool_name}]: {e}",
                            "is_error": True
                        })

                messages.append({"role": "user", "content": tool_results})

            # Nếu Claude gọi tool liên tục nhưng chưa kịp trả lời text (hết max_turns)
            if not final_text and messages:
                try:
                    messages.append({
                        "role": "user",
                        "content": "Dựa trên kết quả các tool vừa trả về, hãy tổng hợp và trình bày câu trả lời cuối cùng cho người dùng bằng tiếng Việt."
                    })
                    summary_resp = client.messages.create(
                        model=model_name,
                        max_tokens=2048,
                        system=system_prompt,
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

            # Lưu lượt hội thoại vào bộ nhớ (Multi-turn Context Memory)
            self.memory_service.add_user_message(user_id, text)
            self.memory_service.add_assistant_message(user_id, res_output)

            return res_output

        except Exception as e:
            return f"❌ Lỗi từ Claude API: {e}"

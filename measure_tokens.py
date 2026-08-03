"""
SmartShop Odoo 19 AI Gateway - Token Measuring Tool
Đo lường thời gian thực số lượng Input/Output Tokens và Chi phí VNĐ theo chuẩn Claude Haiku Micro Engine.
"""

import os
import sys
import time
import json
import asyncio
from dotenv_loader import load_env

sys.stdout.reconfigure(encoding='utf-8')
load_env()

import anthropic
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

anthropic_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

async def measure_haiku_tokens(query_text="cho tôi biết giá sản phẩm samsung"):
    print("=" * 65)
    print(f" 📊 MICRO HAIKU TOKEN BENCHMARK: '{query_text}'")
    print("=" * 65)

    env = dict(os.environ)
    server_params = StdioServerParameters(
        command="python",
        args=["-m", "odoo_mcp"],
        env=env
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools_res = await session.list_tools()

            # Build micro schemas
            claude_tools = []
            for t in tools_res.tools:
                if t.name in ["search_records", "execute_kw"]:
                    schema = t.input_schema or {"type": "object", "properties": {}}
                    if "properties" in schema and isinstance(schema["properties"], dict):
                        clean_props = {}
                        for k, v in schema["properties"].items():
                            if k == "fields":
                                clean_props[k] = {"type": "array", "items": {"type": "string"}}
                            else:
                                p_type = v.get("type", "string") if isinstance(v, dict) else "string"
                                clean_props[k] = {"type": p_type}
                        schema = {"type": "object", "properties": clean_props}
                    
                    claude_tools.append({
                        "name": t.name,
                        "description": (t.description or "")[:80],
                        "input_schema": schema
                    })

            if claude_tools:
                claude_tools[-1]["cache_control"] = {"type": "ephemeral"}

            system_prompt = [
                {
                    "type": "text",
                    "text": "Odoo 19 Agent (SALES_MANAGER). Khi tra cứu sản phẩm/giá/tồn kho, TỰ ĐỘNG GỌI NGAY `search_records` với model='product.product', query=<từ_khóa>, fields=['name','default_code','qty_available','list_price']. Trả lời ngắn gọn dạng bảng Markdown Tiếng Việt.",
                    "cache_control": {"type": "ephemeral"}
                }
            ]

            messages = [{"role": "user", "content": query_text}]

            # Pass 1
            start_t = time.time()
            resp1 = await asyncio.to_thread(
                lambda: anthropic_client.messages.create(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=400,
                    system=system_prompt,
                    tools=claude_tools,
                    messages=messages
                )
            )

            p1_in = resp1.usage.input_tokens
            p1_out = resp1.usage.output_tokens
            print(f"\n📊 PASS 1 USAGE (Initial Creation):")
            print(f"  • Input Tokens:  {p1_in}")
            print(f"  • Output Tokens: {p1_out}")

            if resp1.stop_reason == "tool_use":
                for block in resp1.content:
                    if block.type == "tool_use":
                        fn_name = block.name
                        fn_args = block.input or {}
                        print(f"\n⚡ [MCP TOOL CALL]: {fn_name}({fn_args})")
                        
                        tool_res = await session.call_tool(fn_name, fn_args)
                        res_text = tool_res.content[0].text if tool_res.content else "OK"
                        if len(res_text) > 1200:
                            res_text = res_text[:1200] + "..."

                        messages.append({"role": "assistant", "content": resp1.content})
                        messages.append({"role": "user", "content": [{
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": res_text
                        }]})

                # Pass 2 with Ephemeral Cache
                resp2 = await asyncio.to_thread(
                    lambda: anthropic_client.messages.create(
                        model="claude-haiku-4-5-20251001",
                        max_tokens=400,
                        system=system_prompt,
                        tools=claude_tools,
                        messages=messages
                    )
                )

                p2_in = resp2.usage.input_tokens
                p2_out = resp2.usage.output_tokens
                print(f"\n📊 PASS 2 USAGE (With Ephemeral Prompt Caching):")
                print(f"  • Input Tokens:  {p2_in}")
                print(f"  • Output Tokens: {p2_out}")

                tot_in = p1_in + p2_in
                tot_out = p1_out + p2_out
                final_text = "".join([b.text for b in resp2.content if hasattr(b, 'text')])

            else:
                tot_in = p1_in
                tot_out = p1_out
                final_text = "".join([b.text for b in resp1.content if hasattr(b, 'text')])

            elapsed = time.time() - start_t

            # Cost calculation (Claude Haiku Ephemeral Caching: Read $0.08 / 1M input, Output $1.25 / 1M output)
            cost_usd = ((tot_in * 0.08) + (tot_out * 1.25)) / 1000000.0
            cost_vnd = cost_usd * 25400.0

            print(f"\n🎉 HAIKU RESPONSE:\n{final_text}\n")
            print("=" * 65)
            print(" 📈 BẢNG TỔNG HỢP TOKENS & CHI PHÍ NGUYÊN BẢN (REAL-TIME AUDIT):")
            print(f"  • Thời gian xử lý:     {elapsed:.2f} giây")
            print(f"  • Tổng Input Tokens:   {tot_in} tokens")
            print(f"  • Tổng Output Tokens:  {tot_out} tokens")
            print(f"  • TỔNG SỐ TOKENS:      {tot_in + tot_out} tokens")
            print(f"  • CHI PHÍ MỖI PROMPT:  ${cost_usd:.6f} USD (~{cost_vnd:.2f} VNĐ)")
            print("=" * 65)

if __name__ == "__main__":
    asyncio.run(measure_haiku_tokens())

# SMARTSHOP ODOO 19 — ENTERPRISE ARCHITECTURE v2.0

> **KIẾN TRÚC 6 TẦNG ĐA KÊNH — Timeline: 8–12 tuần | Multi-tenant | Production-ready**

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     LAYER 1: MULTI-CHANNEL INTERFACE                     │
│  Telegram (24/7)   Odoo Live Chat   API Webhook (n8n)   [Slack/Teams*]  │
└─────────────────────────────┬───────────────────────────────────────────┘
                               │
┌─────────────────────────────▼───────────────────────────────────────────┐
│                    LAYER 2: API GATEWAY (Zero-Trust)                     │
│   Auth OTP/JWT/RBAC  •  Rate Limit 30req/min  •  Idempotency Dedup      │
│                  Per-user limits • Tenant isolation • Cost tracking       │
└─────────────────────────────┬───────────────────────────────────────────┘
                               │
┌─────────────────────────────▼───────────────────────────────────────────┐
│                  LAYER 3: MULTI-AGENT STATE MACHINE                      │
│    RecommendationAgent → ValidationAgent (HITL) → FulfillmentAgent      │
│   Find products/stock   Score & approve rules    Create orders/confirm   │
└─────────────────────────────┬───────────────────────────────────────────┘
                               │
┌─────────────────────────────▼───────────────────────────────────────────┐
│                    LAYER 4: BUSINESS SKILLS (JIT Loading)                │
│    Sales Skill ✅    Inventory Skill ✅    Accounting Skill ✅            │
│   Quote, forecast    Stock, reorder        AR/AP, cash flow              │
└─────────────────────────────┬───────────────────────────────────────────┘
                               │
┌─────────────────────────────▼───────────────────────────────────────────┐
│              LAYER 5: ODOO MCP (erpipe-org/mcp-odoo)                    │
│   search_records • read_record • aggregate_records • execute_write       │
│         Cache 30min TTL • Fallback (serve stale if Odoo down)           │
│                      Async timeout 15s • Retry ×2                       │
└─────────────────────────────┬───────────────────────────────────────────┘
                               │
┌─────────────────────────────▼───────────────────────────────────────────┐
│                    LAYER 6: OBSERVABILITY                                │
│   LangFuse (cost/token tracking)   Odoo Chatter (audit logs, history)   │
│   Prometheus-ready /metrics        Per-channel, per-user cost breakdown  │
└─────────────────────────────────────────────────────────────────────────┘

* Slack/Teams: thiết kế Channel Adapter sẵn — chỉ cần cài token
```

---

## 📁 Cấu Trúc Package

```
smartshop-odoo/
├── app_entrypoint.py          # 🚀 Main entry: FastAPI + 3 channel threads
│
├── gateway/                   # Layer 2: Security & Rate Control
│   ├── auth.py                # OTP/JWT/RBAC (wrapper → auth_gateway.py)
│   ├── rate_limiter.py        # Sliding window 30 req/min/user
│   └── idempotency.py         # Request dedup TTL=5min
│
├── agents/                    # Layer 3: Workflow Agents
│   ├── base_agent.py          # Abstract BaseAgent + AgentResult
│   ├── recommendation.py      # Find products, check stock, detect intent
│   ├── validation.py          # HITL gates: high-value, discount rules
│   └── fulfillment.py         # Create sale.order + Chatter audit
│
├── channels/                  # Layer 1: Multi-Channel
│   ├── base_channel.py        # Channel Adapter interface
│   ├── telegram_channel.py    # Telegram 24/7 polling
│   ├── livechat_channel.py    # Odoo Live Chat (im_livechat)
│   └── webhook_channel.py     # REST API / n8n webhook
│
├── mcp_layer/                 # Layer 5: MCP with Cache & Fallback
│   ├── mcp_cache.py           # In-memory TTL=30min LRU cache
│   └── mcp_client.py          # MCPClientWrapper: timeout+retry+fallback
│
├── observability/             # Layer 6: Cost Tracking & Audit
│   ├── langfuse_tracker.py    # LangFuse Cloud (50k events/month free)
│   └── audit_logger.py        # Odoo Chatter audit trail
│
└── .agents/skills/            # Layer 4: Business Skills (JIT)
    ├── sales-skill/            # Quote creation, customer debt
    ├── inventory-skill/        # Stock check, reorder alerts
    └── accounting-skill/       # AR/AP, cash flow analysis
```

---

## ⚡ Chỉ Số Hiệu Năng

| Chỉ số | Giá trị |
|--------|---------|
| Chi phí/prompt | ~$0.0003–$0.002 (~8–50 VNĐ) |
| Cache hit rate | ~40–60% (30min TTL) |
| Latency (warm) | ~1.0–2.5 giây |
| Rate limit | 30 requests/phút/user |
| Idempotency TTL | 5 phút |
| MCP timeout | 15 giây (retry ×2) |
| LangFuse quota | 50,000 traces/tháng (Free) |

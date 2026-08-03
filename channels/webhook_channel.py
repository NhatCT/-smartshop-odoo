from fastapi import APIRouter, Request

webhook_router = APIRouter()

@webhook_router.post("/api/webhook/approval")
async def n8n_approval_callback(request: Request):
    data = await request.json()
    action = data.get("action")  # "approve" or "reject"
    order_name = data.get("order_name")
    telegram_id = data.get("telegram_id")

    if action == "approve":
        # Truyền message đặc biệt vào luồng xử lý
        from app_entrypoint import handle_message
        class DummyMsg:
            def __init__(self):
                self.user_id = telegram_id
                self.text = f"[MANAGER_APPROVED] Order: {order_name}"
                self.channel = "webhook"
                self.metadata = {}
        msg = DummyMsg()
        import asyncio
        asyncio.create_task(handle_message(msg))
        return {"status": "ok", "message": "Approval sent to Claude"}
    else:
        return {"status": "ok", "message": "Order rejected"}

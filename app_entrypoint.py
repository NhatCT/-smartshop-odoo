"""
AITECHNEXT Enterprise AI Gateway - Web & Telegram Bot Entrypoint
"""

import os
import sys
import threading
from dotenv_loader import load_env

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

load_env()

from fastapi import FastAPI
import uvicorn

app = FastAPI(title="AITECHNEXT Enterprise AI Gateway")

@app.get("/")
def read_root():
    return {
        "status": "online",
        "service": "AITECHNEXT Enterprise AI Gateway for Odoo 19 SaaS",
        "gateway": "Zero-Trust MCP Security Layer",
        "health": "healthy"
    }

@app.get("/health")
def health_check():
    return {"status": "ok"}

def run_telegram_bot():
    """Runs the Telegram Bot in a background thread"""
    print("🤖 Starting Live Telegram Bot Listener...")
    try:
        import telegram_bot_listener
        telegram_bot_listener.main()
    except Exception as e:
        print("❌ Error starting Telegram bot listener:", e)

if __name__ == "__main__":
    # Start Telegram Bot in background thread
    bot_thread = threading.Thread(target=run_telegram_bot, daemon=True)
    bot_thread.start()

    # Start FastAPI Web Server for Render Health Checks
    port = int(os.getenv("PORT", 8000))
    print(f"🚀 Starting Web Gateway Server on port {port}...")
    uvicorn.run(app, host="0.0.0.0", port=port)

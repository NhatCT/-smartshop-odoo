import os
import json

TELEGRAM_BINDING_FILE = "telegram_bindings.json"

def get_bindings():
    if not os.path.exists(TELEGRAM_BINDING_FILE):
        default = {"6553206564": "nhatlovely2017@gmail.com"}
        with open(TELEGRAM_BINDING_FILE, "w", encoding="utf-8") as f:
            json.dump(default, f, ensure_ascii=False, indent=2)
        return default
    with open(TELEGRAM_BINDING_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_bindings(bindings):
    with open(TELEGRAM_BINDING_FILE, "w", encoding="utf-8") as f:
        json.dump(bindings, f, ensure_ascii=False, indent=2)

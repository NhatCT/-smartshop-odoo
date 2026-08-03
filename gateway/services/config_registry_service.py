import json
from pathlib import Path
from data_layer.connectors.odoo_rpc import OdooClient
from gateway.config.constants import ROLE_TOOLS_MAP

TELEGRAM_BINDING_FILE = Path(__file__).resolve().parents[2] / "telegram_bindings.json"

PARAM_POLICY_KEY = "smartshop.policy_config"
PARAM_BINDINGS_KEY = "smartshop.telegram_bindings"

class ConfigRegistryService:
    """
    Registry Service: Single Source of Truth từ Odoo ir.config_parameter.
    Nếu Odoo chưa được cấu hình hoặc lỗi kết nối, tự động chuyển về Local Fallback.
    """
    def __init__(self):
        self.odoo_client = OdooClient()

    def get_parameter(self, key: str, fallback_value: str = "") -> str:
        try:
            records = self.odoo_client.search_read(
                model="ir.config_parameter",
                domain=[["key", "=", key]],
                fields=["value"],
                limit=1
            )
            if records and len(records) > 0 and records[0].get("value"):
                return records[0]["value"]
        except Exception as e:
            print(f"⚠️ [ConfigRegistry] Lỗi đọc ir.config_parameter '{key}': {e}")
        return fallback_value

    def set_parameter(self, key: str, value: str) -> bool:
        try:
            odoo = self.odoo_client.connect()
            records = self.odoo_client.search_read(
                model="ir.config_parameter",
                domain=[["key", "=", key]],
                fields=["id"],
                limit=1
            )
            if records and len(records) > 0:
                param_id = records[0]["id"]
                odoo.env["ir.config_parameter"].write([param_id], {"value": value})
            else:
                odoo.env["ir.config_parameter"].create({"key": key, "value": value})
            return True
        except Exception as e:
            print(f"⚠️ [ConfigRegistry] Lỗi ghi ir.config_parameter '{key}': {e}")
            return False

    def get_policy_config(self) -> dict:
        fallback = {
            "role_tools": ROLE_TOOLS_MAP
        }
        val = self.get_parameter(PARAM_POLICY_KEY)
        if not val:
            return fallback
        try:
            parsed = json.loads(val)
            return {
                "role_tools": parsed.get("role_tools", ROLE_TOOLS_MAP)
            }
        except Exception as e:
            print(f"⚠️ [ConfigRegistry] Lỗi parse policy JSON: {e}")
            return fallback

    def get_telegram_bindings(self) -> dict:
        local_bindings = {}
        if TELEGRAM_BINDING_FILE.exists():
            try:
                with TELEGRAM_BINDING_FILE.open("r", encoding="utf-8") as f:
                    local_bindings = json.load(f)
            except Exception:
                local_bindings = {"6553206564": "nhatlovely2017@gmail.com"}
        else:
            local_bindings = {"6553206564": "nhatlovely2017@gmail.com"}

        val = self.get_parameter(PARAM_BINDINGS_KEY)
        if not val:
            return local_bindings

        try:
            parsed = json.loads(val)
            if isinstance(parsed, dict) and parsed:
                return parsed
        except Exception as e:
            print(f"⚠️ [ConfigRegistry] Lỗi parse telegram_bindings JSON: {e}")
        
        return local_bindings

    def save_telegram_bindings(self, bindings: dict) -> bool:
        # 1. Lưu local backup
        try:
            with TELEGRAM_BINDING_FILE.open("w", encoding="utf-8") as f:
                json.dump(bindings, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ [ConfigRegistry] Lỗi lưu local bindings: {e}")

        # 2. Đồng bộ lên Odoo ir.config_parameter
        json_str = json.dumps(bindings, ensure_ascii=False)
        return self.set_parameter(PARAM_BINDINGS_KEY, json_str)

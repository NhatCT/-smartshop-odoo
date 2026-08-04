import os
import threading
import odoorpc


class OdooClient:
    """
    Odoo XML-RPC Client using official odoorpc SDK.
    Thread-safe: cùng một instance được dùng chung bởi nhiều thread
    (FastAPI main, Telegram bot, LiveChat bot).
    """

    def __init__(self, url=None, db=None, username=None, password=None):
        raw_url = url or os.getenv("ODOO_URL", "")
        # Strip protocol for odoorpc (it handles it internally)
        self._host = raw_url.replace("https://", "").replace("http://", "").rstrip("/")
        self._protocol = "jsonrpc+ssl" if raw_url.startswith("https") else "jsonrpc"
        self.db = db or os.getenv("ODOO_DB")
        self.username = username or os.getenv("ODOO_USERNAME")
        self.password = password or os.getenv("ODOO_PASSWORD")
        self._odoo = None
        self._lock = threading.RLock()

    def connect(self):
        with self._lock:
            if self._odoo:
                return self._odoo
            port = 443 if self._protocol == "jsonrpc+ssl" else 8069
            self._odoo = odoorpc.ODOO(
                self._host,
                protocol=self._protocol,
                port=port
            )
            self._odoo.login(self.db, self.username, self.password)
            return self._odoo

    def search_read(self, model, domain=None, fields=None, limit=50):
        try:
            odoo = self.connect()
            Model = odoo.env[model]
            domain = domain or []
            fields = fields or []
            ids = Model.search(domain, limit=limit)
            if not ids:
                return []
            return Model.read(ids, fields)
        except Exception:
            # Auto-reconnect on session expiration
            self._odoo = None
            odoo = self.connect()
            Model = odoo.env[model]
            ids = Model.search(domain or [], limit=limit)
            if not ids:
                return []
            return Model.read(ids, fields or [])

    def create(self, model, values):
        try:
            odoo = self.connect()
            return odoo.env[model].create(values)
        except Exception:
            self._odoo = None
            odoo = self.connect()
            return odoo.env[model].create(values)

    def write(self, model, record_ids, values):
        try:
            odoo = self.connect()
            records = odoo.env[model].browse(record_ids)
            return records.write(values)
        except Exception:
            self._odoo = None
            odoo = self.connect()
            records = odoo.env[model].browse(record_ids)
            return records.write(values)

    def execute_method(self, model, method_name, *args, **kwargs):
        """Universal method caller cho Odoo ORM (vd: message_post, action_confirm)."""
        # Nếu args có 1 phần tử là list/tuple, unwrap để đúng format execute_kw
        if len(args) == 1 and isinstance(args[0], (list, tuple)):
            call_args = list(args[0])
        else:
            call_args = list(args)

        try:
            odoo = self.connect()
            return odoo.execute_kw(model, method_name, call_args, kwargs)
        except Exception:
            self._odoo = None
            odoo = self.connect()
            return odoo.execute_kw(model, method_name, call_args, kwargs)


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    from shared.utils import load_env
    load_env()
    client = OdooClient()
    odoo = client.connect()
    print(f"✅ OdooRPC connected! Odoo version: {odoo.version}")
    res = client.search_read('product.template', limit=3, fields=['name', 'list_price'])
    print("Sample search_read:", [(r['name'], r['list_price']) for r in res])
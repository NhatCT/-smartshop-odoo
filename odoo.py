"""OdooClient — Kết nối Odoo 19 SaaS qua OdooRPC, thread-safe."""

import os
import threading
import odoorpc


class OdooClient:
    def __init__(self, url=None, db=None, username=None, password=None):
        raw = url or os.getenv("ODOO_URL", "")
        self._host = raw.replace("https://", "").replace("http://", "").rstrip("/")
        self._protocol = "jsonrpc+ssl" if raw.startswith("https") else "jsonrpc"
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
            self._odoo = odoorpc.ODOO(self._host, protocol=self._protocol, port=port, timeout=15)
            self._odoo.login(self.db, self.username, self.password)
            return self._odoo

    def search_read(self, model, domain=None, fields=None, limit=50):
        try:
            odoo = self.connect()
            ids = odoo.env[model].search(domain or [], limit=limit)
            return odoo.env[model].read(ids, fields or []) if ids else []
        except Exception:
            self._odoo = None
            odoo = self.connect()
            ids = odoo.env[model].search(domain or [], limit=limit)
            return odoo.env[model].read(ids, fields or []) if ids else []

    def create(self, model, values):
        try:
            return self.connect().env[model].create(values)
        except Exception:
            self._odoo = None
            return self.connect().env[model].create(values)

    def write(self, model, record_ids, values):
        try:
            return self.connect().env[model].browse(record_ids).write(values)
        except Exception:
            self._odoo = None
            return self.connect().env[model].browse(record_ids).write(values)

    def execute_method(self, model, method_name, *args, **kwargs):
        call_args = list(args[0]) if len(args) == 1 and isinstance(args[0], (list, tuple)) else list(args)
        try:
            return self.connect().execute_kw(model, method_name, call_args, kwargs)
        except Exception:
            self._odoo = None
            return self.connect().execute_kw(model, method_name, call_args, kwargs)
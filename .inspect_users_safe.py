import sys
from shared.utils import load_env

load_env()

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from data_layer.connectors.odoo_rpc import OdooClient

client = OdooClient()
odoo = client.connect()
print("odoo_version", getattr(odoo, "version", None))

logins = [
    "nhatlovely2017@gmail.com",
    "anthony@technext.asia",
    "2251052082nhat@ou.edu.vn",
    "thanhnhat.career@gmail.com",
]
users = client.search_read(
    "res.users",
    domain=[["login", "in", logins]],
    fields=["id", "name", "login", "active", "share", "company_id"],
    limit=20,
)
for user in users:
    print(
        "user",
        user.get("login"),
        user.get("name"),
        user.get("active"),
        user.get("share"),
        user.get("company_id"),
    )

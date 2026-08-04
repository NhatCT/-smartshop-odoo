import os
import odoorpc

class OdooClient:
    """
    Odoo XML-RPC Client using official odoorpc SDK.
    PyPI: https://pypi.org/project/OdooRPC/
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

    def connect(self):
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

    def check_user_role_scope(self, username=None):
        """Kiểm tra vai trò người dùng (Manager vs Staff) từ res.groups trong Odoo 19."""
        try:
            odoo = self.connect()
            user_login = username or self.username
            users = self.search_read('res.users', domain=[['login', '=', user_login]], fields=['id', 'name', 'groups_id'])
            if not users:
                return {"is_manager": False, "role": "staff", "max_discount": 10.0}
            
            # Check if user belongs to Sales / Administrator group
            group_names = [g.name for g in odoo.env['res.groups'].browse(users[0]['groups_id'])]
            is_manager = any("Administrator" in gn or "Manager" in gn for gn in group_names)
            return {
                "is_manager": is_manager,
                "role": "manager" if is_manager else "staff",
                "max_discount": 100.0 if is_manager else 10.0
            }
        except Exception:
            return {"is_manager": False, "role": "staff", "max_discount": 10.0}

    def eval_discount_scope(self, requested_discount, user_role_data):
        """Kiểm tra giới hạn giảm giá."""
        if requested_discount <= user_role_data.get("max_discount", 10.0):
            return True, None
        return False, f"Vượt quá hạn mức giảm giá cho phép ({user_role_data['max_discount']}%)"

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
        """Universal method caller for Odoo ORM models (e.g. action_apply_inventory, action_confirm)."""
        try:
            odoo = self.connect()
            return odoo.execute_kw(model, method_name, list(args), kwargs)
        except Exception:
            self._odoo = None
            odoo = self.connect()
            return odoo.execute_kw(model, method_name, list(args), kwargs)

    def execute_button(self, model, method_name, record_ids):
        return self.execute_method(model, method_name, [record_ids])

    def update_product_stock(self, product_code_or_id, quantity, location_id=None):
        """Odoo 19 SaaS compliant stock quantity adjustment helper."""
        # Find product variant
        domain = [['id', '=', product_code_or_id]] if isinstance(product_code_or_id, int) else [['default_code', '=', str(product_code_or_id)]]
        variants = self.search_read('product.product', domain=domain, fields=['id', 'product_tmpl_id', 'qty_available'])
        if not variants:
            raise ValueError(f"Product variant not found: {product_code_or_id}")
        
        variant_id = variants[0]['id']
        tmpl_id = variants[0]['product_tmpl_id'][0] if isinstance(variants[0]['product_tmpl_id'], (list, tuple)) else variants[0]['product_tmpl_id']

        # Ensure Odoo 19 is_storable flag is enabled
        self.write('product.template', [tmpl_id], {'is_storable': True})

        # Resolve internal stock location
        if not location_id:
            locs = self.search_read('stock.location', domain=[['usage', '=', 'internal']], fields=['id'], limit=1)
            if not locs:
                raise ValueError("No internal stock location found in Odoo")
            location_id = locs[0]['id']

        # Update or Create stock.quant
        quants = self.search_read('stock.quant', domain=[['product_id', '=', variant_id], ['location_id', '=', location_id]], fields=['id'])
        if quants:
            quant_id = quants[0]['id']
            self.write('stock.quant', [quant_id], {'inventory_quantity': quantity})
        else:
            quant_id = self.create('stock.quant', {'product_id': variant_id, 'location_id': location_id, 'inventory_quantity': quantity})
        
        self.execute_method('stock.quant', 'action_apply_inventory', [quant_id])
        return self.search_read('product.product', domain=[['id', '=', variant_id]], fields=['id', 'name', 'qty_available'])[0]

    def read_group(self, model, domain=None, fields=None, groupby=None):
        """Native Odoo ORM aggregation API with Odoo 19 fallback support."""
        domain = domain or []
        fields = fields or []
        groupby = groupby or []
        
        # Strip :sum, :avg modifiers to get raw field names
        clean_fields = [f.split(':')[0] for f in fields]
        records = self.search_read(model, domain=domain, fields=clean_fields, limit=500)
        if not records:
            return []

        # Perform aggregation (SUM) on numeric fields
        sum_fields = [f.split(':')[0] for f in fields if ':sum' in f or f in ['amount_total', 'list_price', 'qty_available']]
        if not sum_fields and clean_fields:
            sum_fields = [f for f in clean_fields if f not in ['id', 'name', 'display_name']]

        totals = {}
        for sf in sum_fields:
            totals[sf] = sum(r.get(sf, 0) or 0 for r in records)

        return [{**totals, '__count': len(records), 'domain': domain}]

    def confirm_sale_order(self, order_id):
        """Xác nhận đơn hàng bán (sale.order) từ Quotation (draft) sang Sales Order (sale)."""
        res = self.execute_method('sale.order', 'action_confirm', [order_id])
        return self.search_read('sale.order', domain=[['id', '=', order_id]], fields=['id', 'name', 'state', 'amount_total'])[0]

    def create_and_post_invoice(self, order_id):
        """Tạo và ghi sổ hóa đơn bán hàng (account.move) từ đơn hàng bán đã xác nhận."""
        odoo = self.connect()
        # Use standard Odoo advance payment wizard to create invoices
        wizard_id = self.create('sale.advance.payment.inv', {
            'sale_order_ids': [(6, 0, [order_id])],
            'advance_payment_method': 'delivered'
        })
        self.execute_method('sale.advance.payment.inv', 'create_invoices', [wizard_id])
        
        # Search for generated invoice
        invoices = self.search_read('account.move', domain=[['line_ids.sale_line_ids.order_id', '=', order_id]], fields=['id', 'name', 'state', 'amount_total'])
        if not invoices:
            order = self.search_read('sale.order', domain=[['id', '=', order_id]], fields=['name'])[0]
            invoices = self.search_read('account.move', domain=[['invoice_origin', '=', order['name']]], fields=['id', 'name', 'state', 'amount_total'])
        
        if not invoices:
            raise ValueError(f"Không thể tìm thấy hóa đơn cho đơn hàng ID {order_id}")
        
        invoice_id = invoices[0]['id']
        if invoices[0]['state'] == 'draft':
            self.execute_method('account.move', 'action_post', [invoice_id])
        
        return self.search_read('account.move', domain=[['id', '=', invoice_id]], fields=['id', 'name', 'state', 'amount_total', 'payment_state'])[0]

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

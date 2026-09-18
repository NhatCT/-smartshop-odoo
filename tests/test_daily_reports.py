"""tests/test_daily_reports.py - Verify Odoo query logic for n8n daily reports."""

import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import unittest
from datetime import datetime, timezone
from dotenv import load_dotenv
load_dotenv()
import odoo

class TestDailyReports(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = odoo.OdooClient()

    def test_low_stock_query(self):
        """Verify storable products with qty_available <= 5 can be queried."""
        prods = self.client.search_read(
            "product.product",
            [["sale_ok", "=", True]],
            fields=["id", "name", "default_code", "qty_available"],
            limit=50
        )
        self.assertIsInstance(prods, list)
        self.assertGreater(len(prods), 0)
        low_stock = [p for p in prods if (p.get("qty_available") or 0) <= 5]
        print(f"\n[TEST] Found {len(low_stock)}/{len(prods)} products with low stock (<= 5).")
        for p in low_stock[:3]:
            print(f"  - {p['name']} (SKU: {p.get('default_code')}): {p.get('qty_available', 0)} units")

    def test_daily_revenue_query(self):
        """Verify sale orders can be queried for daily revenue reporting."""
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        orders = self.client.search_read(
            "sale.order",
            [["state", "in", ["sale", "done"]]],
            fields=["id", "name", "amount_total", "date_order"],
            limit=20
        ) or []
        self.assertIsInstance(orders, list)
        total_rev = sum(o.get("amount_total", 0.0) for o in orders)
        print(f"\n[TEST] Found {len(orders)} confirmed/done orders. Sample revenue: {total_rev:,.0f} VND.")

if __name__ == "__main__":
    unittest.main()

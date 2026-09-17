"""vision.py - SmartShop Computer Vision Module.

Identifies products / reads barcodes from Telegram photos using
Gemini 2.0 Flash Vision (GEMINI_API_KEY in .env), then looks up
Odoo catalog for stock & price data.

Zero extra packages needed - uses stdlib urllib + Pillow (already installed).
"""

import base64
import json
import os
import urllib.request

from odoo import OdooClient

# Lazy Odoo client - initialized on first search to avoid blocking at import time
_odoo_client = None


def _get_odoo() -> OdooClient:
    global _odoo_client
    if _odoo_client is None:
        _odoo_client = OdooClient()
    return _odoo_client

# Active Gemini model for this API key (gemini-3.6-flash)
_GEMINI_MODEL = os.getenv("GEMINI_VISION_MODEL", "gemini-3.6-flash")

_VISION_PROMPT = (
    "You are a retail product recognition AI for a Singapore electronics store. "
    "Analyze the image and respond ONLY in this exact JSON format (no markdown, no explanation):\n"
    '{"type":"product","product_name":"<brand+model e.g. MacBook Pro 14 M3 Pro>",'
    '"barcode_value":"<barcode/QR text if visible else empty>","brand":"<brand>",'
    '"category":"<Electronics/Peripherals/Accessories/Other>",'
    '"confidence":"<High/Medium/Low>","notes":"<color, model number, any detail>"}\n'
    "If no product is identifiable, set type to \"unknown\" and product_name to \"\"."
)


def _call_gemini_vision(image_bytes: bytes) -> dict:
    """Call Gemini Vision via google.genai SDK (new SDK, replaces google.generativeai)."""
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        return {"type": "error", "notes": "GEMINI_API_KEY not configured"}
    try:
        from google import genai as _genai
        from google.genai import types as _gtypes
        import re as _re
        client = _genai.Client(api_key=api_key)
        import PIL.Image, io
        img = PIL.Image.open(io.BytesIO(image_bytes))
        response = client.models.generate_content(
            model=_GEMINI_MODEL,
            contents=[img, _VISION_PROMPT],
            config=_gtypes.GenerateContentConfig(
                max_output_tokens=1024,
                temperature=0.05
            )
        )
        raw = response.text.strip()
        print(f"[VISION] Gemini raw: {raw[:300]}")
        clean = raw.strip()
        if clean.startswith("```"):
            clean = clean.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        try:
            return json.loads(clean)
        except json.JSONDecodeError:
            # Attempt to extract JSON object from partial/truncated response
            match = _re.search(r'\{[^{}]*"product_name"\s*:\s*"([^"]+)"[^{}]*\}', clean, _re.DOTALL)
            if match:
                # Try to reconstruct a minimal valid dict from regex groups
                pname_match = _re.search(r'"product_name"\s*:\s*"([^"]+)"', clean)
                brand_match = _re.search(r'"brand"\s*:\s*"([^"]*)"', clean)
                cat_match = _re.search(r'"category"\s*:\s*"([^"]*)"', clean)
                conf_match = _re.search(r'"confidence"\s*:\s*"([^"]*)"', clean)
                barcode_match = _re.search(r'"barcode_value"\s*:\s*"([^"]*)"', clean)
                return {
                    "type": "product",
                    "product_name": pname_match.group(1) if pname_match else clean[:80],
                    "barcode_value": barcode_match.group(1) if barcode_match else "",
                    "brand": brand_match.group(1) if brand_match else "",
                    "category": cat_match.group(1) if cat_match else "Electronics",
                    "confidence": conf_match.group(1) if conf_match else "Medium",
                    "notes": ""
                }
            return {
                "type": "product", "product_name": clean[:80], "barcode_value": "",
                "brand": "", "category": "Unknown", "confidence": "Low", "notes": ""
            }
    except Exception as e:
        print(f"[VISION] Gemini error: {e}")
        return {"type": "error", "notes": str(e)}


def download_telegram_photo(file_id: str) -> bytes | None:
    """Download highest-res Telegram photo by file_id. Returns raw bytes."""
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not bot_token:
        return None
    try:
        meta_url = f"https://api.telegram.org/bot{bot_token}/getFile?file_id={file_id}"
        meta = json.loads(urllib.request.urlopen(meta_url, timeout=8).read())
        file_path = meta["result"]["file_path"]
        img_url = f"https://api.telegram.org/file/bot{bot_token}/{file_path}"
        return urllib.request.urlopen(img_url, timeout=20).read()
    except Exception as e:
        print(f"[VISION] Photo download error: {e}")
        return None


def _search_odoo(keyword: str = "", barcode: str = "") -> list:
    """Search product.product by name keyword or barcode field."""
    try:
        odoo = _get_odoo()
        if barcode:
            domain = ["|", ["barcode", "=", barcode], ["default_code", "=", barcode]]
        else:
            domain = ["|", ["name", "ilike", keyword], ["default_code", "ilike", keyword]]
        return odoo.search_read(
            "product.product", domain,
            fields=["id", "name", "default_code", "barcode", "list_price", "qty_available"],
            limit=3
        ) or []
    except Exception as e:
        print(f"[VISION] Odoo search error: {e}")
        return []


def _product_table(products: list) -> str:
    if not products:
        return "_No matching product found in Odoo catalog._"
    rows = [
        "| # | Product | SKU | Qty | Price (VND) |",
        "|---|---------|-----|-----|-------------|"
    ]
    for i, p in enumerate(products, 1):
        sku = p.get("default_code") or p.get("barcode") or "N/A"
        rows.append(
            f"| {i} | {p.get('name', 'N/A')} | `{sku}` "
            f"| {p.get('qty_available', 0):.0f} | {p.get('list_price', 0):,.0f} |"
        )
    return "\n".join(rows)


def analyze_product_image(image_bytes: bytes) -> str:
    """
    Full pipeline: Gemini Vision -> Odoo lookup -> 3-section business response.
    Called by app.py when a user sends a photo to Telegram.
    """
    # 1. Vision analysis
    v = _call_gemini_vision(image_bytes)
    img_type = v.get("type", "unknown")
    product_name = v.get("product_name", "")
    barcode_val = v.get("barcode_value", "")
    brand = v.get("brand", "")
    category = v.get("category", "")
    confidence = v.get("confidence", "Low")
    notes = v.get("notes", "")

    if img_type in ("unknown", "error") or (not product_name and not barcode_val):
        return (
            "Could not identify a product in this image. "
            "Please send a clearer photo focusing on the product label or barcode."
        )

    # 2. Odoo lookup
    if barcode_val:
        products = _search_odoo(barcode=barcode_val)
    else:
        products = _search_odoo(keyword=product_name)
        if not products and brand:
            products = _search_odoo(keyword=brand)

    table = _product_table(products)
    icon = "📦" if img_type == "product" else "🔲"

    # 3. Format response
    if products:
        top = products[0]
        stock = top.get("qty_available", 0)
        price = top.get("list_price", 0)
        stock_str = f"{stock:.0f} units - {'In Stock' if stock > 0 else 'Out of Stock'}"
        conclusion = (
            f"{icon} Identified: **{product_name or top['name']}**"
            f"{' (' + brand + ')' if brand else ''}\n"
            f"Odoo Match: **{top['name']}** "
            f"(SKU: `{top.get('default_code') or 'N/A'}`)\n"
            f"Stock: **{stock_str}** | Price: **{price:,.0f} VND** | "
            f"Vision Confidence: {confidence}"
        )
        next_steps = (
            f"- `Create quotation for {top['name']} for customer [Name]`\n"
            f"- `Check stock for {top.get('default_code', top['name'])}`\n"
            f"- `Show all {category} products`"
        )
    else:
        conclusion = (
            f"{icon} Identified: **{product_name}** ({brand}) - {category}\n"
            f"Vision Confidence: {confidence}\n"
            f"No matching product found in Odoo. Notes: {notes}"
        )
        next_steps = (
            f"- Ask catalog manager to add **{product_name}** to Odoo\n"
            f"- `Search product {product_name}` for manual lookup"
        )

    return (
        f"### CONCLUSION\n{conclusion}\n\n"
        f"### ACTUAL DATA\n"
        f"Detected: {product_name or barcode_val} | Brand: {brand or 'N/A'} | "
        f"Category: {category or 'N/A'} | Barcode: `{barcode_val or 'N/A'}`\n\n"
        f"{table}\n\n"
        f"### NEXT STEPS\n{next_steps}"
    )


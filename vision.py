"""vision.py - SmartShop Computer Vision Module.

Identifies products / reads barcodes from Telegram photos using
DeepSeek V4 Vision (deepseek-flash via LiteLLM gateway), then looks up
Odoo catalog for stock & price data.
"""

import base64
import json
import os
import urllib.request

# Ensure .env is loaded
if os.path.exists(".env") and not os.getenv("DEEPSEEK_API_KEY"):
    with open(".env", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                k = k.strip()
                if k not in os.environ:
                    os.environ[k] = v.strip()

from odoo import OdooClient

# Lazy Odoo client - initialized on first search to avoid blocking at import time
_odoo_client = None


def _get_odoo() -> OdooClient:
    global _odoo_client
    if _odoo_client is None:
        _odoo_client = OdooClient()
    return _odoo_client


_VISION_PROMPT = (
    "You are a retail product recognition AI for a Singapore electronics store. "
    "Analyze the image and DO YOUR BEST to identify any product, even if the image is not perfect. "
    "Look for: product name text, brand logo, barcode, model number, packaging, or any visible label. "
    "Respond ONLY in this exact JSON format (no markdown, no explanation):\n"
    '{"type":"product","product_name":"<brand+model e.g. MacBook Pro 14 M3 Pro - use your best guess>",'
    '"barcode_value":"<barcode/QR string if visible else empty>","brand":"<brand name>",'
    '"category":"<Electronics/Peripherals/Accessories/Phone/Laptop/Mouse/Keyboard/Other>",'
    '"confidence":"<High/Medium/Low>","notes":"<color, model number, storage, any visible detail>"}\n'
    "IMPORTANT: Always make your best guess for product_name. "
    "Only set type to \"unknown\" if the image contains NO product at all (e.g., a person, landscape, document)."
)


def _call_deepseek_vision(image_bytes: bytes) -> dict:
    """Call DeepSeek V4 (deepseek-flash) via LiteLLM gateway with OpenAI format."""
    api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        return {"type": "error", "notes": "DEEPSEEK_API_KEY not configured"}
    base_url = os.getenv("DEEPSEEK_BASE_URL", "").strip()
    if not base_url or "api.deepseek.com" in base_url:
        base_url = "https://litellm-production-7402.up.railway.app/v1"
    model = os.getenv("DEEPSEEK_MODEL", "deepseek-flash")

    try:
        from openai import OpenAI
        import re as _re
        client = OpenAI(api_key=api_key, base_url=base_url)
        b64 = base64.b64encode(image_bytes).decode("utf-8")

        resp = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": _VISION_PROMPT},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
                    ]
                }
            ],
            max_tokens=800,
            temperature=0.05
        )
        raw = (resp.choices[0].message.content or "").strip()
        print(f"[VISION] (DeepSeek V4 - {model}) raw: {raw[:300]}")
        clean = raw
        if "```" in clean:
            clean = clean.split("```", 1)[-1].rsplit("```", 1)[0]
            if clean.lower().startswith("json"):
                clean = clean[4:].strip()
        try:
            return json.loads(clean)
        except json.JSONDecodeError:
            match = _re.search(r'\{[^{}]*"product_name"\s*:\s*"([^"]+)"[^{}]*\}', clean, _re.DOTALL)
            pname_match = _re.search(r'"product_name"\s*:\s*"([^"]+)"', clean)
            brand_match = _re.search(r'"brand"\s*:\s*"([^"]*)"', clean)
            cat_match = _re.search(r'"category"\s*:\s*"([^"]*)"', clean)
            conf_match = _re.search(r'"confidence"\s*:\s*"([^"]*)"', clean)
            barcode_match = _re.search(r'"(?:barcode_value|barcode_number)"\s*:\s*"([^"]*)"', clean)
            if pname_match:
                return {
                    "type": "product",
                    "product_name": pname_match.group(1),
                    "barcode_value": barcode_match.group(1) if barcode_match else "",
                    "brand": brand_match.group(1) if brand_match else "",
                    "category": cat_match.group(1) if cat_match else "Electronics",
                    "confidence": conf_match.group(1) if conf_match else "High",
                    "notes": ""
                }
            return {"type": "error", "notes": f"Could not parse: {clean[:100]}"}
    except Exception as e:
        print(f"[VISION] DeepSeek V4 error: {e}")
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
    """Search product.product by name keyword or barcode field with fuzzy token fallback."""
    try:
        odoo = _get_odoo()
        if barcode:
            domain = ["|", ["barcode", "=", barcode], ["default_code", "=", barcode]]
            res = odoo.search_read(
                "product.product", domain,
                fields=["id", "name", "default_code", "barcode", "list_price", "qty_available"],
                limit=3
            ) or []
            if res:
                return res

        if keyword:
            # 1. Direct ilike substring search
            domain = ["|", ["name", "ilike", keyword], ["default_code", "ilike", keyword]]
            res = odoo.search_read(
                "product.product", domain,
                fields=["id", "name", "default_code", "barcode", "list_price", "qty_available"],
                limit=3
            ) or []
            if res:
                return res

            # 2. Token overlap fallback across all saleable products
            all_prods = odoo.search_read(
                "product.product", [["sale_ok", "=", True]],
                fields=["id", "name", "default_code", "barcode", "list_price", "qty_available"],
                limit=100
            ) or []
            kw_tokens = set(keyword.lower().replace("-", " ").replace("_", " ").split())
            kw_versions = {t for t in kw_tokens if t.isdigit() and len(t) <= 2}
            scored = []
            for p in all_prods:
                p_name = (p.get("name") or "").lower()
                p_code = (p.get("default_code") or "").lower()
                cand_tokens = set(p_name.replace("-", " ").replace("_", " ").split())
                p_tokens = set((p_name + " " + p_code).replace("-", " ").replace("_", " ").split())
                cand_versions = {t for t in cand_tokens if t.isdigit() and len(t) <= 2}

                # Do not match if model/version digits conflict (e.g. 16 vs 15)
                if kw_versions and cand_versions and kw_versions != cand_versions:
                    continue

                overlap = len(kw_tokens & p_tokens)
                ratio = overlap / len(cand_tokens) if cand_tokens else 0
                if overlap >= 2 and ratio >= 0.5:
                    scored.append((overlap, p))
            if scored:
                scored.sort(key=lambda x: x[0], reverse=True)
                return [x[1] for x in scored[:3]]

        return []
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
    Full pipeline: DeepSeek V4 Vision -> Odoo lookup -> 3-section business response.
    Called by app.py when a user sends a photo to Telegram.
    """
    # 1. Vision analysis: DeepSeek V4 (deepseek-flash via LiteLLM gateway)
    v = _call_deepseek_vision(image_bytes)
    img_type = v.get("type", "unknown")
    product_name = v.get("product_name", "")
    barcode_val = v.get("barcode_value", "")
    brand = v.get("brand", "")
    category = v.get("category", "")
    confidence = v.get("confidence", "Low")
    notes = v.get("notes", "")

    if img_type == "error":
        return (
            f"Vision error: {notes[:100]}\n"
            "Please try again or send a different photo."
        )

    # Be lenient: if DeepSeek returned "unknown" but still extracted a product name, use it
    if img_type == "unknown" and product_name:
        img_type = "product"

    if not product_name and not barcode_val:
        return (
            "Could not identify any product in this photo.\n\n"
            "Tips:\n"
            "- Ensure the product name or barcode is clearly visible\n"
            "- Use good lighting, avoid glare\n"
            "- Try a closer shot of the product label or box\n"
            "- You can also type the product name directly (e.g. `Search MacBook Pro`)"
        )

    # 2. Odoo lookup: try barcode -> product name -> brand
    products = []
    if barcode_val:
        products = _search_odoo(barcode=barcode_val)
    if not products and product_name:
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
            f"AI Engine: **DeepSeek V4** (Confidence: {confidence})"
        )
        next_steps = (
            f"- `Create quotation for {top['name']} for customer [Name]`\n"
            f"- `Check stock for {top.get('default_code') or top.get('name')}`\n"
            f"- `Show all {category} products`"
        )
    else:
        conclusion = (
            f"{icon} Identified: **{product_name}** ({brand}) - {category}\n"
            f"AI Engine: **DeepSeek V4** (Confidence: {confidence})\n"
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


"""
Sigma AI Assistant — Full Stack
/       → Chatbot (Claude-powered)
/admin  → Admin panel (products, dealers, config, conversations, images, offers)

FIXES in this version:
1. Images correctly injected into chatbot product cards from static/images/
2. Dealer data loaded from dealers.xlsx (chn/del/klr/klt/bng sheets) with full CRUD
3. Language: default English; if user explicitly asks in another language → reply in that
"""

import os, json, re, uuid, shutil
from datetime import datetime
from flask import (Flask, render_template, request, jsonify,
                   session, send_from_directory)
import openpyxl
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "sigma-assistant-2025-secret")

# ── PATHS ────────────────────────────────────────────────
BASE_DIR      = os.path.dirname(__file__)
XLSX_PATH     = os.path.join(BASE_DIR, "sigma_products.xlsx")
DEALER_PATH   = os.path.join(BASE_DIR, "dealers.xlsx")
CONFIG_PATH   = os.path.join(BASE_DIR, "data", "config.json")
CONV_PATH     = os.path.join(BASE_DIR, "data", "conversations.json")
IMAGES_DIR    = os.path.join(BASE_DIR, "static", "images")
PRICES_PATH   = os.path.join(BASE_DIR, "data", "prices.json")
SERVICE_CENTER_PATH = os.path.join(BASE_DIR, "data", "service-center.json")
WHATSAPP_CONFIG_PATH   = os.path.join(BASE_DIR, "data", "whatsapp_config.json")
WHATSAPP_SESSIONS_PATH = os.path.join(BASE_DIR, "data", "whatsapp_sessions.json")

for d in [os.path.join(BASE_DIR, "data"), IMAGES_DIR]:
    os.makedirs(d, exist_ok=True)

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "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")
CLAUDE_MODEL      = "claude-sonnet-4-20250514"
ALLOWED_EXT       = {"png", "jpg", "jpeg", "webp", "gif"}

# ── DEALER SHEET MAPPING ─────────────────────────────────
DEALER_SHEET_MAP = {
    "chn": "Chennai & South",
    "del": "Delhi & North",
    "klr": "Kerala",
    "klt": "Kolkata & East",
    "bng": "Bangalore & West",
    "mum": "Mumbai",
    "tel": "Telangana & Andra"
}
DEALER_HEADERS = [
    "customer_name", "company_parent_id", "address_one", "address_two",
    "address_three", "address_four", "city", "state", "pincode",
    "gst_no", "pan_no", "dealer_code", "sales person"
]

# ══════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════
DEFAULT_CONFIG = {
    "language": "English",
    "response_length": "medium",
    "response_style": "professional",
    "show_comparison": True,
    "show_price_table": True,
    "show_dealer_section": True,
    "show_amazon_links": True,
    "max_products_shown": 6,
    "currency": "INR",
    "usd_to_inr_rate": 84,
    "mandatory_message": "",
    "loyalty_program": "",
    "offer_banner": "",
    "site_url": "https://sigmaindia.in/",
    "brand_name": "Sigma AI Assistant",
    "welcome_message": "Welcome! I'm your dedicated Sigma product expert.",
    "bot_personality": "professional",
    "updated_at": "",
    # User data collection
    "collect_user_data": False,
    "user_data_message_gap": 3,
    "collect_user_prompt": "May I have your name and phone number so our team can assist you better?",
}

def load_config():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH) as f:
                cfg = json.load(f)
            for k, v in DEFAULT_CONFIG.items():
                cfg.setdefault(k, v)
            return cfg
        except:
            pass
    return dict(DEFAULT_CONFIG)

def save_config(cfg):
    cfg["updated_at"] = datetime.now().isoformat()
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)

# ══════════════════════════════════════════════════════════
# WHATSAPP CONFIG + SESSIONS
# ══════════════════════════════════════════════════════════
DEFAULT_WHATSAPP_CONFIG = {
    "enabled": True,
    "brand_name": "Sigma AI Assistant",
    "welcome_message": "Welcome, {name}. I am the Sigma AI Assistant, your guide for everything related to Sigma in India.",
    "footer_text": "sigmaindia.in",
    "business_hours": "Monday to Saturday, 9 AM to 6 PM IST",
    "support_email": "info@sigmaindia.in",
    "updated_at": "",
}

def load_whatsapp_config():
    if os.path.exists(WHATSAPP_CONFIG_PATH):
        try:
            with open(WHATSAPP_CONFIG_PATH) as f:
                cfg = json.load(f)
            for k, v in DEFAULT_WHATSAPP_CONFIG.items():
                cfg.setdefault(k, v)
            return cfg
        except:
            pass
    return dict(DEFAULT_WHATSAPP_CONFIG)

def save_whatsapp_config(cfg):
    cfg["updated_at"] = datetime.now().isoformat()
    os.makedirs(os.path.dirname(WHATSAPP_CONFIG_PATH), exist_ok=True)
    with open(WHATSAPP_CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)

def load_whatsapp_sessions() -> list:
    """Load the WhatsApp bot's session log (written by sigma_whatsapp_bot.py)."""
    if os.path.exists(WHATSAPP_SESSIONS_PATH):
        try:
            with open(WHATSAPP_SESSIONS_PATH) as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except Exception as e:
            print(f"[WHATSAPP SESSIONS ERROR] {e}")
    return []

def save_whatsapp_sessions(data: list):
    os.makedirs(os.path.dirname(WHATSAPP_SESSIONS_PATH), exist_ok=True)
    with open(WHATSAPP_SESSIONS_PATH, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# ══════════════════════════════════════════════════════════
# CONVERSATIONS
# ══════════════════════════════════════════════════════════
def load_conversations():
    if os.path.exists(CONV_PATH):
        try:
            with open(CONV_PATH) as f:
                return json.load(f)
        except:
            pass
    return []

def save_conversation(session_id, messages):
    convs = load_conversations()
    for c in convs:
        if c["session_id"] == session_id:
            c["messages"]      = messages
            c["updated_at"]    = datetime.now().isoformat()
            c["message_count"] = len([m for m in messages if m["role"] == "user"])
            break
    else:
        convs.append({
            "session_id":    session_id,
            "started_at":    datetime.now().isoformat(),
            "updated_at":    datetime.now().isoformat(),
            "message_count": len([m for m in messages if m["role"] == "user"]),
            "messages":      messages
        })
    convs = sorted(convs, key=lambda x: x["updated_at"], reverse=True)[:500]
    with open(CONV_PATH, "w") as f:
        json.dump(convs, f, indent=2)

# ══════════════════════════════════════════════════════════
# PRICE HELPERS
# ══════════════════════════════════════════════════════════
PRICE_USD = {
    "14mm F1.8 DG HSM": 1299, "14mm F1.4 DG DN": 1599,
    "15mm F1.4 DG DN Diagonal Fisheye": 1099, "20mm F1.4 DG DN": 899,
    "24mm F1.4 DG DN": 849, "28mm F1.4 DG HSM": 799,
    "35mm F1.2 DG DN II": 1599, "35mm F1.4 DG DN": 899, "35mm F1.4 DG II": 799,
    "50mm F1.2 DG DN": 1299, "50mm F1.4 DG DN": 949, "70mm F2.8 DG MACRO": 599,
    "85mm F1.4 DG DN": 999, "105mm F2.8 DG DN MACRO": 849, "135mm F1.4 DG": 1399,
    "14-24mm F2.8 DG DN": 1299, "14-24mm F2.8 DG HSM": 1299, "17-40mm F1.8 DC": 999,
    "24-70mm F2.8 DG OS HSM": 1099, "24-70mm F2.8 DG DN II": 1099,
    "24-105mm F4 DG OS HSM": 899, "28-45mm F1.8 DG DN": 1499,
    "28-105mm F2.8 DG DN": 1699, "50-100mm F1.8 DC HSM": 1099,
    "17mm F4 DG": 449, "20mm F2 DG": 549, "24mm F2 DG": 499, "24mm F3.5 DG": 449,
    "35mm F2 DG": 499, "45mm F2.8 DG": 399, "50mm F2 DG": 549,
    "65mm F2 DG": 599, "90mm F2.8 DG": 499,
    "12mm F1.4 DC": 599, "15mm F1.4 DC": 649, "16mm F1.4 DC DN": 449,
    "23mm F1.4 DC DN": 349, "30mm F1.4 DC DN": 299, "56mm F1.4 DC DN": 329,
    "10-18mm F2.8 DC DN": 549, "16-28mm F2.8 DG DN": 799,
    "18-50mm F2.8 DC DN": 499, "16-300mm F3.5-6.7 DC OS": 699,
    "20-200mm F3.5-6.3 DG": 699, "28-70mm F2.8 DG DN": 699,
    "100-400mm F5-6.3 DG DN OS": 1099, "200mm F2 DG OS": 2999,
    "500mm F5.6 DG DN OS": 2199, "60-600mm F4.5-6.3 DG DN OS": 2199,
    "60-600mm F4.5-6.3 DG OS HSM": 1999, "70-200mm F2.8 DG DN OS": 1499,
    "150-600mm F5-6.3 DG DN OS": 1699, "300-600mm F4 DG OS": 3999,
    "Sigma BF": 1999, "Sigma fp L": 2499, "Sigma fp": 1499,
    "USB DOCK UD-11": 59, "USB DOCK UD-01": 59,
    "TELE CONVERTER TC-1401 / TC-2001": 299, "TELE CONVERTER TC-1411 / TC-2011": 299,
    "WR CIRCULAR PL FILTER": 79, "WR UV FILTER": 59, "PROTECTOR": 49,
    "WR PROTECTOR": 59, "WR CERAMIC PROTECTOR": 99,
    "MOUNT CONVERTER MC-31": 249, "MOUNT CONVERTER MC-21": 249,
    "MOUNT CONVERTER MC-11": 199, "FLASH USB DOCK FD-11": 49,
    "ELECTRONIC VIEWFINDER EVF-11": 399, "ELECTRONIC FLASH EF-630": 299,
    "ELECTRONIC FLASH MACRO EM-140 DG": 249,
}

def fmt_inr(usd, rate=None):
    r   = rate or load_config().get("usd_to_inr_rate", 84)
    inr = round(usd * r / 500) * 500
    return f"₹{inr/100000:.1f} Lakh" if inr >= 100000 else f"₹{inr:,}"

def fmt_inr_range(usd, rate=None):
    r  = rate or load_config().get("usd_to_inr_rate", 84)
    lo = round(int(usd * r * 0.96) / 500) * 500
    hi = round(int(usd * r * 1.06) / 500) * 500
    f  = lambda v: f"₹{v/100000:.1f} Lakh" if v >= 100000 else f"₹{v:,}"
    return f"{f(lo)} – {f(hi)}"

# ══════════════════════════════════════════════════════════
# IMAGE HELPERS  ← FIX: consistent ID generation
# ══════════════════════════════════════════════════════════
def _product_id(name):
    """Generate stable filesystem-safe ID from product name."""
    pid = re.sub(r"[^a-z0-9]+", "_", name.lower())
    return pid.strip("_")

def _find_image(pid):
    """Return URL path to product image if it exists, else empty string."""
    for ext in ["jpg", "jpeg", "png", "webp", "gif"]:
        fpath = os.path.join(IMAGES_DIR, f"{pid}.{ext}")
        if os.path.exists(fpath):
            return f"/static/images/{pid}.{ext}"
    return ""

# ══════════════════════════════════════════════════════════
# PRODUCT DATA (Excel CRUD)
# ══════════════════════════════════════════════════════════
SHEET_MAP = {
    "Still Lenses": "still_lenses",
    "Cine Lenses":  "cine_lenses",
    "Cameras":      "cameras",
    "Accessories":  "accessories",
}

# ══════════════════════════════════════════════════════════
# PRICE JSON STORE  — editable from admin panel
# ══════════════════════════════════════════════════════════
def load_prices() -> dict:
    """Load price overrides from data/prices.json safely."""
    
    # Create file if missing
    if not os.path.exists(PRICES_PATH):
        with open(PRICES_PATH, "w") as f:
            json.dump({}, f, indent=2)
        return {}

    try:
        with open(PRICES_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Ensure dictionary
        if isinstance(data, dict):
            return data

        print("[PRICES] Invalid format in prices.json — resetting")
        return {}

    except Exception as e:
        print(f"[PRICES ERROR] {e}")

        # Reset broken file
        with open(PRICES_PATH, "w", encoding="utf-8") as f:
            json.dump({}, f, indent=2)

        return {}
    
# ══════════════════════════════════════════════════════════
# SERVICE CENTERS
# ══════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════
# SERVICE CENTER HELPERS
# ══════════════════════════════════════════════════════════

def load_service_centers():

    if not os.path.exists(SERVICE_CENTER_PATH):
        return []

    try:
        with open(SERVICE_CENTER_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        return data if isinstance(data, list) else []

    except Exception as e:
        print("[SERVICE CENTER ERROR]", e)
        return []


def search_service_centers(query, limit=10):

    q = query.lower().strip()

    centers = load_service_centers()

    scored = []

    for c in centers:

        blob = " ".join([
            str(c.get("name","")),
            str(c.get("city","")),
            str(c.get("state","")),
            str(c.get("address",""))
        ]).lower()

        score = 0

        for word in q.split():

            if len(word) < 3:
                continue

            if word in blob:
                score += 3

        if score > 0:
            scored.append((score, c))

    scored.sort(key=lambda x: -x[0])

    return [x[1] for x in scored[:limit]]


def format_service_center_for_chat(c):

    return {
        "name": c.get("name",""),
        "type": "Authorised Sigma Service Center",
        "location": f"{c.get('city','')}, {c.get('state','')}",
        "address": c.get("address",""),
        "phone": c.get("phone",""),
        "email": c.get("email",""),
        "url": "https://sigmaindia.in/service-support/"
    }
 
def save_prices(prices: dict):
    with open(PRICES_PATH, "w") as f:
        json.dump(prices, f, indent=2)
 
# def get_price_inr(name: str, fallback_usd: int = 0) -> str:
#     """Return INR price: check prices.json first, then fall back to PRICE_USD."""
#     overrides = load_prices()
#     if name in overrides:
#         return overrides[name].get("price_inr", "Contact dealer")
#     if fallback_usd:
#         return fmt_inr(fallback_usd)
#     return "Contact dealer"
 
# def get_price_range_inr(name: str, fallback_usd: int = 0) -> str:
#     overrides = load_prices()
#     if name in overrides:
#         return overrides[name].get("price_range_inr", "")
#     if fallback_usd:
#         return fmt_inr_range(fallback_usd)
#     return ""


# ─────────────────────────────────────────────────────────
# PATCH: Replace ONLY the existing normalize_name(),
# find_best_price_key(), get_price_inr(),
# and get_price_range_inr() functions with this code.
# This patch is backward-compatible and does not affect
# any other logic in your application.
# ─────────────────────────────────────────────────────────

def normalize_name(name: str) -> str:
    """
    Normalize product names so price lookup works even when:
    - Different dash characters are used (–, —, −)
    - 'Sigma' prefix is present
    - Extra spaces exist
    - Case differs
    """
    if not name:
        return ""

    name = str(name).strip().lower()

    # Normalize all Unicode dash variants to ASCII hyphen
    name = (
        name.replace("\u2013", "-")  # en dash
            .replace("\u2014", "-")  # em dash
            .replace("\u2212", "-")  # minus sign
            .replace("-", "-")       # non-breaking hyphen
            .replace("‒", "-")       # figure dash
    )

    # Remove common prefixes
    for prefix in ("sigma ", "the sigma "):
        if name.startswith(prefix):
            name = name[len(prefix):]

    # Normalize whitespace
    name = re.sub(r"\s+", " ", name).strip()

    return name


def find_best_price_key(name: str):
    """
    Return the best matching key from:
    1. prices.json overrides
    2. PRICE_USD dictionary

    Supports:
    - Exact normalized match
    - Partial normalized match
    """
    if not name:
        return None

    target = normalize_name(name)
    overrides = load_prices()

    # Search overrides first, then PRICE_USD
    all_keys = list(overrides.keys()) + list(PRICE_USD.keys())

    # 1. Exact normalized match
    for key in all_keys:
        if normalize_name(key) == target:
            return key

    # 2. Partial match fallback
    for key in all_keys:
        nk = normalize_name(key)
        if target in nk or nk in target:
            return key

    return None


def get_price_inr(name: str, fallback_usd: int = 0) -> str:
    """
    Return INR price string.

    Priority:
    1. prices.json override
    2. PRICE_USD converted to INR
    3. fallback_usd converted to INR
    4. Contact dealer
    """
    overrides = load_prices()
    key = find_best_price_key(name)

    # prices.json override
    if key and key in overrides:
        price = overrides[key].get("price_inr")
        if price:
            return price

    # PRICE_USD fallback
    if key and key in PRICE_USD:
        return fmt_inr(PRICE_USD[key])

    # Explicit fallback USD
    if fallback_usd:
        return fmt_inr(fallback_usd)

    return "Contact dealer"


def get_price_range_inr(name: str, fallback_usd: int = 0) -> str:
    """
    Return INR price range string.

    Priority:
    1. prices.json override
    2. PRICE_USD converted to range
    3. fallback_usd converted to range
    4. empty string
    """
    overrides = load_prices()
    key = find_best_price_key(name)

    # prices.json override
    if key and key in overrides:
        price_range = overrides[key].get("price_range_inr")
        if price_range:
            return price_range

    # PRICE_USD fallback
    if key and key in PRICE_USD:
        return fmt_inr_range(PRICE_USD[key])

    # Explicit fallback USD
    if fallback_usd:
        return fmt_inr_range(fallback_usd)

    return ""


def load_products():
    products = {k: [] for k in SHEET_MAP.values()}
    try:
        wb = openpyxl.load_workbook(XLSX_PATH, read_only=True, data_only=True)
        for sheet_name, key in SHEET_MAP.items():
            if sheet_name not in wb.sheetnames:
                continue
            ws   = wb[sheet_name]
            rows = list(ws.iter_rows(values_only=True))
            if not rows:
                continue
            headers = [str(h).strip() if h else "" for h in rows[0]]
            for row in rows[1:]:
                if not any(row):
                    continue
                item = {
                    headers[i]: (str(row[i]).strip() if row[i] is not None else "")
                    for i in range(min(len(headers), len(row)))
                }
                name = item.get("Product Name", "")
                if not name or name == "None":
                    continue
                pid = _product_id(name)
                item["_category"]         = key
                item["_display_category"] = sheet_name
                item["_id"]               = pid
                # usd = PRICE_USD.get(name, 0)
                # item["_price_inr"]        = fmt_inr(usd) if usd else "Contact dealer"
                # item["_price_range_inr"]  = fmt_inr_range(usd) if usd else ""
                # item["_price_usd"]        = usd

                usd = PRICE_USD.get(name, 0)
                item["_price_inr"]        = get_price_inr(name, usd)
                item["_price_range_inr"]  = get_price_range_inr(name, usd)
                item["_price_usd"]        = usd
                # ← KEY FIX: always re-check image at load time
                item["_image"]            = _find_image(pid)
                products[key].append(item)
        wb.close()
    except Exception as e:
        print(f"[XLSX ERROR] {e}")
    return products

def get_all_products():
    p = load_products()
    return (p["still_lenses"] + p["cine_lenses"] +
            p["cameras"] + p["accessories"])

def save_product_to_xlsx(sheet_name, product_name, updated_fields):
    try:
        wb   = openpyxl.load_workbook(XLSX_PATH)
        if sheet_name not in wb.sheetnames:
            return False, "Sheet not found"
        ws   = wb[sheet_name]
        rows = list(ws.iter_rows())
        hdrs = [c.value for c in rows[0]]
        for row in rows[1:]:
            if row[0].value == product_name:
                for ci, h in enumerate(hdrs):
                    if h and h in updated_fields:
                        ws.cell(row=row[0].row, column=ci + 1, value=updated_fields[h])
                break
        wb.save(XLSX_PATH)
        return True, "Saved"
    except Exception as e:
        return False, str(e)

def delete_product_from_xlsx(sheet_name, product_name):
    try:
        wb   = openpyxl.load_workbook(XLSX_PATH)
        if sheet_name not in wb.sheetnames:
            return False, "Sheet not found"
        ws   = wb[sheet_name]
        rows = list(ws.iter_rows())
        for row in rows[1:]:
            if row[0].value == product_name:
                ws.delete_rows(row[0].row)
                break
        wb.save(XLSX_PATH)
        return True, "Deleted"
    except Exception as e:
        return False, str(e)

def add_product_to_xlsx(sheet_name, fields):
    try:
        wb   = openpyxl.load_workbook(XLSX_PATH)
        if sheet_name not in wb.sheetnames:
            return False, "Sheet not found"
        ws   = wb[sheet_name]
        hdrs = [c.value for c in list(ws.iter_rows())[0]]
        ws.append([fields.get(h, "") for h in hdrs])
        wb.save(XLSX_PATH)
        return True, "Added"
    except Exception as e:
        return False, str(e)

# ══════════════════════════════════════════════════════════
# DEALER DATA (dealers.xlsx CRUD)
# ══════════════════════════════════════════════════════════
def load_dealers(sheet_key=None):
    """Load dealers from dealers.xlsx. Returns dict {sheet_key: [rows]}."""
    result = {}
    if not os.path.exists(DEALER_PATH):
        return result
    try:
        wb = openpyxl.load_workbook(DEALER_PATH, read_only=True, data_only=True)
        sheets = [sheet_key] if sheet_key else list(DEALER_SHEET_MAP.keys())
        for sh in sheets:
            if sh not in wb.sheetnames:
                continue
            ws   = wb[sh]
            rows = list(ws.iter_rows(values_only=True))
            if not rows:
                continue
            hdrs = [str(h).strip() if h else "" for h in rows[0]]
            dealers = []
            for row in rows[1:]:
                if not any(row):
                    continue
                d = {hdrs[i]: (str(row[i]).strip() if row[i] is not None else "")
                     for i in range(min(len(hdrs), len(row)))}
                name = d.get("customer_name", "")
                if name and name != "None":
                    d["_sheet"]      = sh
                    d["_region"]     = DEALER_SHEET_MAP.get(sh, sh)
                    dealers.append(d)
            result[sh] = dealers
        wb.close()
    except Exception as e:
        print(f"[DEALER XLSX ERROR] {e}")
    return result

def get_all_dealers_flat():
    """Return flat list of all dealers."""
    dealers = []
    for sh, rows in load_dealers().items():
        dealers.extend(rows)
    return dealers
def search_dealers_by_query(query_text, limit=12):
    """
    Smart dealer search from Excel data by city, region, name, or state.
    Returns matched dealers with full address details.
    """
    q = query_text.lower().strip()
    all_dealers = get_all_dealers_flat()
    
    # Region keyword → sheet key mapping
    REGION_KEYWORDS = {
        "chn": ["chennai","tamil","madras","coimbatore","madurai","trichy","vellore","pondicherry",
                "pondycherry","salem","erode","tiruchirappalli","tirunelveli","thanjavur",
                "nellore","vijayawada","visakhapatnam","vizag","hyderabad","telangana","andhra"],
        "del": ["delhi","north","gurgaon","noida","faridabad","ghaziabad","chandigarh","lucknow",
                "kanpur","agra","jaipur","rajasthan","uttar pradesh","haryana","punjab",
                "himachal","uttarakhand","jammu","kashmir","mp","madhya pradesh","bhopal",
                "indore","ratlam","nagpur","chhattisgarh","raipur"],
        "klr": ["kerala","trivandrum","thiruvananthapuram","kochi","cochin","ernakulam",
                "thrissur","kozhikode","calicut","malappuram","kannur","palakkad","kollam"],
        "klt": ["kolkata","west bengal","bengal","assam","guwahati","bhubaneswar","odisha",
                "orissa","jharkhand","ranchi","patna","bihar","northeast","meghalaya",
                "manipur","tripura","sikkim","mizoram","nagaland","arunachal"],
        "bng": ["bangalore","bengaluru","karnataka","mysore","mysuru","hubli","mangalore",
                "pune","maharashtra","mumbai","thane","nashik","aurangabad","gujarat",
                "ahmedabad","surat","vadodara","goa","rajkot"],
    }
    
    # Determine which region(s) to search
    target_sheets = []
    for sh, keywords in REGION_KEYWORDS.items():
        if any(k in q for k in keywords):
            target_sheets.append(sh)
    
    # If no region detected, search all
    if not target_sheets:
        target_sheets = list(DEALER_SHEET_MAP.keys())
    
    scored = []
    for d in all_dealers:
        if d.get("_sheet") not in target_sheets:
            continue
        city     = (d.get("city") or "").lower()
        name     = (d.get("customer_name") or "").lower()
        addr_all = " ".join([
            str(d.get("address_one") or ""),
            str(d.get("address_two") or ""),
            str(d.get("address_three") or ""),
            str(d.get("address_four") or ""),
        ]).lower()
        
        score = 0
        # Score city match highest
        for word in q.split():
            if len(word) < 3:
                continue
            if word in city:
                score += 5
            elif word in name:
                score += 3
            elif word in addr_all:
                score += 1
        
        # Boost if dealer sheet region matches
        if d.get("_sheet") in target_sheets:
            score += 2
            
        if score > 0:
            scored.append((score, d))
    
    scored.sort(key=lambda x: (-x[0], x[1].get("customer_name", "")))
    return [d for _, d in scored[:limit]]


def format_dealer_for_chat(d):
    """Format a dealer row as a chat-friendly dict."""
    addr_parts = [
        d.get("address_one",""), d.get("address_two",""),
        d.get("address_three",""), d.get("address_four",""),
    ]
    address = ", ".join(p.strip() for p in addr_parts if p and str(p).strip() and str(p).strip() != "None")
    city    = (d.get("city") or "").strip()
    pincode = str(d.get("pincode") or "").strip()
    if pincode and pincode != "None": city = f"{city} - {pincode}"
    return {
        "name":        d.get("customer_name",""),
        "type":        "Authorised Sigma Dealer",
        "location":    f"{city}, {d.get('_region','')}",
        "address":     address,
        "dealer_code": d.get("dealer_code",""),
        "sales_person":d.get("sales person",""),
        "url":         "https://sigmaindia.in/dealer-network/",
    }



def save_dealer_to_xlsx(sheet_key, dealer_code, updated_fields):
    """Update a dealer row in dealers.xlsx by dealer_code."""
    try:
        wb = openpyxl.load_workbook(DEALER_PATH)
        if sheet_key not in wb.sheetnames:
            return False, "Sheet not found"
        ws   = wb[sheet_key]
        rows = list(ws.iter_rows())
        hdrs = [c.value for c in rows[0]]
        code_col = hdrs.index("dealer_code") if "dealer_code" in hdrs else -1
        for row in rows[1:]:
            cell_val = str(row[code_col].value).strip() if code_col >= 0 and row[code_col].value else ""
            if cell_val == dealer_code:
                for ci, h in enumerate(hdrs):
                    if h and h in updated_fields:
                        ws.cell(row=row[0].row, column=ci + 1, value=updated_fields[h])
                break
        wb.save(DEALER_PATH)
        return True, "Saved"
    except Exception as e:
        return False, str(e)

def delete_dealer_from_xlsx(sheet_key, dealer_code):
    """Delete a dealer row from dealers.xlsx by dealer_code."""
    try:
        wb = openpyxl.load_workbook(DEALER_PATH)
        if sheet_key not in wb.sheetnames:
            return False, "Sheet not found"
        ws   = wb[sheet_key]
        rows = list(ws.iter_rows())
        hdrs = [c.value for c in rows[0]]
        code_col = hdrs.index("dealer_code") if "dealer_code" in hdrs else -1
        for row in rows[1:]:
            cell_val = str(row[code_col].value).strip() if code_col >= 0 and row[code_col].value else ""
            if cell_val == dealer_code:
                ws.delete_rows(row[0].row)
                break
        wb.save(DEALER_PATH)
        return True, "Deleted"
    except Exception as e:
        return False, str(e)

def add_dealer_to_xlsx(sheet_key, fields):
    """Append a new dealer row to dealers.xlsx."""
    try:
        wb = openpyxl.load_workbook(DEALER_PATH)
        if sheet_key not in wb.sheetnames:
            return False, "Sheet not found"
        ws   = wb[sheet_key]
        hdrs = [c.value for c in list(ws.iter_rows())[0]]
        ws.append([fields.get(h, "") for h in hdrs])
        wb.save(DEALER_PATH)
        return True, "Added"
    except Exception as e:
        return False, str(e)

# ══════════════════════════════════════════════════════════
# SEARCH
# ══════════════════════════════════════════════════════════
def search_products(query, limit=8):
    keywords = [k for k in re.split(r"[\s,/]+", query.lower()) if len(k) > 2]
    scored   = []
    for p in get_all_products():
        blob  = " ".join(str(v) for v in p.values()).lower()
        score = sum(
            3 if k in (p.get("Product Name", "") or "").lower() else
            2 if k in (p.get("Key Features", "") or "").lower() else
            1 if k in blob else 0
            for k in keywords
        )
        if score:
            scored.append((score, p))
    scored.sort(key=lambda x: -x[0])
    return [p for _, p in scored[:limit]]

# ══════════════════════════════════════════════════════════
# LANGUAGE DETECTION
# ══════════════════════════════════════════════════════════
LANGUAGE_TRIGGERS = {
    "hindi":     ["hindi", "हिंदी", "हिन्दी", "mein baat karo", "hindi me"],
    "tamil":     ["tamil", "தமிழ்"],
    "telugu":    ["telugu", "తెలుగు"],
    "kannada":   ["kannada", "ಕನ್ನಡ"],
    "malayalam": ["malayalam", "മലയാളം"],
    "marathi":   ["marathi", "मराठी"],
    "bengali":   ["bengali", "বাংলা"],
    "gujarati":  ["gujarati", "ગુજરાતી"],
    "punjabi":   ["punjabi", "ਪੰਜਾਬੀ"],
    "english":   ["english", "in english", "reply in english"],
}

def detect_language_request(message):
    """
    If user explicitly asks to respond in a specific language, return that language.
    Otherwise return None (use default English).
    """
    msg_lower = message.lower()
    for lang, triggers in LANGUAGE_TRIGGERS.items():
        for t in triggers:
            if t in msg_lower:
                return lang.capitalize()
    return None

# ══════════════════════════════════════════════════════════
# SYSTEM PROMPT
# ══════════════════════════════════════════════════════════
def build_system_prompt(detected_language=None):
    cfg    = load_config()
    all_p  = get_all_products()
    cat_lines = [
        f"- [{p.get('_display_category','')}] {p.get('Product Name','')} | "
        f"Line:{p.get('Product Line', p.get('Category',''))} | "
        f"{p.get('Focal Length','')} {p.get('Max Aperture', p.get('T-Stop',''))} | "
        f"Mounts:{p.get('Available Mounts', p.get('Compatibility',''))} | "
        f"Price:{p.get('_price_inr','')} | "
        f"{p.get('Key Features','')[:70]}"
        for p in all_p
    ]

    # Language instruction:
    # If user explicitly requested a language this turn → use it.
    # Otherwise default to English regardless of config language setting.
    if detected_language:
        lang_inst = (
            f"The user has explicitly requested to communicate in {detected_language}. "
            f"You MUST respond entirely in {detected_language} for this and subsequent messages "
            f"unless the user asks to switch again."
        )
    else:
        lang_inst = (
            "Always respond in English by default. "
            "ONLY switch language if the user explicitly asks you to respond in a different language. "
            "Do not assume language from the user's name or location."
        )

    length_map = {
        "short":    "Be very concise — 1-2 sentences after products.",
        "medium":   "Give 2-4 sentence explanations.",
        "detailed": "Be thorough and technically detailed.",
    }
    style_map = {
        "professional": "Use professional, precise language.",
        "friendly":     "Use warm, friendly conversational tone.",
        "technical":    "Use highly technical language with full spec details.",
    }

    mandatory  = cfg.get("mandatory_message", "").strip()
    loyalty    = cfg.get("loyalty_program", "").strip()
    site_url   = cfg.get("site_url", "https://sigmaindia.in/")
    brand      = cfg.get("brand_name", "Sigma AI Assistant")
    max_p      = cfg.get("max_products_shown", 6)
    show_amz   = cfg.get("show_amazon_links", True)
    show_price = cfg.get("show_price_table", True)
    show_deal  = cfg.get("show_dealer_section", True)
    show_comp  = cfg.get("show_comparison", True)

    # Build city index for prompt context
    all_dealers_flat = get_all_dealers_flat()
    city_map = {}
    for d in all_dealers_flat:
        city = (d.get("city") or "").strip().title()
        region = d.get("_region", "")
        if city and city != "None":
            city_map.setdefault(city, {"region": region, "count": 0})
            city_map[city]["count"] += 1
    city_index = [f"  {city} ({info['region']}): {info['count']} dealers"
                  for city, info in sorted(city_map.items())[:40]]

    amz_rule   = '' if not show_amz else ''
    comp_rule  = 'Show product comparisons when helpful.' if show_comp else 'Do NOT compare products.'
    mand_line  = f'MANDATORY — append to every response: "{mandatory}"' if mandatory else ''
    loyal_line = f'LOYALTY PROGRAM (mention when relevant): {loyalty}' if loyalty else ''
    price_inst = 'When user asks about pricing, include ```json_prices``` with Sigma India, Amazon India, Flipkart.' if show_price else 'Do NOT include price tables.'
    dealer_inst= 'When user asks about dealers, ALWAYS output ```json_dealers``` block with _meta + real dealer rows.' if show_deal else 'Do NOT include dealer sections.'
    amz_inst   = '' if show_amz else 'Do NOT include Amazon links in product cards.'

    return (
        f"You are {brand} — expert AI product guide for Sigma ({site_url}).\n"
        f"{lang_inst}\n"
        f"{length_map.get(cfg.get('response_length','medium'),'')} "
        f"{style_map.get(cfg.get('response_style','professional'),'')}\n"
        f"Brand voice: \"Pursuit of Perfection.\"\n\n"
        f"RULES:\n"
        f"- ALL prices in INR. Never mention USD or sigma-global.com.\n"
        f"- Product links to {site_url}\n"
        f"- Amazon links to amazon.in only\n"
        f"- Max {max_p} products per response\n"
        f"- {comp_rule}\n"
        f"{'- ' + mand_line + chr(10) if mand_line else ''}"
        f"{'- ' + loyal_line + chr(10) if loyal_line else ''}"
        f"\nPRODUCT CATALOGUE ({len(all_p)} products):\n"
        + chr(10).join(cat_lines) +
        f"\n\nAUTHORISED DEALER DATABASE ({len(all_dealers_flat)} dealers across India):\n"
        f"Regions: Chennai & South | Delhi & North | Kerala | Kolkata & East | Bangalore & West\n"
        f"Cities available:\n"
        + chr(10).join(city_index) +
        f"\n\nDEALER QUERY RULE: When user asks about dealers in any city/region:\n"
        f"- Output a json_dealers block with _meta object first (query_city + query_region), then up to 8 dealer entries\n"
        f"- The backend will REPLACE your dealer entries with REAL data from our Excel database\n"
        f"- So just output the _meta with the city/region detected from user query\n"
        f"- Always be helpful about which cities we have dealers in\n"
        f"\nFORMAT — product recommendations:\n"
        f"```json_products\n"
        f'[{{"name":"...","line":"...","category":"...","focal_length":"...","aperture":"...",'
        f'"mounts":"...","key_features":"...","url":"{site_url}",'
        f'"amazon_in":"https://www.amazon.in/s?k=Sigma+name",'
        f'"price_inr":"INR X","price_range_inr":"INR X-Y","reason":"why"}}]\n'
        f"```\n"
        f"Then write explanation.\n\n"
        f"{price_inst}\n"
        f"{dealer_inst}\n"
        f"{amz_inst}\n"
        f"\nPRICE FORMAT:\n"
        f"```json_prices\n"
        f'[{{"platform":"Sigma India","price":"INR X","url":"{site_url}","status":"Authorised"}},'
        f'{{"platform":"Amazon India","price":"INR X","url":"https://www.amazon.in/s?k=sigma","status":"Check listing"}},'
        f'{{"platform":"Flipkart","price":"INR X","url":"https://www.flipkart.com/search?q=sigma","status":"Check listing"}}]\n'
        f"```\n\n"
        f"DEALER FORMAT (backend replaces with real data from Excel):\n"
        f"```json_dealers\n"
        f'[{{"_meta":true,"query_city":"city user asked","query_region":"chn or del or klr or klt or bng"}},'
        f'{{"name":"Sample Dealer","type":"Authorised Sigma Dealer","location":"City, Region","address":"Full address","dealer_code":"CODE","url":"https://sigmaindia.in/dealer-network/"}}]\n'
        f"```\n\n"
        f"SERVICE CENTRES: When user asks about service/repair centres, mention we have 10 authorised service centres across India in cities: Bangalore, Mumbai (×2), Delhi (×2), Kolkata, Chennai, Secunderabad, Vijayawada, Kottayam. The backend will auto-inject their details.\n"
        f"NEVER invent products Sigma does not make.\n"
        f"NEVER invent dealer names — backend handles real dealer data."
    )

# ══════════════════════════════════════════════════════════
# CLAUDE API
# ══════════════════════════════════════════════════════════
def call_claude(messages, system):
    import urllib.request
    import urllib.error
    import ssl
    import certifi

    if not ANTHROPIC_API_KEY:
        return _fallback(messages[-1]["content"] if messages else "")

    payload = json.dumps({
        "model": CLAUDE_MODEL,
        "max_tokens": 2048,
        "system": system,
        "messages": messages
    }).encode()

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
        },
        method="POST"
    )

    # SSL FIX
    ssl_context = ssl.create_default_context(cafile=certifi.where())

    try:
        with urllib.request.urlopen(
            req,
            timeout=30,
            context=ssl_context
        ) as r:
            return json.loads(r.read())["content"][0]["text"]

    except Exception as e:
        print(f"[CLAUDE] {e}")
        return _fallback(messages[-1]["content"] if messages else "")
    
    
def _fallback(query):
    results = search_products(query, 5)
    if not results:
        return ("I couldn't find products matching that. "
                "Try asking about a focal length, aperture, or product line.")
    prods = []
    for p in results:
        name = p.get("Product Name", "")
        prods.append({
            "name":           name,
            "line":           p.get("Product Line", p.get("Category", "")),
            "category":       p.get("_display_category", ""),
            "focal_length":   p.get("Focal Length", ""),
            "aperture":       p.get("Max Aperture", p.get("T-Stop", "")),
            "mounts":         p.get("Available Mounts", p.get("Compatibility", "")),
            "key_features":   p.get("Key Features", "")[:120],
            "url":            "https://sigmaindia.in/",
            "amazon_in":      f"https://www.amazon.in/s?k=Sigma+{name.replace(' ','+')}",
            "price_inr":      p.get("_price_inr", "Contact dealer"),
            "price_range_inr": p.get("_price_range_inr", ""),
            "reason":         "Matches your search criteria"
        })
    return ("```json_products\n" + json.dumps(prods, indent=2) + "\n```\n\n"
            "Here are Sigma products matching your query. Visit sigmaindia.in for pricing.")

def clean_text_for_chat(text: str) -> str:
    """
    Convert Claude's markdown text into clean plain-text paragraphs
    so the frontend fmtText() renderer handles all formatting.
    Removes: # headings → plain text, excessive blank lines.
    Keeps: **bold**, *italic*, `code`, - bullets, numbered lists.
    The frontend fmtText() will handle those correctly.
    """
    import re
    lines = text.split('\n')
    cleaned = []
    for line in lines:
        # Convert # headings to plain bold text
        m = re.match(r'^#{1,3}\s+(.+)', line)
        if m:
            cleaned.append(f'**{m.group(1)}**')
            continue
        # Remove horizontal rules
        if re.match(r'^[-*_]{3,}$', line.strip()):
            continue
        cleaned.append(line)
 
    result = '\n'.join(cleaned)
    # Collapse 3+ consecutive blank lines into 2
    result = re.sub(r'\n{3,}', '\n\n', result)
    return result.strip()
 
 
# ── 2. Replace the existing parse_response() with this ──────────
 
def parse_response(raw):
    result = {"text": raw, "products": [], "prices": [], "dealers": []}
 
    def ex(tag):
        m = re.search(rf"```{tag}\s*([\s\S]*?)```", raw)
        if m:
            try:
                return json.loads(m.group(1).strip())
            except:
                return []
        return []
 
    result["products"] = ex("json_products")
    result["prices"]   = ex("json_prices")
    result["dealers"]  = ex("json_dealers")
 
    # Strip all JSON blocks from text
    clean = re.sub(r"```json_\w+\s*[\s\S]*?```", "", raw).strip()
 
    # Clean markdown headings → plain text so frontend renders correctly
    result["text"] = clean_text_for_chat(clean)
 
    return result

def load_service_centers() -> list:
    if os.path.exists(SERVICE_CENTER_PATH):
        try:
            with open(SERVICE_CENTER_PATH) as f:
                return json.load(f)
        except:
            pass
    return []
 
def search_service_centers(query: str) -> list:
    """Search service centers by city, state, or name."""
    q = query.lower()
    all_sc = load_service_centers()
    scored = []
    for sc in all_sc:
        city  = (sc.get("city","") or "").lower()
        state = (sc.get("state","") or "").lower()
        name  = (sc.get("name","") or "").lower()
        score = 0
        for word in q.split():
            if len(word) < 3: continue
            if word in city:  score += 5
            elif word in state: score += 3
            elif word in name:  score += 2
        if score > 0:
            scored.append((score, sc))
    scored.sort(key=lambda x: -x[0])
    # If no location match, return all
    if not scored:
        return all_sc
    return [sc for _, sc in scored]
 

# ══════════════════════════════════════════════════════════
# CHATBOT ROUTES
# ══════════════════════════════════════════════════════════
@app.route("/")
def index():
    if "sid" not in session:
        session["sid"] = str(uuid.uuid4())
    session.setdefault("history", [])
    session.setdefault("language_override", None)
    return render_template("index.html", config=load_config())

@app.route("/chat", methods=["POST"])
def chat():
    data     = request.get_json()
    user_msg = (data.get("message") or "").strip()
    if not user_msg:
        return jsonify({"error": "Empty message"}), 400

    history  = session.get("history", [])

    # Detect explicit language request
    detected_lang = detect_language_request(user_msg)
    if detected_lang:
        session["language_override"] = detected_lang
    lang_for_prompt = session.get("language_override")

    history.append({"role": "user", "content": user_msg})
    if len(history) > 20:
        history = history[-20:]

    system = build_system_prompt(detected_language=lang_for_prompt)
    raw    = call_claude(history, system)

    history.append({"role": "assistant", "content": raw})
    session["history"] = history
    save_conversation(session.get("sid", "anon"), history)

    parsed = parse_response(raw)

    # ── Inject images into product cards (always re-check disk) ────────────────
    img_map = {}
    for p in get_all_products():
        name = p.get("Product Name", "")
        pid  = p.get("_id", _product_id(name))
        img_map[name] = _find_image(pid)

    for prod in parsed["products"]:
        prod_name = prod.get("name", "")
        img = img_map.get(prod_name, "")
        if not img:
            img = _find_image(_product_id(prod_name))
        prod["_image"] = img

    # ── Replace AI dealer output with REAL Excel dealer data ───────────────────
    if parsed.get("dealers"):
        raw_dealers = parsed["dealers"]
        meta = next((d for d in raw_dealers if d.get("_meta")), None)
        query_city   = (meta.get("query_city", "")   if meta else "").strip()
        query_region = (meta.get("query_region", "") if meta else "").strip()

        search_q    = f"{user_msg} {query_city} {query_region}"
        real_dealers = search_dealers_by_query(search_q, limit=10)

        if real_dealers:
            city_label = query_city.title() if query_city else "your area"
            formatted  = [format_dealer_for_chat(d) for d in real_dealers]
            formatted.insert(0, {
                "name":        f"Sigma Authorised Dealers — {city_label}",
                "type":        f"{len(real_dealers)} dealers found in our database",
                "location":    "India",
                "address":     "",
                "dealer_code": "",
                "url":         "https://sigmaindia.in/dealer-network/"
            })
            parsed["dealers"] = formatted
        else:
            parsed["dealers"] = [{
                "name":    "Sigma India Dealer Network",
                "type":    "1215+ Authorised Dealers Pan India",
                "location":"Pan India",
                "address": "Visit sigmaindia.in/dealer-network/ to find dealers near you",
                "dealer_code": "",
                "url":     "https://sigmaindia.in/dealer-network/"
            }]
    
    # ── SERVICE CENTERS ─────────────────────

    SERVICE_KEYWORDS = [
        "service center",
        "service centre",
        "repair",
        "warranty repair",
        "service point",
        "authorised service",
        "camera repair",
        "lens repair"
    ]

    msg_lower = user_msg.lower()

    if any(kw in msg_lower for kw in SERVICE_KEYWORDS):

        raw_results = search_service_centers(user_msg)

        parsed["service_centers"] = [
            format_service_center_for_chat(x)
            for x in raw_results
        ]

    else:
        parsed["service_centers"] = []

    return jsonify(parsed)

@app.route("/reset", methods=["POST"])
def reset():
    session["history"]           = []
    session["sid"]               = str(uuid.uuid4())
    session["language_override"] = None
    return jsonify({"ok": True})

@app.route("/config-public")
def config_public():
    cfg = load_config()
    return jsonify({k: cfg[k] for k in [
        "brand_name", "welcome_message", "offer_banner", "mandatory_message",
        "language", "show_comparison", "show_price_table", "show_dealer_section",
        "show_amazon_links", "max_products_shown",
        "collect_user_data", "user_data_message_gap", "collect_user_prompt"
    ]})

# ── User Lead Capture ─────────────────────────────────────
LEADS_PATH = os.path.join(BASE_DIR, "data", "leads.json")

def load_leads():
    if os.path.exists(LEADS_PATH):
        try:
            with open(LEADS_PATH) as f:
                return json.load(f)
        except:
            pass
    return []

@app.route("/save-lead", methods=["POST"])
def save_lead():
    data = request.get_json()
    leads = load_leads()
    leads.append({
        "session_id": session.get("sid", "anon"),
        "name":       (data.get("name") or "").strip(),
        "phone":      (data.get("phone") or "").strip(),
        "captured_at": datetime.now().isoformat(),
        "message_count": len([m for m in session.get("history", []) if m["role"] == "user"])
    })
    with open(LEADS_PATH, "w") as f:
        json.dump(leads, f, indent=2)
    return jsonify({"ok": True})

@app.route("/admin/api/leads")
def api_leads():
    return jsonify(load_leads())

@app.route("/admin/api/leads/clear", methods=["POST"])
def api_clear_leads():
    with open(LEADS_PATH, "w") as f:
        json.dump([], f)
    return jsonify({"ok": True})

# ══════════════════════════════════════════════════════════
# ADMIN ROUTES
# ══════════════════════════════════════════════════════════
@app.route("/admin")
def admin():
    if not session.get("admin_logged_in"):
        return render_template("admin.html")

    return render_template("admin.html")
# ── Products ─────────────────────────────────────────────
@app.route("/admin/api/products")
def api_products():
    return jsonify(get_all_products())

@app.route("/admin/api/products/update", methods=["POST"])
def api_update_product():
    d = request.get_json()
    ok, msg = save_product_to_xlsx(d.get("sheet"), d.get("product_name"), d.get("fields", {}))
    return jsonify({"ok": ok, "message": msg})

@app.route("/admin/api/products/delete", methods=["POST"])
def api_delete_product():
    d = request.get_json()
    ok, msg = delete_product_from_xlsx(d.get("sheet"), d.get("product_name"))
    return jsonify({"ok": ok, "message": msg})

@app.route("/admin/api/products/add", methods=["POST"])
def api_add_product():
    d = request.get_json()
    ok, msg = add_product_to_xlsx(d.get("sheet"), d.get("fields", {}))
    return jsonify({"ok": ok, "message": msg})

# ── Images ───────────────────────────────────────────────
@app.route("/admin/api/products/image", methods=["POST"])
def api_upload_image():
    pid = request.form.get("product_id", "")
    if "image" not in request.files:
        return jsonify({"ok": False, "message": "No file"})
    f   = request.files["image"]
    ext = (f.filename.rsplit(".", 1)[-1] if "." in f.filename else "").lower()
    if ext not in ALLOWED_EXT:
        return jsonify({"ok": False, "message": "Invalid file type"})
    # Remove any existing images for this product
    for e in ALLOWED_EXT:
        old = os.path.join(IMAGES_DIR, f"{pid}.{e}")
        if os.path.exists(old):
            os.remove(old)
    filename = f"{pid}.{ext}"
    f.save(os.path.join(IMAGES_DIR, filename))
    url = f"/static/images/{filename}"
    print(f"[IMAGE UPLOAD] Saved {filename} → {url}")
    return jsonify({"ok": True, "url": url})

@app.route("/admin/api/products/image/delete", methods=["POST"])
def api_delete_image():
    pid = request.get_json().get("product_id", "")
    for e in ALLOWED_EXT:
        p = os.path.join(IMAGES_DIR, f"{pid}.{e}")
        if os.path.exists(p):
            os.remove(p)
    return jsonify({"ok": True})

# ── Dealers ──────────────────────────────────────────────
@app.route("/admin/api/dealers")
def api_dealers():
    sheet = request.args.get("sheet", None)
    if sheet:
        data = load_dealers(sheet)
        return jsonify(data.get(sheet, []))
    return jsonify(get_all_dealers_flat())

@app.route("/admin/api/dealers/sheets")
def api_dealer_sheets():
    return jsonify([
        {"key": k, "label": v}
        for k, v in DEALER_SHEET_MAP.items()
    ])

@app.route("/admin/api/dealers/update", methods=["POST"])
def api_update_dealer():
    d = request.get_json()
    ok, msg = save_dealer_to_xlsx(d.get("sheet"), d.get("dealer_code"), d.get("fields", {}))
    return jsonify({"ok": ok, "message": msg})

@app.route("/admin/api/dealers/delete", methods=["POST"])
def api_delete_dealer():
    d = request.get_json()
    ok, msg = delete_dealer_from_xlsx(d.get("sheet"), d.get("dealer_code"))
    return jsonify({"ok": ok, "message": msg})

@app.route("/admin/api/dealers/add", methods=["POST"])
def api_add_dealer():
    d = request.get_json()
    ok, msg = add_dealer_to_xlsx(d.get("sheet"), d.get("fields", {}))
    return jsonify({"ok": ok, "message": msg})

# ── Config ───────────────────────────────────────────────
@app.route("/admin/api/config", methods=["GET"])
def api_get_config():
    return jsonify(load_config())

@app.route("/admin/api/config", methods=["POST"])
def api_save_config():
    data = request.get_json()
    cfg  = load_config()
    for k in DEFAULT_CONFIG:
        if k in data:
            cfg[k] = data[k]
    save_config(cfg)
    return jsonify({"ok": True, "message": "Configuration saved successfully"})

# ── WhatsApp Config + Sessions ────────────────────────────
@app.route("/admin/api/whatsapp/config", methods=["GET"])
def api_get_whatsapp_config():
    return jsonify(load_whatsapp_config())

@app.route("/admin/api/whatsapp/config", methods=["POST"])
def api_save_whatsapp_config():
    data = request.get_json()
    cfg  = load_whatsapp_config()
    for k in DEFAULT_WHATSAPP_CONFIG:
        if k in data:
            cfg[k] = data[k]
    save_whatsapp_config(cfg)
    return jsonify({"ok": True, "message": "WhatsApp configuration saved"})

@app.route("/admin/api/whatsapp/sessions")
def api_whatsapp_sessions():
    """Summary list for the table — phone, name, counts, timestamps."""
    sessions = load_whatsapp_sessions()
    summaries = []
    for s in sessions:
        hist = s.get("history", [])
        last_text = hist[-1].get("text", "") if hist else ""
        summaries.append({
            "phone":         s.get("phone", ""),
            "name":          s.get("name", ""),
            "started_at":    s.get("started_at", ""),
            "updated_at":    s.get("updated_at", ""),
            "message_count": len(hist),
            "last_message":  last_text,
        })
    summaries.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
    return jsonify(summaries)

@app.route("/admin/api/whatsapp/sessions/detail")
def api_whatsapp_session_detail():
    phone = request.args.get("phone", "")
    for s in load_whatsapp_sessions():
        if s.get("phone") == phone:
            return jsonify(s)
    return jsonify({"error": "Not found"}), 404

@app.route("/admin/api/whatsapp/sessions/delete", methods=["POST"])
def api_whatsapp_session_delete():
    phone    = (request.get_json() or {}).get("phone", "")
    sessions = [s for s in load_whatsapp_sessions() if s.get("phone") != phone]
    save_whatsapp_sessions(sessions)
    return jsonify({"ok": True})

@app.route("/admin/api/whatsapp/sessions/clear", methods=["POST"])
def api_whatsapp_sessions_clear():
    save_whatsapp_sessions([])
    return jsonify({"ok": True})

# ── Conversations ────────────────────────────────────────
@app.route("/admin/api/conversations")
def api_conversations():
    convs      = load_conversations()
    summaries  = []
    for c in convs:
        msgs  = c.get("messages", [])
        first = next((m["content"][:100] for m in msgs if m["role"] == "user"), "")
        summaries.append({
            "session_id":    c["session_id"],
            "started_at":    c.get("started_at", ""),
            "updated_at":    c.get("updated_at", ""),
            "message_count": c.get("message_count", 0),
            "preview":       first
        })
    return jsonify(summaries)

@app.route("/admin/api/conversations/<sid>")
def api_conversation(sid):
    for c in load_conversations():
        if c["session_id"] == sid:
            return jsonify(c)
    return jsonify({"error": "Not found"}), 404

@app.route("/admin/api/conversations/delete", methods=["POST"])
def api_del_conversation():
    sid   = request.get_json().get("session_id", "")
    convs = [c for c in load_conversations() if c["session_id"] != sid]
    with open(CONV_PATH, "w") as f:
        json.dump(convs, f, indent=2)
    return jsonify({"ok": True})

@app.route("/admin/api/conversations/clear", methods=["POST"])
def api_clear_conversations():
    with open(CONV_PATH, "w") as f:
        json.dump([], f)
    return jsonify({"ok": True})

# ── Static images ─────────────────────────────────────────
@app.route("/static/images/<filename>")
def serve_img(filename):
    return send_from_directory(IMAGES_DIR, filename)

# ══════════════════════════════════════════════════════════
# SERVICE CENTERS
# ══════════════════════════════════════════════════════════

 
# ── Admin: Price CRUD ─────────────────────────────────────
@app.route("/admin/api/prices")
def api_get_prices():
    """Return merged prices: PRICE_USD defaults + any overrides from prices.json."""
    overrides = load_prices()
    merged = {}
    for name, usd in PRICE_USD.items():
        if name in overrides:
            merged[name] = overrides[name]
        else:
            merged[name] = {
                "price_inr":       fmt_inr(usd),
                "price_range_inr": fmt_inr_range(usd),
                "price_usd":       usd,
            }
    # Also include any overrides for names NOT in PRICE_USD
    for name, data in overrides.items():
        if name not in merged:
            merged[name] = data
    return jsonify(merged)
 
@app.route("/admin/api/prices/update", methods=["POST"])
def api_update_price():
    data     = request.get_json()
    name     = (data.get("name") or "").strip()
    price_inr = (data.get("price_inr") or "").strip()
    price_range = (data.get("price_range_inr") or "").strip()
    price_usd   = data.get("price_usd", 0)
    if not name:
        return jsonify({"ok": False, "message": "Name required"})
    overrides = load_prices()
    overrides[name] = {
        "price_inr":       price_inr,
        "price_range_inr": price_range,
        "price_usd":       price_usd,
    }
    save_prices(overrides)
    return jsonify({"ok": True, "message": "Price updated"})
 
@app.route("/admin/api/prices/delete", methods=["POST"])
def api_delete_price_override():
    name = (request.get_json().get("name") or "").strip()
    overrides = load_prices()
    if name in overrides:
        del overrides[name]
        save_prices(overrides)
    return jsonify({"ok": True})
 
# ── Admin: Service Centers CRUD ───────────────────────────
@app.route("/admin/api/service-centers")
def api_service_centers():
    return jsonify(load_service_centers())
 
@app.route("/admin/api/service-centers/update", methods=["POST"])
def api_update_service_center():
    data  = request.get_json()
    idx   = data.get("index")
    fields = data.get("fields", {})
    scs   = load_service_centers()
    if idx is None or idx < 0 or idx >= len(scs):
        return jsonify({"ok": False, "message": "Invalid index"})
    scs[idx].update(fields)
    with open(SERVICE_CENTER_PATH, "w") as f:
        json.dump(scs, f, indent=2)
    return jsonify({"ok": True})
 
@app.route("/admin/api/service-centers/add", methods=["POST"])
def api_add_service_center():
    data = request.get_json()
    scs  = load_service_centers()
    scs.append(data)
    with open(SERVICE_CENTER_PATH, "w") as f:
        json.dump(scs, f, indent=2)
    return jsonify({"ok": True})
 
@app.route("/admin/api/service-centers/delete", methods=["POST"])
def api_delete_service_center():
    idx = request.get_json().get("index")
    scs = load_service_centers()
    if idx is None or idx < 0 or idx >= len(scs):
        return jsonify({"ok": False, "message": "Invalid index"})
    scs.pop(idx)
    with open(SERVICE_CENTER_PATH, "w") as f:
        json.dump(scs, f, indent=2)
    return jsonify({"ok": True})


# ══════════════════════════════════════════════════════════
# ADMIN AUTH
# ══════════════════════════════════════════════════════════

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "sigma123"


@app.route("/admin/login", methods=["POST"])
def admin_login():
    data = request.json

    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        session["admin_logged_in"] = True
        return jsonify({
            "success": True
        })

    return jsonify({
        "success": False,
        "message": "Invalid credentials"
    }), 401


@app.route("/admin/logout", methods=["POST"])
def admin_logout():
    session.pop("admin_logged_in", None)

    return jsonify({
        "success": True
    })


@app.route("/admin/check-auth")
def check_admin_auth():
    return jsonify({
        "authenticated": session.get("admin_logged_in", False)
    })
 

if __name__ == "__main__":
    print("=" * 56)
    print("  Sigma AI Assistant  →  http://localhost:5000")
    print("  Admin Panel         →  http://localhost:5000/admin")
    print("=" * 56)
    if not ANTHROPIC_API_KEY:
        print("  ⚠  No ANTHROPIC_API_KEY — fallback mode")
    print("=" * 56)
    app.run(host="0.0.0.0", port=5000)
"""
╔══════════════════════════════════════════════════════════════════╗
║           SIGMA AI — WhatsApp Bot  (Twilio)                      ║
║   Place this file in the same folder as app.py                   ║
║   Run: python sigma_whatsapp_bot.py                              ║
╚══════════════════════════════════════════════════════════════════╝

SETUP
─────
1.  pip install flask twilio python-dotenv
2.  Create a Twilio account → enable WhatsApp Sandbox
3.  Fill .env with TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_FROM
4.  Expose with ngrok: ngrok http 5000
5.  Set sandbox webhook to: https://<ngrok-url>/whatsapp
6.  python sigma_whatsapp_bot.py

DESIGN NOTES
────────────
• Interactive list messages (tap-to-select) via Twilio Content API.
  Menus with ≤10 items use WhatsApp interactive lists (buttons user taps).
  Menus with >10 items split into pages of 10 with a Next Page button.
• Every reply is a NEW message — chat history is never deleted.
• No product/dealer/service counts shown to the user anywhere.
• Footer links only to sigmaindia.in.
"""

import os, sys, json, logging, re
from datetime import datetime, timezone
from pathlib import Path
from flask import Flask, request

# Load .env file if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

sys.path.insert(0, os.path.dirname(__file__))
from app import (
    get_all_products, search_products, load_products,
    load_prices, PRICE_USD, get_price_inr, get_price_range_inr,
    fmt_inr, fmt_inr_range,
    load_dealers, get_all_dealers_flat, search_dealers_by_query,
    format_dealer_for_chat, DEALER_SHEET_MAP,
    load_service_centers, search_service_centers, format_service_center_for_chat,
    load_config,
    BASE_DIR, IMAGES_DIR,
)

from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse

# ════════════════════════════════════════════════════════════════════
#  CONFIG
# ════════════════════════════════════════════════════════════════════
ACCOUNT_SID  = os.getenv("TWILIO_ACCOUNT_SID", "YOUR_ACCOUNT_SID")
AUTH_TOKEN   = os.getenv("TWILIO_AUTH_TOKEN",  "YOUR_AUTH_TOKEN")
FROM_NUMBER  = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")

SIGMA_WEBSITE = "https://sigmaindia.in"
SESSIONS_PATH = Path(BASE_DIR) / "data" / "whatsapp_sessions.json"

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)

app_flask    = Flask(__name__)
twilio_client = Client(ACCOUNT_SID, AUTH_TOKEN)

# ════════════════════════════════════════════════════════════════════
#  CONSTANTS
# ════════════════════════════════════════════════════════════════════
DIV    = "━" * 28
FOOTER = f"\n{'─'*28}\n🌐 sigmaindia.in"

# Twilio interactive list max items per section
LIST_PAGE_SIZE = 10

# ════════════════════════════════════════════════════════════════════
#  SESSION STORAGE
# ════════════════════════════════════════════════════════════════════
SESSIONS: dict = {}


def get_session(phone: str) -> dict:
    if phone not in SESSIONS:
        SESSIONS[phone] = {"menu": "main", "history": [], "context": {}}
    return SESSIONS[phone]


def save_session_disk(phone: str, name: str):
    sess     = SESSIONS.get(phone, {})
    sessions = _load_sessions_disk()
    now      = datetime.now(timezone.utc).isoformat()
    for s in sessions:
        if s.get("phone") == phone:
            s["history"]    = sess.get("history", [])[-50:]
            s["updated_at"] = now
            s["name"]       = name
            _write_sessions_disk(sessions)
            return
    sessions.append({
        "phone": phone, "name": name,
        "started_at": now, "updated_at": now,
        "history": sess.get("history", []),
    })
    _write_sessions_disk(sessions)


def _load_sessions_disk() -> list:
    if SESSIONS_PATH.exists():
        try:
            with open(SESSIONS_PATH) as f:
                return json.load(f)
        except Exception:
            pass
    return []


def _write_sessions_disk(data: list):
    SESSIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SESSIONS_PATH, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ════════════════════════════════════════════════════════════════════
#  TWILIO INTERACTIVE LIST MESSAGE SENDER
#  Sends a WhatsApp interactive list (tap-to-select buttons).
#  options = list of (label, reply_id)  — max 10 per call.
#  body_text is displayed above the list button.
# ════════════════════════════════════════════════════════════════════

def send_interactive_list(to: str, header: str, body: str,
                           options: list, button_label: str = "Choose an option"):
    """
    Send a WhatsApp interactive list message via Twilio Content API.
    options: list of (title, id) tuples — max 10, each title max 24 chars.
    Returns the Twilio message SID or None on failure.
    """
    # Build Content API payload
    items = []
    for title, reply_id in options[:LIST_PAGE_SIZE]:
        items.append({
            "id":    reply_id[:200],
            "title": title[:24],
        })

    content_payload = {
        "friendly_name": f"sigma_menu_{datetime.now().strftime('%H%M%S')}",
        "language":      "en",
        "variables":     {},
        "types": {
            "twilio/list-picker": {
                "body":   body[:1024],
                "button": button_label[:20],
                "items":  items,
            }
        }
    }

    try:
        # Create content template
        content = twilio_client.content.v1.contents.create(
            friendly_name=content_payload["friendly_name"],
            language=content_payload["language"],
            variables=content_payload["variables"],
            types=content_payload["types"],
        )
        # Send via content SID
        msg = twilio_client.messages.create(
            content_sid=content.sid,
            from_=FROM_NUMBER,
            to=to,
        )
        log.info(f"Interactive list sent: {msg.sid}")
        return msg.sid
    except Exception as e:
        log.warning(f"Interactive list failed ({e}), falling back to text menu")
        return None


def send_text_message(to: str, body: str):
    """Send a plain text WhatsApp message."""
    try:
        msg = twilio_client.messages.create(
            body=body,
            from_=FROM_NUMBER,
            to=to,
        )
        log.info(f"Text message sent: {msg.sid}")
        return msg.sid
    except Exception as e:
        log.error(f"Failed to send text message: {e}")
        return None


def send_menu(to: str, header: str, body_text: str, options: list,
              button_label: str = "Choose an option") -> bool:
    """
    Try interactive list first; fall back to numbered text menu.
    Returns True if interactive was used, False if text fallback.
    options: list of (label, key) tuples.
    """
    sid = send_interactive_list(to, header, body_text, options, button_label)
    if sid:
        return True
    # Fallback: numbered text
    lines = [f"{header}", DIV, body_text, ""]
    for i, (label, _) in enumerate(options, 1):
        lines.append(f"  *{i}.* {label}")
    lines.append("\n_Reply with a number to continue_")
    lines.append(FOOTER)
    send_text_message(to, "\n".join(lines))
    return False


# ════════════════════════════════════════════════════════════════════
#  MENU OPTION DEFINITIONS
# ════════════════════════════════════════════════════════════════════

MAIN_OPTIONS = [
    ("🛒  Sales",      "sales"),
    ("🔧  Services",   "services"),
    ("🛡️  Warranty",   "warranty"),
    ("⭐  Loyalty",    "loyalty"),
]

SALES_OPTIONS = [
    ("📦  Browse Products", "products"),
    ("💰  View Pricing",    "prices"),
    ("🤝  Find a Dealer",   "dealers"),
    ("🏠  Main Menu",       "main"),
]

SERVICES_OPTIONS = [
    ("🔧  Find a Service Centre", "service"),
    ("🧰  What We Service",       "svc_coverage"),
    ("📞  Contact Support",       "contact"),
    ("🏠  Main Menu",             "main"),
]

WARRANTY_OPTIONS = [
    ("📜  Warranty Terms",        "warranty_terms"),
    ("📝  Register Your Product", "warranty_register"),
    ("🔍  Check Warranty Status", "warranty_status"),
    ("🏠  Main Menu",             "main"),
]

LOYALTY_OPTIONS = [
    ("🎁  Member Benefits",  "loyalty_benefits"),
    ("➕  How to Join",      "loyalty_join"),
    ("📈  My Loyalty Status","loyalty_status"),
    ("🏠  Main Menu",        "main"),
]

PRODUCT_CAT_OPTIONS = [
    ("📷  Still Lenses", "cat:Still Lenses"),
    ("🎬  Cine Lenses",  "cat:Cine Lenses"),
    ("📸  Cameras",      "cat:Cameras"),
    ("🎒  Accessories",  "cat:Accessories"),
    ("⬅️  Back to Sales","sales"),
    ("🏠  Main Menu",    "main"),
]

PRICE_CAT_OPTIONS = [
    ("📷  Still Lenses", "price_cat:Still Lenses"),
    ("🎬  Cine Lenses",  "price_cat:Cine Lenses"),
    ("📸  Cameras",      "price_cat:Cameras"),
    ("🎒  Accessories",  "price_cat:Accessories"),
    ("⬅️  Back to Sales","sales"),
    ("🏠  Main Menu",    "main"),
]

DEALER_REGION_OPTIONS = [
    ("🔴  Chennai",    "dealer_region:chn"),
    ("🟠  Delhi",      "dealer_region:del"),
    ("🟢  Kerala",     "dealer_region:klr"),
    ("🔵  Kozhikode",  "dealer_region:klt"),
    ("🟣  Bangalore",  "dealer_region:bng"),
    ("🟡  Mumbai",     "dealer_region:mum"),
    ("⚪  Telangana",  "dealer_region:tel"),
    ("⬅️  Back to Sales","sales"),
    ("🏠  Main Menu",  "main"),
]

CAT_KEY_MAP = {
    "Still Lenses": "still_lenses", "Cine Lenses": "cine_lenses",
    "Cameras": "cameras",           "Accessories": "accessories",
}


def build_product_list_options(category: str) -> list:
    items = load_products().get(CAT_KEY_MAP.get(category, "still_lenses"), [])
    opts  = [(p["Product Name"][:24], f"product:{p['Product Name']}") for p in items]
    opts.append(("⬅️  Categories", "products"))
    opts.append(("🏠  Main Menu",  "main"))
    return opts


def build_price_list_options(category: str) -> list:
    items = load_products().get(CAT_KEY_MAP.get(category, "still_lenses"), [])
    opts  = [(p["Product Name"][:24], f"price:{p['Product Name']}") for p in items]
    opts.append(("⬅️  Pricing",   "prices"))
    opts.append(("🏠  Main Menu", "main"))
    return opts


def build_dealer_list_options(region_key: str, dealers: list) -> list:
    opts = [(d.get("customer_name", "Dealer")[:24], f"dealer:{region_key}:{i}")
            for i, d in enumerate(dealers)]
    opts.append(("⬅️  Regions",   "dealers"))
    opts.append(("🏠  Main Menu", "main"))
    return opts


def build_service_list_options(centers: list) -> list:
    opts = [(c.get("name", "Centre")[:24], f"svc:{i}")
            for i, c in enumerate(centers)]
    opts.append(("⬅️  Services",  "services"))
    opts.append(("🏠  Main Menu", "main"))
    return opts


# ════════════════════════════════════════════════════════════════════
#  PAGINATED MENU SENDER
#  Splits large option lists into pages of LIST_PAGE_SIZE.
# ════════════════════════════════════════════════════════════════════

def send_paged_menu(to: str, header: str, body: str,
                    options: list, sess: dict, page: int = 0):
    """
    Sends one page of options (up to LIST_PAGE_SIZE items).
    Appends a 'Next Page ▶' option if more pages remain.
    Stores full options + page in session for numeric fallback.
    """
    # Always keep nav options (last 2) outside paging logic
    nav   = options[-2:]   # ⬅️ back + 🏠 main
    items = options[:-2]   # actual content options

    start   = page * (LIST_PAGE_SIZE - 3)   # reserve 3 slots for nav + next
    end     = start + (LIST_PAGE_SIZE - 3)
    page_items = items[start:end]
    has_next   = end < len(items)
    has_prev   = page > 0

    display = list(page_items)
    if has_prev:
        display.append(("◀  Prev Page", f"__page_prev__{page-1}"))
    if has_next:
        display.append(("▶  Next Page", f"__page_next__{page+1}"))
    display += nav

    sess["options"]       = display
    sess["all_options"]   = options
    sess["current_page"]  = page

    send_menu(to, header, body, display)


# ════════════════════════════════════════════════════════════════════
#  CONTENT MESSAGES (no counts anywhere)
# ════════════════════════════════════════════════════════════════════

def welcome_msg(user_name: str) -> str:
    cfg   = load_config()
    brand = cfg.get("brand_name", "Sigma AI Assistant")
    return (
        f"👋 *Welcome, {user_name}!*\n\n"
        f"I'm the *{brand}* — your dedicated guide for everything "
        f"related to Sigma in India.\n\n"
        f"I can help you:\n"
        f"• Explore products and pricing\n"
        f"• Locate dealers and service centres\n"
        f"• Understand your warranty\n"
        f"• Learn about our loyalty programme\n"
        f"{FOOTER}"
    )


SALES_BODY = (
    "Whether you're choosing your first Sigma lens or expanding a "
    "professional kit, this is the right place to start.\n\n"
    "Browse our catalogue across Still Lenses, Cine Lenses, Cameras, "
    "and Accessories — each engineered to Sigma's exacting standards.\n\n"
    "Browse by category, check Indian pricing, or find an authorised "
    "dealer near you."
)

SERVICES_BODY = (
    "Our authorised service network keeps your Sigma equipment "
    "performing at its best.\n\n"
    "Get warranty repairs, out-of-warranty servicing, firmware updates, "
    "and precision calibration — all by Sigma-trained technicians "
    "using genuine parts."
)

WARRANTY_BODY = (
    "Every Sigma product sold through our authorised channels in India "
    "is backed by a manufacturer's warranty.\n\n"
    "Registering your product ensures your coverage is recorded "
    "correctly and helps us serve you faster."
)

LOYALTY_BODY = (
    "Recognising customers on their long-term creative journey with "
    "Sigma — exclusive offers, priority service, early product "
    "access, and trade-up benefits."
)

WARRANTY_TERMS_MSG = (
    f"📜 *Warranty Terms*\n{DIV}\n"
    f"• *Coverage:* Manufacturing defects in materials and workmanship "
    f"from date of purchase at an authorised dealer.\n\n"
    f"• *What's covered:* Focus mechanisms, electronic contacts, build "
    f"issues under normal use.\n\n"
    f"• *Not covered:* Accidental damage, water damage, unauthorised "
    f"modifications, and normal wear.\n\n"
    f"• *Proof of purchase:* Keep your original invoice — it's required "
    f"for all warranty claims.\n\n"
    f"Full terms are included with your product or on our website."
    f"{FOOTER}"
)

WARRANTY_REGISTER_MSG = (
    f"📝 *Register Your Product*\n{DIV}\n"
    f"Registration takes just a couple of minutes and speeds up any "
    f"future service visit.\n\n"
    f"You'll need:\n"
    f"• Serial number (on the barcode label or lens barrel)\n"
    f"• Copy of your purchase invoice\n"
    f"• Your contact details\n\n"
    f"Register via the product registration page at sigmaindia.in."
    f"{FOOTER}"
)

WARRANTY_STATUS_MSG = (
    f"🔍 *Check Warranty Status*\n{DIV}\n"
    f"To check your warranty or repair status, please have ready:\n"
    f"• Product serial number\n"
    f"• Service request / job sheet number\n"
    f"• Mobile number or email used at registration\n\n"
    f"Our support team can look this up, or use the warranty lookup "
    f"on sigmaindia.in."
    f"{FOOTER}"
)

LOYALTY_BENEFITS_MSG = (
    f"🎁 *Member Benefits*\n{DIV}\n"
    f"• *Exclusive offers:* Members-only pricing on selected products.\n\n"
    f"• *Priority service:* Faster turnaround at authorised service centres.\n\n"
    f"• *Early access:* First to know about new launches and firmware.\n\n"
    f"• *Trade-up assistance:* Preferential terms when upgrading Sigma gear.\n\n"
    f"• *Dedicated support:* Direct line to our team for membership queries.\n\n"
    f"Full details available on sigmaindia.in."
    f"{FOOTER}"
)

LOYALTY_JOIN_MSG = (
    f"➕ *How to Join*\n{DIV}\n"
    f"Joining is free for owners of registered Sigma products.\n\n"
    f"Steps:\n"
    f"1. *Register* a Sigma product (see Warranty › Register).\n"
    f"2. *Enrol* using your registered details on sigmaindia.in.\n"
    f"3. *Activate* — benefits go live once verified.\n\n"
    f"Haven't registered your product yet? That's the best place to start."
    f"{FOOTER}"
)

LOYALTY_STATUS_MSG = (
    f"📈 *My Loyalty Status*\n{DIV}\n"
    f"To check your membership tier, points, or active offers, have ready:\n"
    f"• Mobile number or email used at enrolment\n"
    f"• Membership ID (sent at sign-up)\n\n"
    f"Our support team can verify your status, or log in at sigmaindia.in."
    f"{FOOTER}"
)

SVC_COVERAGE_MSG = (
    f"🧰 *What We Service*\n{DIV}\n"
    f"Our centres handle the full Sigma range:\n\n"
    f"• *Lenses:* Focus repairs, aperture & contact issues, optical "
    f"cleaning, mount repairs, image stabilisation (OS) servicing.\n\n"
    f"• *Cameras:* Sensor cleaning & calibration, firmware updates, "
    f"button/dial repairs, diagnostics.\n\n"
    f"• *Calibration:* Precision AF calibration for your lens + camera body.\n\n"
    f"• *Firmware:* Updates for latest body & feature compatibility.\n\n"
    f"All work uses genuine Sigma parts."
    f"{FOOTER}"
)

CONTACT_MSG = (
    f"📞 *Contact Sigma India*\n{DIV}\n"
    f"📧  *General Enquiries:*  info@sigmaindia.in\n"
    f"🔧  *Service Support:*  sigmaindia.in/service-support/\n"
    f"🤝  *Dealer Network:*  sigmaindia.in/dealer-network/\n\n"
    f"🕐  *Business Hours:*  Mon–Sat, 9 AM – 6 PM IST\n"
    f"_Our team typically responds within 2 business hours._"
    f"{FOOTER}"
)


# ════════════════════════════════════════════════════════════════════
#  DETAIL FORMATTERS
# ════════════════════════════════════════════════════════════════════

def fmt_product_detail(p: dict) -> str:
    name     = p.get("Product Name", "—")
    cat      = p.get("_display_category", "")
    line     = p.get("Product Line", p.get("Category", ""))
    fl       = p.get("Focal Length", "")
    ap       = p.get("Max Aperture", p.get("T-Stop", ""))
    mounts   = p.get("Available Mounts", p.get("Compatibility", ""))
    features = p.get("Key Features", "")
    price    = get_price_inr(name)
    pr_range = get_price_range_inr(name)

    lines = [f"📦 *{name}*"]
    if cat or line:
        lines.append(f"_{cat}{'  •  ' if cat and line else ''}{line}_")
    lines.append(DIV)
    if fl:       lines.append(f"🔭  *Focal Length:*  {fl}")
    if ap:       lines.append(f"🔆  *Aperture:*  {ap}")
    if mounts:   lines.append(f"🔩  *Mounts:*  {mounts}")
    if features: lines.append(f"\n✨  *Key Features*\n{features}")
    lines.append(DIV)
    lines.append(f"💰  *Price (India):*  {price}")
    if pr_range: lines.append(f"📊  *Range:*  {pr_range}")
    lines.append(
        f"\n🛒  Amazon India: amazon.in (search Sigma {name})"
        f"\n🔵  Flipkart: flipkart.com (search Sigma {name})"
    )
    lines.append(FOOTER)
    return "\n".join(l for l in lines if l)


def fmt_price_detail(name: str) -> str:
    price    = get_price_inr(name)
    pr_range = get_price_range_inr(name)
    usd      = PRICE_USD.get(name, 0)
    overrides = load_prices()
    source   = "🔒 Admin Override" if name in overrides else "📊 Calculated from USD"
    return (
        f"💰 *{name}*\n{DIV}\n"
        f"🇮🇳  *Sigma India Price:*  {price}\n"
        f"📊  *Price Range:*  {pr_range or '—'}\n"
        f"🌐  *USD Price:*  ${usd:,}\n"
        f"🔍  *Source:*  {source}\n{DIV}\n"
        f"_Prices are indicative. Contact your nearest dealer for final pricing._"
        f"{FOOTER}"
    )


def fmt_dealer_detail(d: dict) -> str:
    f = format_dealer_for_chat(d)
    lines = [
        f"🏪 *{f.get('name', '—')}*",
        f"✅  _Authorised Sigma Dealer_",
        DIV,
        f"📍  *Location:*  {f.get('location', '')}",
    ]
    if f.get("address"):      lines.append(f"🗺️  *Address:*  {f['address']}")
    if f.get("dealer_code"):  lines.append(f"🆔  *Dealer Code:*  {f['dealer_code']}")
    if f.get("sales_person"): lines.append(f"👤  *Sales Contact:*  {f['sales_person']}")
    lines.append(FOOTER)
    return "\n".join(l for l in lines if l)


def fmt_service_center(c: dict) -> str:
    f = format_service_center_for_chat(c)
    lines = [
        f"🔧 *{f.get('name', '—')}*",
        f"✅  _Authorised Sigma Service Centre_",
        DIV,
        f"📍  *Location:*  {f.get('location', '')}",
        f"🗺️  *Address:*  {f.get('address', '')}",
        f"📞  *Phone:*  {f.get('phone', '—')}",
        f"📧  *Email:*  {f.get('email', '—')}",
    ]
    lines.append(FOOTER)
    return "\n".join(l for l in lines if l)


# ════════════════════════════════════════════════════════════════════
#  CORE MESSAGE PROCESSOR
# ════════════════════════════════════════════════════════════════════

def process_message(phone: str, user_name: str, body: str):
    """
    Main entry point. Sends replies directly via Twilio.
    Returns nothing — all sending happens here.
    """
    sess = get_session(phone)
    body = body.strip()
    low  = body.lower()
    hist = sess.setdefault("history", [])
    ctx  = sess.setdefault("context", {})
    hist.append({"ts": datetime.now(timezone.utc).isoformat(), "text": body})

    # ── Global shortcuts ──────────────────────────────────────────
    if low in ("hi", "hello", "hey", "start", "/start"):
        sess["menu"] = "main"
        ctx.clear()
        send_text_message(phone, welcome_msg(user_name))
        _send_main_menu(phone, sess)
        return

    if low in ("menu", "/menu", "0", "back", "home"):
        sess["menu"] = "main"
        ctx.clear()
        _send_main_menu(phone, sess)
        return

    # ── Check if reply matches an interactive list item ID ─────────
    # Twilio sends the item's `id` field as the message body when user taps
    current_options = sess.get("options", [])
    matched_key = None

    # Direct ID match (interactive list reply)
    for label, key in current_options:
        if body == key:
            matched_key = key
            break

    # Pagination shortcuts
    if matched_key is None:
        pg_next = re.match(r"^__page_next__(\d+)$", body)
        pg_prev = re.match(r"^__page_prev__(\d+)$", body)
        if pg_next:
            all_opts = sess.get("all_options", current_options)
            hdr      = sess.get("page_header", "Options")
            bod      = sess.get("page_body", "Select an option:")
            send_paged_menu(phone, hdr, bod, all_opts, sess, int(pg_next.group(1)))
            return
        if pg_prev:
            all_opts = sess.get("all_options", current_options)
            hdr      = sess.get("page_header", "Options")
            bod      = sess.get("page_body", "Select an option:")
            send_paged_menu(phone, hdr, bod, all_opts, sess, int(pg_prev.group(1)))
            return

    # Numeric fallback (user typed a number instead of tapping)
    if matched_key is None and body.isdigit():
        idx = int(body) - 1
        if 0 <= idx < len(current_options):
            matched_key = current_options[idx][1]

    if matched_key is not None:
        route(phone, user_name, matched_key, sess)
        return

    # ── Plain text search ──────────────────────────────────────────
    handle_text_search(phone, user_name, body, sess)


def _send_main_menu(phone: str, sess: dict):
    sess["options"] = MAIN_OPTIONS
    send_menu(phone, "🏠 Main Menu", "How can I help you today?",
              MAIN_OPTIONS, "Choose a topic")


def route(phone: str, user_name: str, key: str, sess: dict):
    ctx = sess.setdefault("context", {})

    # ── Main menu ──────────────────────────────────────────────────
    if key == "main":
        sess["menu"] = "main"
        ctx.clear()
        _send_main_menu(phone, sess)

    # ── Sales ──────────────────────────────────────────────────────
    elif key == "sales":
        sess["options"] = SALES_OPTIONS
        send_menu(phone, "🛒 Sales", SALES_BODY, SALES_OPTIONS, "What would you like?")

    # ── Services ──────────────────────────────────────────────────
    elif key == "services":
        sess["options"] = SERVICES_OPTIONS
        send_menu(phone, "🔧 Services", SERVICES_BODY, SERVICES_OPTIONS, "How can we help?")

    # ── Warranty ──────────────────────────────────────────────────
    elif key == "warranty":
        sess["options"] = WARRANTY_OPTIONS
        send_menu(phone, "🛡️ Warranty", WARRANTY_BODY, WARRANTY_OPTIONS, "What would you like?")

    # ── Loyalty ───────────────────────────────────────────────────
    elif key == "loyalty":
        sess["options"] = LOYALTY_OPTIONS
        send_menu(phone, "⭐ Loyalty Programme", LOYALTY_BODY, LOYALTY_OPTIONS, "What would you like?")

    # ── Warranty detail ────────────────────────────────────────────
    elif key == "warranty_terms":
        back = [("⬅️  Warranty", "warranty"), ("🏠  Main Menu", "main")]
        sess["options"] = back
        send_text_message(phone, WARRANTY_TERMS_MSG)
        send_menu(phone, "↩️ Go back", "What would you like to do next?", back, "Go back")

    elif key == "warranty_register":
        back = [("⬅️  Warranty", "warranty"), ("🏠  Main Menu", "main")]
        sess["options"] = back
        send_text_message(phone, WARRANTY_REGISTER_MSG)
        send_menu(phone, "↩️ Go back", "What would you like to do next?", back, "Go back")

    elif key == "warranty_status":
        back = [("⬅️  Warranty", "warranty"), ("🏠  Main Menu", "main")]
        sess["options"] = back
        send_text_message(phone, WARRANTY_STATUS_MSG)
        send_menu(phone, "↩️ Go back", "What would you like to do next?", back, "Go back")

    # ── Loyalty detail ─────────────────────────────────────────────
    elif key == "loyalty_benefits":
        back = [("⬅️  Loyalty", "loyalty"), ("🏠  Main Menu", "main")]
        sess["options"] = back
        send_text_message(phone, LOYALTY_BENEFITS_MSG)
        send_menu(phone, "↩️ Go back", "What would you like to do next?", back, "Go back")

    elif key == "loyalty_join":
        back = [("⬅️  Loyalty", "loyalty"), ("🏠  Main Menu", "main")]
        sess["options"] = back
        send_text_message(phone, LOYALTY_JOIN_MSG)
        send_menu(phone, "↩️ Go back", "What would you like to do next?", back, "Go back")

    elif key == "loyalty_status":
        back = [("⬅️  Loyalty", "loyalty"), ("🏠  Main Menu", "main")]
        sess["options"] = back
        send_text_message(phone, LOYALTY_STATUS_MSG)
        send_menu(phone, "↩️ Go back", "What would you like to do next?", back, "Go back")

    # ── Service coverage ───────────────────────────────────────────
    elif key == "svc_coverage":
        back = [("⬅️  Services", "services"), ("🏠  Main Menu", "main")]
        sess["options"] = back
        send_text_message(phone, SVC_COVERAGE_MSG)
        send_menu(phone, "↩️ Go back", "What would you like to do next?", back, "Go back")

    elif key == "contact":
        back = [("⬅️  Services", "services"), ("🏠  Main Menu", "main")]
        sess["options"] = back
        send_text_message(phone, CONTACT_MSG)
        send_menu(phone, "↩️ Go back", "What would you like to do next?", back, "Go back")

    # ── Products: category picker ──────────────────────────────────
    elif key == "products":
        sess["options"] = PRODUCT_CAT_OPTIONS
        send_menu(phone, "📦 Browse Products",
                  "Our catalogue spans four categories. Select one to explore:",
                  PRODUCT_CAT_OPTIONS, "Choose a category")

    elif key.startswith("cat:"):
        category = key.split(":", 1)[1]
        opts     = build_product_list_options(category)
        sess["page_header"] = f"📦 {category}"
        sess["page_body"]   = "Select a product to view full specifications and pricing:"
        send_paged_menu(phone, f"📦 {category}",
                        "Select a product to view full specifications and pricing:",
                        opts, sess, 0)

    elif key.startswith("product:"):
        name  = key.split(":", 1)[1]
        all_p = get_all_products()
        p     = next((x for x in all_p if x.get("Product Name") == name), None)
        if p:
            cat  = p.get("_display_category", "Still Lenses")
            back = [(f"⬅️  {cat}", f"cat:{cat}"), ("🏠  Main Menu", "main")]
            sess["options"] = back
            send_text_message(phone, fmt_product_detail(p))
            send_menu(phone, "↩️ Go back", "What would you like to do next?", back, "Go back")
        else:
            send_text_message(phone, "⚠️  Product not found.")

    # ── Pricing ────────────────────────────────────────────────────
    elif key == "prices":
        sess["options"] = PRICE_CAT_OPTIONS
        send_menu(phone, "💰 Sigma India Pricing",
                  "Pricing shown in Indian Rupees (₹). Select a category:",
                  PRICE_CAT_OPTIONS, "Choose a category")

    elif key.startswith("price_cat:"):
        category = key.split(":", 1)[1]
        opts     = build_price_list_options(category)
        sess["page_header"] = f"💰 {category} — Pricing"
        sess["page_body"]   = "Select a product to view its price:"
        send_paged_menu(phone, f"💰 {category} — Pricing",
                        "Select a product to view its price:",
                        opts, sess, 0)

    elif key.startswith("price:"):
        name = key.split(":", 1)[1]
        back = [("⬅️  Back to Pricing", "prices"), ("🏠  Main Menu", "main")]
        sess["options"] = back
        send_text_message(phone, fmt_price_detail(name))
        send_menu(phone, "↩️ Go back", "What would you like to do next?", back, "Go back")

    # ── Dealers ────────────────────────────────────────────────────
    elif key == "dealers":
        sess["options"] = DEALER_REGION_OPTIONS
        send_menu(phone, "🤝 Find a Dealer",
                  "We have authorised dealers across India. Select your region:",
                  DEALER_REGION_OPTIONS, "Choose a region")

    elif key.startswith("dealer_region:"):
        region_key   = key.split(":", 1)[1]
        region_label = DEALER_SHEET_MAP.get(region_key, region_key)
        dealers_data = load_dealers(region_key)
        dealers      = dealers_data.get(region_key, [])
        if not dealers:
            back = [("⬅️  Regions", "dealers"), ("🏠  Main Menu", "main")]
            sess["options"] = back
            send_text_message(
                phone,
                f"🤝 *{region_label}*\n\nNo dealers listed for this region yet.\n"
                f"Visit sigmaindia.in/dealer-network/ for the latest listings.{FOOTER}"
            )
            send_menu(phone, "↩️ Go back", "What would you like to do next?", back, "Go back")
            return
        ctx[f"dealers_{region_key}"] = dealers
        opts = build_dealer_list_options(region_key, dealers)
        sess["page_header"] = f"🤝 {region_label}"
        sess["page_body"]   = "Select a dealer for full contact details:"
        send_paged_menu(phone, f"🤝 {region_label}",
                        "Select a dealer for full contact details:",
                        opts, sess, 0)

    elif key.startswith("dealer:"):
        _, region_key, idx_str = key.split(":", 2)
        idx     = int(idx_str)
        dealers = ctx.get(f"dealers_{region_key}", [])
        if not dealers:
            dealers_data = load_dealers(region_key)
            dealers      = dealers_data.get(region_key, [])
        if 0 <= idx < len(dealers):
            region_label = DEALER_SHEET_MAP.get(region_key, "Region")
            back = [(f"⬅️  {region_label}", f"dealer_region:{region_key}"),
                    ("🏠  Main Menu", "main")]
            sess["options"] = back
            send_text_message(phone, fmt_dealer_detail(dealers[idx]))
            send_menu(phone, "↩️ Go back", "What would you like to do next?", back, "Go back")
        else:
            send_text_message(phone, "⚠️  Dealer not found.")

    # ── Service centres ────────────────────────────────────────────
    elif key == "service":
        centers = load_service_centers()
        ctx["service_centers"] = centers
        opts = build_service_list_options(centers)
        sess["page_header"] = "🔧 Sigma Authorised Service Centres"
        sess["page_body"]   = "Select a centre for contact details:"
        send_paged_menu(phone, "🔧 Sigma Authorised Service Centres",
                        "Select a centre for contact details:",
                        opts, sess, 0)

    elif key.startswith("svc:"):
        idx     = int(key.split(":", 1)[1])
        centers = ctx.get("service_centers") or load_service_centers()
        if 0 <= idx < len(centers):
            back = [("⬅️  All Centres", "service"), ("🏠  Main Menu", "main")]
            sess["options"] = back
            send_text_message(phone, fmt_service_center(centers[idx]))
            send_menu(phone, "↩️ Go back", "What would you like to do next?", back, "Go back")
        else:
            send_text_message(phone, "⚠️  Service centre not found.")

    # ── Search dealer result ───────────────────────────────────────
    elif key.startswith("search_dealer:"):
        idx     = int(key.split(":", 1)[1])
        dealers = ctx.get("search_dealers", [])
        if 0 <= idx < len(dealers):
            back = [("🤝  All Regions", "dealers"), ("🏠  Main Menu", "main")]
            sess["options"] = back
            send_text_message(phone, fmt_dealer_detail(dealers[idx]))
            send_menu(phone, "↩️ Go back", "What would you like to do next?", back, "Go back")

    # ── Fallback ───────────────────────────────────────────────────
    else:
        _send_main_menu(phone, sess)


def handle_text_search(phone: str, user_name: str, body: str, sess: dict):
    low = body.lower()
    ctx = sess.setdefault("context", {})

    # ── Dealer search ──────────────────────────────────────────────
    if any(k in low for k in ["dealer", "buy", "purchase", "shop", "store", "outlet"]):
        dealers = search_dealers_by_query(body, limit=10)
        if dealers:
            ctx["search_dealers"] = dealers
            opts = [(d.get("customer_name", "Dealer")[:24], f"search_dealer:{i}")
                    for i, d in enumerate(dealers)]
            opts.append(("🤝  All Regions", "dealers"))
            opts.append(("🏠  Main Menu",   "main"))
            sess["page_header"] = "🤝 Dealer Search Results"
            sess["page_body"]   = "Select a dealer for full details:"
            send_paged_menu(phone, "🤝 Dealer Search Results",
                            "Select a dealer for full details:", opts, sess, 0)
        else:
            back = [("🤝  Browse by Region", "dealers"), ("🏠  Main Menu", "main")]
            sess["options"] = back
            send_text_message(
                phone,
                f"🤝 No dealers found for *{body}*.\n\n"
                f"Try browsing by region or visit sigmaindia.in/dealer-network/{FOOTER}"
            )
            send_menu(phone, "↩️ Go back", "What would you like to do next?", back, "Go back")
        return

    # ── Service centre search ──────────────────────────────────────
    if any(k in low for k in ["service", "repair", "calibrat"]):
        centers = search_service_centers(body)
        if centers:
            ctx["service_centers"] = centers
            opts = build_service_list_options(centers)
            sess["page_header"] = "🔧 Service Centre Results"
            sess["page_body"]   = "Select a centre for contact details:"
            send_paged_menu(phone, "🔧 Service Centre Results",
                            "Select a centre for contact details:", opts, sess, 0)
        else:
            back = [("🔧  View All Centres", "service"), ("🏠  Main Menu", "main")]
            sess["options"] = back
            send_text_message(phone, f"🔧 No specific matches found.{FOOTER}")
            send_menu(phone, "↩️ Go back", "What would you like to do next?", back, "Go back")
        return

    # ── Product search ─────────────────────────────────────────────
    results = search_products(body, limit=8)
    if results:
        opts = [(p["Product Name"][:24], f"product:{p['Product Name']}") for p in results]
        opts.append(("📋  All Categories", "products"))
        opts.append(("🏠  Main Menu",      "main"))
        sess["page_header"] = f"🔍 Search: {body}"
        sess["page_body"]   = "Select a product for full specifications and pricing:"
        send_paged_menu(phone, f"🔍 Search: {body}",
                        "Select a product for full specifications and pricing:",
                        opts, sess, 0)
        return

    # ── Nothing found ──────────────────────────────────────────────
    send_text_message(
        phone,
        f"🔍 No results found for *{body}*.\n\nTry the main menu or search again.{FOOTER}"
    )
    _send_main_menu(phone, sess)


# ════════════════════════════════════════════════════════════════════
#  TWILIO WEBHOOK
# ════════════════════════════════════════════════════════════════════

@app_flask.route("/whatsapp", methods=["POST"])
def whatsapp_webhook():
    incoming_msg = request.values.get("Body", "").strip()
    from_number  = request.values.get("From", "")
    profile_name = request.values.get("ProfileName", "there")

    log.info(f"MSG from {from_number}: {incoming_msg!r}")

    try:
        process_message(from_number, profile_name, incoming_msg)
        save_session_disk(from_number, profile_name)
    except Exception as e:
        log.exception(f"Error processing message: {e}")
        try:
            send_text_message(
                from_number,
                "⚠️  Something went wrong. Please type *menu* to restart."
            )
        except Exception:
            pass

    # Return empty TwiML — we send messages via REST API directly
    return str(MessagingResponse()), 200, {"Content-Type": "text/xml"}


@app_flask.route("/health", methods=["GET"])
def health():
    return {"status": "ok", "bot": "Sigma WhatsApp Bot"}, 200


# ════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ════════════════════════════════════════════════════════════════════

def main():
    missing = []
    if not ACCOUNT_SID or ACCOUNT_SID == "YOUR_ACCOUNT_SID":
        missing.append("TWILIO_ACCOUNT_SID")
    if not AUTH_TOKEN or AUTH_TOKEN == "YOUR_AUTH_TOKEN":
        missing.append("TWILIO_AUTH_TOKEN")
    if missing:
        print("Missing Twilio credentials in environment or .env file:")
        for m in missing:
            print(f"  {m}")
        print("\nAdd them to your .env file and re-run.")
        sys.exit(1)

    print("=" * 56)
    print("  Sigma AI WhatsApp Bot  (Twilio — Interactive Lists)")
    try:
        print(f"  Products:         {len(get_all_products())}")
        print(f"  Dealers:          {len(get_all_dealers_flat())}")
        print(f"  Service Centres:  {len(load_service_centers())}")
    except Exception as e:
        print(f"  Data load warning: {e}")
    print("=" * 56)
    print("  Webhook URL: POST /whatsapp")
    print("  Health:      GET  /health")
    print("  Running on   http://0.0.0.0:5000")
    print("=" * 56)

    app_flask.run(host="0.0.0.0", port=5000, debug=False)


if __name__ == "__main__":
    main()
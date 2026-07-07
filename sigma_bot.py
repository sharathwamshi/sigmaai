"""
╔══════════════════════════════════════════════════════════════════╗
║           SIGMA AI — Telegram Bot  (v3)                          ║
║   Place this file in the same folder as app.py                  ║
║   Run: python sigma_telegram_bot.py                              ║
╚══════════════════════════════════════════════════════════════════╝

SETUP
─────
1.  pip install "python-telegram-bot>=21.0"
2.  Create bot via @BotFather → copy token
3.  export SIGMA_BOT_TOKEN="your_token_here"
4.  python sigma_telegram_bot.py

DESIGN NOTES
────────────
• Main menu has FOUR entry points: Sales, Services, Warranty, Loyalty.
• Every interaction SENDS A NEW MESSAGE (never edits/deletes a previous
  one), so the conversation reads top-to-bottom like a discussion and
  users can always scroll back through earlier answers.
• Every message ends with the standard footer linking to
  sigmaindia.in and sigmaai.in.
"""

import os, sys, json, logging
from datetime import datetime, timezone
from pathlib import Path

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

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters,
)

# ════════════════════════════════════════════════════════════════════
#  CONFIG
# ════════════════════════════════════════════════════════════════════
BOT_TOKEN     = os.getenv("SIGMA_BOT_TOKEN", "8997906238:AAFzPMgqQDPANRzewP7rmlKIKhfPTWWfVQA")
SESSIONS_PATH = Path(BASE_DIR) / "data" / "telegram_sessions.json"

SIGMA_WEBSITE = "https://sigmaindia.in"
SIGMA_AI      = "https://sigmaai.in"

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)

# ════════════════════════════════════════════════════════════════════
#  CONSTANTS
# ════════════════════════════════════════════════════════════════════
DIV  = "━" * 30
FDIV = "─" * 30

FOOTER = (
    f"\n`{FDIV}`\n"
    f"🌐 [sigmaindia.in]({SIGMA_WEBSITE})  •  🤖 [sigmaai.in]({SIGMA_AI})"
)

# ════════════════════════════════════════════════════════════════════
#  SESSION STORAGE
# ════════════════════════════════════════════════════════════════════
def load_sessions() -> list:
    if SESSIONS_PATH.exists():
        try:
            with open(SESSIONS_PATH) as f:
                return json.load(f)
        except Exception:
            pass
    return []

def save_session(user_id: int, user_info: dict, history: list):
    sessions = load_sessions()
    now = datetime.now(timezone.utc).isoformat()
    for s in sessions:
        if s.get("user_id") == user_id:
            s["history"]    = history[-50:]
            s["updated_at"] = now
            s["user_info"]  = user_info
            _write_sessions(sessions)
            return
    sessions.append({
        "user_id":    user_id,
        "user_info":  user_info,
        "started_at": now,
        "updated_at": now,
        "history":    history,
    })
    _write_sessions(sessions)

def _write_sessions(data: list):
    SESSIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SESSIONS_PATH, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def log_interaction(ctx: ContextTypes.DEFAULT_TYPE, update: Update, text: str):
    user = update.effective_user
    hist = ctx.user_data.setdefault("history", [])
    hist.append({"ts": datetime.now(timezone.utc).isoformat(), "text": text})
    save_session(
        user.id,
        {"id": user.id, "name": user.full_name,
         "username": user.username or "", "lang": user.language_code or ""},
        hist,
    )

# ════════════════════════════════════════════════════════════════════
#  MESSAGE DELIVERY HELPER  (always sends a NEW message)
# ════════════════════════════════════════════════════════════════════
async def send_step(update: Update, ctx: ContextTypes.DEFAULT_TYPE, text: str,
                     reply_markup=None):
    """Send a fresh message — used for both callback queries and plain text,
    so the running conversation is preserved and nothing is edited away."""
    chat_id = update.effective_chat.id
    await ctx.bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode="Markdown",
        reply_markup=reply_markup,
        disable_web_page_preview=True,
    )

# ════════════════════════════════════════════════════════════════════
#  KEYBOARD HELPERS
# ════════════════════════════════════════════════════════════════════
def _btn(label: str, cb: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(label, callback_data=cb)

def _row(*pairs) -> list:
    return [_btn(label, cb) for label, cb in pairs]

def kb(*rows) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(label, callback_data=data) for label, data in row]
        for row in rows
    ])

HOME_ROW = [("🏠  Main Menu", "menu:main")]

# ─── Main menu — four entry points ───────────────────────────────
MAIN_MENU = InlineKeyboardMarkup([
    _row(("🛒  Sales",     "menu:sales"),
         ("🔧  Services",  "menu:services")),
    _row(("🛡️  Warranty",  "menu:warranty"),
         ("⭐  Loyalty",    "menu:loyalty")),
])

# ─── Sales sub-menu ───────────────────────────────────────────────
SALES_MENU = InlineKeyboardMarkup([
    _row(("📦  Browse Products", "menu:products")),
    _row(("💰  View Pricing",    "menu:prices")),
    _row(("🤝  Find a Dealer",   "menu:dealers")),
    _row(*HOME_ROW),
])

# ─── Services sub-menu ────────────────────────────────────────────
SERVICES_MENU = InlineKeyboardMarkup([
    _row(("🔧  Find a Service Centre", "menu:service")),
    _row(("🧰  What We Service",       "svcinfo:coverage")),
    _row(("📞  Contact Support",       "menu:contact")),
    _row(*HOME_ROW),
])

# ─── Warranty sub-menu ────────────────────────────────────────────
WARRANTY_MENU = InlineKeyboardMarkup([
    _row(("📜  Warranty Terms",        "warranty:terms")),
    _row(("📝  Register Your Product", "warranty:register")),
    _row(("🔍  Check Warranty Status", "warranty:status")),
    _row(*HOME_ROW),
])

# ─── Loyalty sub-menu ─────────────────────────────────────────────
LOYALTY_MENU = InlineKeyboardMarkup([
    _row(("🎁  Member Benefits",   "loyalty:benefits")),
    _row(("➕  How to Join",       "loyalty:join")),
    _row(("📈  My Loyalty Status", "loyalty:status")),
    _row(*HOME_ROW),
])

# ─── Products sub-menu (category picker) ─────────────────────────
def products_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        _row(("📷  Still Lenses",   "cat:Still Lenses"),
             ("🎬  Cine Lenses",    "cat:Cine Lenses")),
        _row(("📸  Cameras",        "cat:Cameras"),
             ("🎒  Accessories",    "cat:Accessories")),
        _row(("⬅️  Sales", "menu:sales"), HOME_ROW[0]),
    ])

def products_in_category_kb(category: str) -> InlineKeyboardMarkup:
    key_map = {
        "Still Lenses": "still_lenses", "Cine Lenses": "cine_lenses",
        "Cameras": "cameras",           "Accessories": "accessories",
    }
    items = load_products().get(key_map.get(category, "still_lenses"), [])
    rows  = [_row((f"  {p['Product Name'][:42]}", f"product:{p['Product Name']}"))
             for p in items[:20]]
    rows.append(_row(("⬅️  Categories", "menu:products"), ("🏠  Main Menu", "menu:main")))
    return InlineKeyboardMarkup(rows)

def prices_category_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        _row(("📷  Still Lenses",   "price_cat:Still Lenses"),
             ("🎬  Cine Lenses",    "price_cat:Cine Lenses")),
        _row(("📸  Cameras",        "price_cat:Cameras"),
             ("🎒  Accessories",    "price_cat:Accessories")),
        _row(("⬅️  Sales", "menu:sales"), HOME_ROW[0]),
    ])

def prices_list_kb(category: str) -> InlineKeyboardMarkup:
    key_map = {
        "Still Lenses": "still_lenses", "Cine Lenses": "cine_lenses",
        "Cameras": "cameras",           "Accessories": "accessories",
    }
    items = load_products().get(key_map.get(category, "still_lenses"), [])
    rows  = [_row((f"₹  {p['Product Name'][:42]}", f"price:{p['Product Name']}"))
             for p in items[:20]]
    rows.append(_row(("⬅️  Pricing", "menu:prices"), ("🏠  Main Menu", "menu:main")))
    return InlineKeyboardMarkup(rows)

def dealer_regions_kb() -> InlineKeyboardMarkup:
    REGION_ICONS = {
        "chn": "🔴", "del": "🟠", "klr": "🟢",
        "klt": "🔵", "bng": "🟣", "mum": "🟡", "tel": "⚪",
    }
    rows = [_row((f"{REGION_ICONS.get(k, '📍')}  {label}", f"dealer_region:{k}"))
            for k, label in DEALER_SHEET_MAP.items()]
    rows.append(_row(("⬅️  Sales", "menu:sales"), ("🏠  Main Menu", "menu:main")))
    return InlineKeyboardMarkup(rows)

def dealer_list_kb(region_key: str, dealers: list) -> InlineKeyboardMarkup:
    rows = [_row((f"🏪  {d.get('customer_name', 'Dealer')[:38]}", f"dealer:{region_key}:{i}"))
            for i, d in enumerate(dealers[:15])]
    rows.append(_row(("⬅️  Regions", "menu:dealers"), ("🏠  Main Menu", "menu:main")))
    return InlineKeyboardMarkup(rows)

def service_list_kb(centers: list) -> InlineKeyboardMarkup:
    rows = [_row((f"🔧  {c.get('name', 'Centre')[:38]}", f"svc:{i}"))
            for i, c in enumerate(centers)]
    rows.append(_row(("⬅️  Services", "menu:services"), ("🏠  Main Menu", "menu:main")))
    return InlineKeyboardMarkup(rows)

# ════════════════════════════════════════════════════════════════════
#  CONTENT — discussion-style introductions for each top-level area
# ════════════════════════════════════════════════════════════════════
def build_welcome(user_name: str) -> str:
    cfg      = load_config()
    brand    = cfg.get("brand_name", "Sigma AI Assistant")
    products = get_all_products()
    dealers  = get_all_dealers_flat()
    svc      = load_service_centers()
    return (
        f"👋 *Welcome, {user_name}!*\n\n"
        f"I'm the *{brand}* — your dedicated guide for everything related to "
        f"Sigma in India. I can help you explore products and pricing, locate "
        f"dealers and service centres, understand your warranty, and learn "
        f"about our loyalty programme.\n"
        f"`{DIV}`\n"
        f"📦  *{len(products)}* products in our catalogue\n"
        f"🤝  *{len(dealers)}+* authorised dealers across India\n"
        f"🔧  *{len(svc)}* authorised service centres\n"
        f"`{DIV}`\n"
        f"Please choose a topic below to get started:"
        f"{FOOTER}"
    )

def sales_intro() -> str:
    products = get_all_products()
    dealers  = get_all_dealers_flat()
    return (
        f"🛒 *Sales*\n"
        f"`{DIV}`\n"
        f"Whether you're choosing your first Sigma lens or expanding a "
        f"professional kit, this is the right place to start. Our catalogue "
        f"spans *{len(products)} products* across Still Lenses, Cine Lenses, "
        f"Cameras, and Accessories — each engineered to Sigma's exacting "
        f"standards for optical performance and build quality.\n\n"
        f"You can browse the full range by category, check current Indian "
        f"pricing for any product, or find your nearest authorised dealer "
        f"from our network of *{len(dealers)}+ dealers* across the country "
        f"for a hands-on look and the best possible advice before you buy.\n\n"
        f"What would you like to do?"
        f"{FOOTER}"
    )

def services_intro() -> str:
    centers = load_service_centers()
    return (
        f"🔧 *Services*\n"
        f"`{DIV}`\n"
        f"Sigma equipment is built to last, and our authorised service "
        f"network is here to keep it performing at its best. With "
        f"*{len(centers)} authorised service centres* across India, you can "
        f"get warranty repairs, out-of-warranty servicing, firmware updates, "
        f"and precision sensor or optical calibration — all carried out by "
        f"technicians trained to Sigma's standards using genuine parts.\n\n"
        f"If you're experiencing an issue with a lens, camera, or accessory, "
        f"start by finding the service centre nearest to you. For general "
        f"questions about turnaround times or repair costs, our support team "
        f"is happy to help.\n\n"
        f"How can we assist you today?"
        f"{FOOTER}"
    )

def warranty_intro() -> str:
    return (
        f"🛡️ *Warranty*\n"
        f"`{DIV}`\n"
        f"Every Sigma product sold through our authorised channels in India "
        f"is backed by a manufacturer's warranty covering manufacturing "
        f"defects in materials and workmanship. Registering your product "
        f"shortly after purchase ensures your coverage is recorded correctly "
        f"and helps us serve you faster if you ever need a repair.\n\n"
        f"Below you'll find an overview of our warranty terms, a link to "
        f"register a new purchase, and a way to check the status of an "
        f"existing warranty claim. If anything is unclear, our support team "
        f"is always available to walk you through it.\n\n"
        f"What would you like to know?"
        f"{FOOTER}"
    )

def loyalty_intro() -> str:
    return (
        f"⭐ *Loyalty Programme*\n"
        f"`{DIV}`\n"
        f"We created the Sigma Loyalty Programme to recognise customers who "
        f"choose Sigma as part of their long-term creative journey. As a "
        f"member, you gain access to exclusive offers, priority service "
        f"scheduling, early access to new product launches, and trade-up "
        f"benefits when you're ready to upgrade your gear.\n\n"
        f"Joining is simple and free for owners of registered Sigma "
        f"products. Take a look at the benefits below, find out how to "
        f"enrol, or check the status of your existing membership.\n\n"
        f"Let's get started:"
        f"{FOOTER}"
    )

# ════════════════════════════════════════════════════════════════════
#  WARRANTY / LOYALTY / SERVICE-INFO — detail content
# ════════════════════════════════════════════════════════════════════
WARRANTY_TERMS_MSG = (
    f"📜 *Warranty Terms*\n"
    f"`{DIV}`\n"
    f"Here's a clear summary of how Sigma's warranty coverage works in "
    f"India:\n\n"
    f"• *Coverage period:* Sigma products carry a standard manufacturer's "
    f"warranty against defects in materials and workmanship from the date "
    f"of purchase from an authorised dealer.\n\n"
    f"• *What's covered:* Manufacturing faults — for example, focusing "
    f"mechanisms, electronic contacts, or build issues that arise under "
    f"normal use.\n\n"
    f"• *What's not covered:* Accidental damage, water damage, unauthorised "
    f"repairs or modifications, and normal wear and tear are outside the "
    f"scope of the standard warranty.\n\n"
    f"• *Proof of purchase:* Always keep your original invoice from an "
    f"authorised dealer — it's the primary document needed to validate any "
    f"warranty claim.\n\n"
    f"For the complete, up-to-date terms and conditions, please refer to "
    f"the warranty documentation included with your product or visit our "
    f"website."
    f"{FOOTER}"
)

WARRANTY_REGISTER_MSG = (
    f"📝 *Register Your Product*\n"
    f"`{DIV}`\n"
    f"Registering your Sigma product takes just a couple of minutes and "
    f"brings real benefits: it creates a digital record of your purchase "
    f"date and dealer, speeds up any future service visit, and keeps you "
    f"informed about firmware updates relevant to your gear.\n\n"
    f"To register, you'll typically need:\n"
    f"• Your product's serial number (found on the barcode label or lens "
    f"barrel)\n"
    f"• A copy or photo of your purchase invoice\n"
    f"• Your contact details\n\n"
    f"You can complete registration through the official Sigma India "
    f"product registration page on our website."
    f"{FOOTER}"
)

WARRANTY_STATUS_MSG = (
    f"🔍 *Check Warranty Status*\n"
    f"`{DIV}`\n"
    f"If you've already registered your product or raised a service "
    f"request, you can check where things stand at any time.\n\n"
    f"To check your warranty or repair status, please have the following "
    f"ready:\n"
    f"• Product serial number\n"
    f"• Service request / job sheet number (if a repair is in progress)\n"
    f"• The mobile number or email used at registration\n\n"
    f"Our support team can look this up for you directly, or you can use "
    f"the warranty status lookup on our website."
    f"{FOOTER}"
)

LOYALTY_BENEFITS_MSG = (
    f"🎁 *Member Benefits*\n"
    f"`{DIV}`\n"
    f"As a Sigma Loyalty member, you'll enjoy a set of benefits designed "
    f"around how photographers and filmmakers actually work and grow their "
    f"kit over time:\n\n"
    f"• *Exclusive offers:* Members-only pricing and bundle deals on "
    f"selected lenses, cameras, and accessories.\n\n"
    f"• *Priority service:* Faster turnaround at authorised service "
    f"centres for registered members.\n\n"
    f"• *Early access:* Be among the first to know about new product "
    f"launches and firmware releases.\n\n"
    f"• *Trade-up assistance:* Preferential terms when upgrading from one "
    f"Sigma lens or body to another.\n\n"
    f"• *Dedicated support:* A direct line to our team for membership and "
    f"product-related queries.\n\n"
    f"Benefits may vary by membership tier — full details are available on "
    f"our website."
    f"{FOOTER}"
)

LOYALTY_JOIN_MSG = (
    f"➕ *How to Join*\n"
    f"`{DIV}`\n"
    f"Joining the Sigma Loyalty Programme is free for owners of registered "
    f"Sigma products purchased through an authorised dealer in India.\n\n"
    f"Here's how it works:\n"
    f"1. *Register* at least one Sigma product (see the Warranty section "
    f"for product registration).\n"
    f"2. *Enrol* in the Loyalty Programme using your registered details on "
    f"our website.\n"
    f"3. *Activate* — once verified, your membership benefits become "
    f"active and you'll receive a confirmation.\n\n"
    f"If you've recently purchased a Sigma product and haven't registered "
    f"it yet, that's the best place to start."
    f"{FOOTER}"
)

LOYALTY_STATUS_MSG = (
    f"📈 *My Loyalty Status*\n"
    f"`{DIV}`\n"
    f"To check your current membership tier, points balance, or active "
    f"offers, please have the following ready:\n\n"
    f"• The mobile number or email used during enrolment\n"
    f"• Your membership ID (sent to you at sign-up, if applicable)\n\n"
    f"Our support team can verify your status directly, or you can log in "
    f"to your account on the loyalty section of our website to view your "
    f"dashboard."
    f"{FOOTER}"
)

SERVICE_COVERAGE_MSG = (
    f"🧰 *What We Service*\n"
    f"`{DIV}`\n"
    f"Our authorised service centres are equipped to handle the full range "
    f"of Sigma equipment, including:\n\n"
    f"• *Lenses:* Focus mechanism repairs, aperture and electronic contact "
    f"issues, optical element cleaning and replacement, mount repairs, and "
    f"image stabilisation (OS) servicing.\n\n"
    f"• *Cameras:* Sensor cleaning and calibration, firmware updates, "
    f"button and dial repairs, and general diagnostics.\n\n"
    f"• *Calibration:* Precision autofocus calibration to ensure your lens "
    f"performs accurately on your specific camera body.\n\n"
    f"• *Firmware:* Updates to keep your gear compatible with the latest "
    f"camera bodies and features.\n\n"
    f"All work is carried out using genuine Sigma parts. For an estimate or "
    f"to book a service, please get in touch with your nearest centre."
    f"{FOOTER}"
)

# ════════════════════════════════════════════════════════════════════
#  MESSAGE FORMATTERS (products / prices / dealers / service)
# ════════════════════════════════════════════════════════════════════
def fmt_product_detail(p: dict) -> str:
    name     = p.get("Product Name", "—")
    cat      = p.get("_display_category", "")
    line     = p.get("Product Line", p.get("Category", ""))
    fl       = p.get("Focal Length", "")
    ap       = p.get("Max Aperture", p.get("T-Stop", ""))
    mounts   = p.get("Available Mounts", p.get("Compatibility", ""))
    features = p.get("Key Features", "")
    price    = p.get("_price_inr", get_price_inr(name))
    pr_range = p.get("_price_range_inr", get_price_range_inr(name))

    lines = [f"📦 *{name}*"]
    if cat or line:
        lines.append(f"_{cat}{'  •  ' if cat and line else ''}{line}_")
    lines.append(f"`{DIV}`")
    if fl:       lines.append(f"🔭  *Focal Length:*  {fl}")
    if ap:       lines.append(f"🔆  *Aperture:*  {ap}")
    if mounts:   lines.append(f"🔩  *Mounts:*  {mounts}")
    if features: lines.append(f"\n✨  *Key Features*\n{features}")
    lines.append(f"`{DIV}`")
    lines.append(f"💰  *Price (India):*  {price}")
    if pr_range: lines.append(f"📊  *Range:*  {pr_range}")
    lines.append(
        f"\n🛒  [Buy on Amazon India](https://www.amazon.in/s?k=Sigma+{name.replace(' ','+')})"
        f"\n🔵  [Search on Flipkart](https://www.flipkart.com/search?q=Sigma+{name.replace(' ','+')})"
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
        f"💰 *{name}*\n"
        f"`{DIV}`\n"
        f"🇮🇳  *Sigma India Price:*  {price}\n"
        f"📊  *Price Range:*  {pr_range or '—'}\n"
        f"🌐  *USD Price:*  ${usd:,}\n"
        f"🔍  *Source:*  {source}\n"
        f"`{DIV}`\n"
        f"_Prices are indicative. Contact your nearest dealer for final pricing._\n"
        f"\n🛒  [Amazon India](https://www.amazon.in/s?k=Sigma+{name.replace(' ','+')})"
        f"  •  🔵  [Flipkart](https://www.flipkart.com/search?q=Sigma+{name.replace(' ','+')})"
        f"{FOOTER}"
    )

def fmt_dealer_detail(d: dict) -> str:
    f = format_dealer_for_chat(d)
    lines = [
        f"🏪 *{f.get('name', '—')}*",
        f"✅  _Authorised Sigma Dealer_",
        f"`{DIV}`",
        f"📍  *Location:*  {f.get('location', '')}",
    ]
    if f.get("address"):      lines.append(f"🗺️  *Address:*  {f['address']}")
    if f.get("dealer_code"):  lines.append(f"🆔  *Dealer Code:*  `{f['dealer_code']}`")
    if f.get("sales_person"): lines.append(f"👤  *Sales Contact:*  {f['sales_person']}")
    lines.append(FOOTER)
    return "\n".join(l for l in lines if l)

def fmt_service_center(c: dict) -> str:
    f = format_service_center_for_chat(c)
    lines = [
        f"🔧 *{f.get('name', '—')}*",
        f"✅  _Authorised Sigma Service Centre_",
        f"`{DIV}`",
        f"📍  *Location:*  {f.get('location', '')}",
        f"🗺️  *Address:*  {f.get('address', '')}",
        f"📞  *Phone:*  {f.get('phone', '—')}",
        f"📧  *Email:*  {f.get('email', '—')}",
    ]
    lines.append(FOOTER)
    return "\n".join(l for l in lines if l)

CONTACT_MSG = (
    f"📞 *Contact Sigma India*\n"
    f"`{DIV}`\n"
    f"📧  *General Enquiries:*  info@sigmaindia.in\n"
    f"🔧  *Service Support:*  [Submit a Request]({SIGMA_WEBSITE}/service-support/)\n"
    f"🤝  *Dealer Network:*  [Find Dealers]({SIGMA_WEBSITE}/dealer-network/)\n"
    f"`{DIV}`\n"
    f"🕐  *Business Hours:*  Mon – Sat,  9 AM – 6 PM IST\n"
    f"_Our team typically responds within 2 business hours._"
    f"{FOOTER}"
)

# ════════════════════════════════════════════════════════════════════
#  COMMAND HANDLERS
# ════════════════════════════════════════════════════════════════════
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    log_interaction(ctx, update, "/start")
    await send_step(update, ctx, build_welcome(user.first_name), MAIN_MENU)

async def cmd_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    log_interaction(ctx, update, "/menu")
    await send_step(
        update, ctx,
        f"🏠 *Main Menu*\n`{DIV}`\nHow can I help you today? Choose a topic below:"
        f"{FOOTER}",
        MAIN_MENU,
    )

async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    log_interaction(ctx, update, "/help")
    await send_step(
        update, ctx,
        f"ℹ️ *Sigma AI Bot — Help*\n"
        f"`{DIV}`\n"
        f"*Available Commands:*\n"
        f"  /start  — Welcome & main menu\n"
        f"  /menu   — Go to main menu\n"
        f"  /help   — This message\n"
        f"`{DIV}`\n"
        f"You can also *type any query* — search for products, dealers, or "
        f"service centres by name or city.\n\n"
        f"_Example:_ `dealers in Chennai`  or  `50mm lens`"
        f"{FOOTER}",
        kb(HOME_ROW),
    )

# ════════════════════════════════════════════════════════════════════
#  CALLBACK ROUTER
# ════════════════════════════════════════════════════════════════════
async def handle_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q    = update.callback_query
    data = q.data
    await q.answer()
    log_interaction(ctx, update, f"cb:{data}")

    # ── Main menu ────────────────────────────────────────────────
    if data == "menu:main":
        await send_step(update, ctx, build_welcome(update.effective_user.first_name), MAIN_MENU)

    # ── Top-level: Sales ─────────────────────────────────────────
    elif data == "menu:sales":
        await send_step(update, ctx, sales_intro(), SALES_MENU)

    # ── Top-level: Services ─────────────────────────────────────
    elif data == "menu:services":
        await send_step(update, ctx, services_intro(), SERVICES_MENU)

    # ── Top-level: Warranty ──────────────────────────────────────
    elif data == "menu:warranty":
        await send_step(update, ctx, warranty_intro(), WARRANTY_MENU)

    # ── Top-level: Loyalty ───────────────────────────────────────
    elif data == "menu:loyalty":
        await send_step(update, ctx, loyalty_intro(), LOYALTY_MENU)

    # ── Warranty detail screens ──────────────────────────────────
    elif data == "warranty:terms":
        await send_step(update, ctx, WARRANTY_TERMS_MSG,
                         kb([("⬅️  Warranty", "menu:warranty")], HOME_ROW))

    elif data == "warranty:register":
        await send_step(update, ctx, WARRANTY_REGISTER_MSG,
                         kb([("⬅️  Warranty", "menu:warranty")], HOME_ROW))

    elif data == "warranty:status":
        await send_step(update, ctx, WARRANTY_STATUS_MSG,
                         kb([("⬅️  Warranty", "menu:warranty")], HOME_ROW))

    # ── Loyalty detail screens ───────────────────────────────────
    elif data == "loyalty:benefits":
        await send_step(update, ctx, LOYALTY_BENEFITS_MSG,
                         kb([("⬅️  Loyalty", "menu:loyalty")], HOME_ROW))

    elif data == "loyalty:join":
        await send_step(update, ctx, LOYALTY_JOIN_MSG,
                         kb([("⬅️  Loyalty", "menu:loyalty")], HOME_ROW))

    elif data == "loyalty:status":
        await send_step(update, ctx, LOYALTY_STATUS_MSG,
                         kb([("⬅️  Loyalty", "menu:loyalty")], HOME_ROW))

    # ── Service info screen ──────────────────────────────────────
    elif data == "svcinfo:coverage":
        await send_step(update, ctx, SERVICE_COVERAGE_MSG,
                         kb([("⬅️  Services", "menu:services")], HOME_ROW))

    # ── Products → category picker ────────────────────────────────
    elif data == "menu:products":
        products = get_all_products()
        await send_step(
            update, ctx,
            f"📦 *Browse Products*\n"
            f"`{DIV}`\n"
            f"Our catalogue includes *{len(products)} products* across four "
            f"categories. Select one to explore:"
            f"{FOOTER}",
            products_menu_kb(),
        )

    # ── Category → product list ───────────────────────────────────
    elif data.startswith("cat:"):
        category = data.split(":", 1)[1]
        key_map  = {
            "Still Lenses": "still_lenses", "Cine Lenses": "cine_lenses",
            "Cameras": "cameras",           "Accessories": "accessories",
        }
        count = len(load_products().get(key_map.get(category, ""), []))
        await send_step(
            update, ctx,
            f"📦 *{category}*\n"
            f"`{DIV}`\n"
            f"*{count} products* available.\n"
            f"Select a product to view full specifications and pricing:"
            f"{FOOTER}",
            products_in_category_kb(category),
        )

    # ── Single product detail ─────────────────────────────────────
    elif data.startswith("product:"):
        name  = data.split(":", 1)[1]
        all_p = get_all_products()
        p     = next((x for x in all_p if x.get("Product Name") == name), None)
        if p:
            cat_key = p.get("_display_category", "Still Lenses")
            await send_step(
                update, ctx, fmt_product_detail(p),
                kb([(f"⬅️  {cat_key}", f"cat:{cat_key}")], HOME_ROW),
            )

    # ── Pricing → category picker ─────────────────────────────────
    elif data == "menu:prices":
        total = len(PRICE_USD)
        await send_step(
            update, ctx,
            f"💰 *Sigma India Pricing*\n"
            f"`{DIV}`\n"
            f"Pricing is available for *{total} products*, shown in Indian "
            f"Rupees (₹). Select a category to view pricing:"
            f"{FOOTER}",
            prices_category_kb(),
        )

    elif data.startswith("price_cat:"):
        category = data.split(":", 1)[1]
        key_map  = {
            "Still Lenses": "still_lenses", "Cine Lenses": "cine_lenses",
            "Cameras": "cameras",           "Accessories": "accessories",
        }
        count = len(load_products().get(key_map.get(category, ""), []))
        await send_step(
            update, ctx,
            f"💰 *{category} — Pricing*\n"
            f"`{DIV}`\n"
            f"*{count} products* in this category. Select a product to view "
            f"its price:"
            f"{FOOTER}",
            prices_list_kb(category),
        )

    # ── Single price detail ───────────────────────────────────────
    elif data.startswith("price:"):
        name = data.split(":", 1)[1]
        await send_step(
            update, ctx, fmt_price_detail(name),
            kb([("⬅️  Back to Pricing", "menu:prices")], HOME_ROW),
        )

    # ── Dealer regions ────────────────────────────────────────────
    elif data == "menu:dealers":
        total = len(get_all_dealers_flat())
        await send_step(
            update, ctx,
            f"🤝 *Find a Dealer*\n"
            f"`{DIV}`\n"
            f"We work with *{total}+ authorised dealers* across India who "
            f"can help you choose, demo, and purchase Sigma products. "
            f"Select your region:"
            f"{FOOTER}",
            dealer_regions_kb(),
        )

    elif data.startswith("dealer_region:"):
        region_key   = data.split(":", 1)[1]
        region_label = DEALER_SHEET_MAP.get(region_key, region_key)
        dealers_data = load_dealers(region_key)
        dealers      = dealers_data.get(region_key, [])
        if not dealers:
            await send_step(
                update, ctx,
                f"🤝 *{region_label}*\n\n"
                f"No dealers are listed for this region yet. Please visit "
                f"[sigmaindia.in/dealer-network/]({SIGMA_WEBSITE}/dealer-network/) "
                f"for the latest listings."
                f"{FOOTER}",
                kb([("⬅️  Regions", "menu:dealers")], HOME_ROW),
            )
            return
        ctx.user_data[f"dealers_{region_key}"] = dealers
        await send_step(
            update, ctx,
            f"🤝 *{region_label}*\n"
            f"`{DIV}`\n"
            f"*{len(dealers)} authorised dealers* in this region. Select one "
            f"for full contact details:"
            f"{FOOTER}",
            dealer_list_kb(region_key, dealers),
        )

    elif data.startswith("dealer:"):
        _, region_key, idx_str = data.split(":", 2)
        idx     = int(idx_str)
        dealers = ctx.user_data.get(f"dealers_{region_key}", [])
        if not dealers:
            dealers_data = load_dealers(region_key)
            dealers      = dealers_data.get(region_key, [])
        if 0 <= idx < len(dealers):
            await send_step(
                update, ctx, fmt_dealer_detail(dealers[idx]),
                kb([(f"⬅️  {DEALER_SHEET_MAP.get(region_key, 'Region')}",
                     f"dealer_region:{region_key}")], HOME_ROW),
            )

    # ── Service centres ───────────────────────────────────────────
    elif data == "menu:service":
        centers = load_service_centers()
        ctx.user_data["service_centers"] = centers
        await send_step(
            update, ctx,
            f"🔧 *Sigma Authorised Service Centres*\n"
            f"`{DIV}`\n"
            f"*{len(centers)} service centres* across India are fully "
            f"authorised for warranty repairs, out-of-warranty servicing, "
            f"and sensor or optical calibration.\n\n"
            f"Select a centre for contact details:"
            f"{FOOTER}",
            service_list_kb(centers),
        )

    elif data.startswith("svc:"):
        idx     = int(data.split(":", 1)[1])
        centers = ctx.user_data.get("service_centers") or load_service_centers()
        if 0 <= idx < len(centers):
            await send_step(
                update, ctx, fmt_service_center(centers[idx]),
                kb([("⬅️  All Centres", "menu:service")], HOME_ROW),
            )

    # ── Contact ───────────────────────────────────────────────────
    elif data == "menu:contact":
        await send_step(
            update, ctx, CONTACT_MSG,
            kb([("⬅️  Services", "menu:services")], HOME_ROW),
        )

# ════════════════════════════════════════════════════════════════════
#  PLAIN TEXT — SMART SEARCH
# ════════════════════════════════════════════════════════════════════
async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message.text.strip()
    low = msg.lower()
    log_interaction(ctx, update, msg)

    # ── Dealer search ─────────────────────────────────────────────
    if any(k in low for k in ["dealer", "buy", "purchase", "shop", "store", "outlet"]):
        dealers = search_dealers_by_query(msg, limit=10)
        if dealers:
            ctx.user_data["search_dealers"] = dealers
            rows = [_row((f"🏪  {d.get('customer_name', 'Dealer')[:38]}", f"search_dealer:{i}"))
                    for i, d in enumerate(dealers)]
            rows.append(_row(("🤝  All Regions", "menu:dealers"), ("🏠  Main Menu", "menu:main")))
            await send_step(
                update, ctx,
                f"🤝 *Dealers — Search Results*\n"
                f"`{DIV}`\n"
                f"Found *{len(dealers)} authorised dealer(s)* matching your "
                f"query. Select one for full details:"
                f"{FOOTER}",
                InlineKeyboardMarkup(rows),
            )
        else:
            await send_step(
                update, ctx,
                f"🤝 No dealers found for *{msg}*.\n\n"
                f"Try browsing by region or visit "
                f"[sigmaindia.in/dealer-network/]({SIGMA_WEBSITE}/dealer-network/)."
                f"{FOOTER}",
                kb([("🤝  Browse by Region", "menu:dealers")], HOME_ROW),
            )
        return

    # ── Service centre search ─────────────────────────────────────
    if any(k in low for k in ["service", "repair", "warranty", "calibrat"]):
        centers = search_service_centers(msg)
        if centers:
            ctx.user_data["service_centers"] = centers
            rows = [_row((f"🔧  {c.get('name', 'Centre')[:38]}", f"svc:{i}"))
                    for i, c in enumerate(centers)]
            rows.append(_row(("🏠  Main Menu", "menu:main")))
            await send_step(
                update, ctx,
                f"🔧 *Service Centres — Search Results*\n"
                f"`{DIV}`\n"
                f"Found *{len(centers)} centre(s)* matching your query. "
                f"Select one for contact details:"
                f"{FOOTER}",
                InlineKeyboardMarkup(rows),
            )
        else:
            await send_step(
                update, ctx,
                f"🔧 No specific matches. Browse all authorised service "
                f"centres below:"
                f"{FOOTER}",
                kb([("🔧  View All Centres", "menu:service")], HOME_ROW),
            )
        return

    # ── Product search ────────────────────────────────────────────
    results = search_products(msg, limit=8)
    if results:
        rows = [_row((f"📦  {p['Product Name'][:42]}", f"product:{p['Product Name']}"))
                for p in results]
        rows.append(_row(("📋  All Categories", "menu:products"), ("🏠  Main Menu", "menu:main")))
        await send_step(
            update, ctx,
            f"🔍 *Search Results for:* _{msg}_\n"
            f"`{DIV}`\n"
            f"Found *{len(results)} product(s)* matching your query. Select "
            f"one for full specifications and pricing:"
            f"{FOOTER}",
            InlineKeyboardMarkup(rows),
        )
    else:
        await send_step(
            update, ctx,
            f"🔍 No results found for *{msg}*.\n\n"
            f"Try browsing the full catalogue or refine your search:"
            f"{FOOTER}",
            MAIN_MENU,
        )

# ── Search dealer result callback ─────────────────────────────────
async def handle_search_dealer_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q   = update.callback_query
    idx = int(q.data.split(":", 1)[1])
    await q.answer()
    log_interaction(ctx, update, f"cb:{q.data}")
    dealers = ctx.user_data.get("search_dealers", [])
    if 0 <= idx < len(dealers):
        await send_step(
            update, ctx, fmt_dealer_detail(dealers[idx]),
            kb([("🏠  Main Menu", "menu:main")]),
        )

# ════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ════════════════════════════════════════════════════════════════════
def main():
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("Set your bot token: export SIGMA_BOT_TOKEN='your_token'")
        sys.exit(1)

    print("=" * 56)
    print("  Sigma AI Telegram Bot  (v3)")
    try:
        print(f"  Products:         {len(get_all_products())}")
        print(f"  Dealers:          {len(get_all_dealers_flat())}")
        print(f"  Service Centres:  {len(load_service_centers())}")
    except Exception as e:
        print(f"  Data load warning: {e}")
    print("=" * 56)

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .arbitrary_callback_data(False)
        .build()
    )

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("menu",  cmd_menu))
    app.add_handler(CommandHandler("help",  cmd_help))
    app.add_handler(CallbackQueryHandler(
        handle_search_dealer_cb, pattern=r"^search_dealer:\d+$"
    ))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND, handle_text
    ))

    print("  Bot is running — press Ctrl+C to stop")
    app.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
    )

if __name__ == "__main__":
    main()
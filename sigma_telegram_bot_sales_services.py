"""
╔══════════════════════════════════════════════════════════════════╗
║           SIGMA AI — Telegram Bot                                ║
║   Place this file in the same folder as app.py                  ║
║   Run: python sigma_telegram_bot.py                              ║
╚══════════════════════════════════════════════════════════════════╝

SETUP
─────
1.  pip install "python-telegram-bot>=21.0"   (v21+ / v22+ both supported)
2.  Create bot via @BotFather → copy token
3.  Set env var:  export SIGMA_BOT_TOKEN="your_token_here"
    OR edit BOT_TOKEN below directly
4.  python sigma_telegram_bot.py
"""

import os, sys, json, logging, asyncio
from datetime import datetime, timezone
from pathlib import Path

# ── Import all data functions directly from your app.py ─────────────
sys.path.insert(0, os.path.dirname(__file__))
from app6 import (
    # Products
    get_all_products, search_products, load_products,
    # Prices
    load_prices, PRICE_USD, get_price_inr, get_price_range_inr,
    fmt_inr, fmt_inr_range,
    # Dealers
    load_dealers, get_all_dealers_flat, search_dealers_by_query,
    format_dealer_for_chat, DEALER_SHEET_MAP,
    # Service Centers
    load_service_centers, search_service_centers, format_service_center_for_chat,
    # Config
    load_config,
    # Paths
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
BOT_TOKEN = os.getenv("SIGMA_BOT_TOKEN", "8997906238:AAFzPMgqQDPANRzewP7rmlKIKhfPTWWfVQA")

# Session storage — saved next to your existing data/ folder
SESSIONS_PATH = Path(BASE_DIR) / "data" / "telegram_sessions.json"

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO
)
log = logging.getLogger(__name__)

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
            s["history"]    = history[-50:]   # keep last 50 interactions
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
    user  = update.effective_user
    hist  = ctx.user_data.setdefault("history", [])
    hist.append({"ts": datetime.now(timezone.utc).isoformat(), "text": text})
    save_session(
        user.id,
        {"id": user.id, "name": user.full_name,
         "username": user.username or "", "lang": user.language_code or ""},
        hist,
    )

# ════════════════════════════════════════════════════════════════════
#  KEYBOARD HELPERS
# ════════════════════════════════════════════════════════════════════
def kb(*rows) -> InlineKeyboardMarkup:
    """rows = list of lists of (label, callback_data)"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(label, callback_data=data) for label, data in row]
        for row in rows
    ])

# ── Static menus ──────────────────────────────────────────────────
MAIN_MENU = kb(
    [("🔭  Browse Products",    "menu:products"),
     ("💰  Pricing",            "menu:prices")],
    [("🤝  Find a Dealer",      "menu:dealers"),
     ("🔧  Service Centres",    "menu:service")],
    [("📋  Product Categories", "menu:categories"),
     ("📞  Contact Sigma",      "menu:contact")],
)




# ── Smart Conversational Onboarding ─────────────────────────────
ONBOARDING_QUESTIONS = {
    "purpose": {
        "question": F"🎯 *Question 1 of 3* \n"

        "What can I help you with today?",
        "options": [
            ("🛍 Sales", "sales"),
            ("🔧 Services", "services"),
        ],
    },
    "sales_need": {
        "question": f"🛍 *Question 2 of 3* \n"

        "What are you looking for?",
        "options": [
            ("📦 Products & Prices", "products_prices"),
            ("🤝 Find Dealer", "find_dealer"),
        ],
    },
    "service_need": {
        "question": f"🔧 *Question 2 of 3* \n"

        "How can we assist you?",
        "options": [
            ("🛠 Service Centres", "service_centres"),
            ("📞 Contact Sigma", "contact_sigma"),
        ],
    },
    "location": {
        "question": f"📍 *Question 3 of 3* \n"

        "Which city are you located in?",
        "options": [
            ("🌆 Bangalore", "Bangalore"),
            ("🏙 Chennai", "Chennai"),
            ("🌃 Mumbai", "Mumbai"),
            ("🏛 Delhi", "Delhi"),
            ("🌍 Other", "Other"),
        ],
    },
}

PURPOSE_FLOW = {
    "sales": ["sales_need"],
    "services": ["service_need"],
    "products_prices": [],
    "find_dealer": ["location"],
    "service_centres": ["location"],
    "contact_sigma": [],
}



def onboarding_kb(question_key: str) -> InlineKeyboardMarkup:
    q = ONBOARDING_QUESTIONS[question_key]
    rows = []
    opts = q["options"]
    for i in range(0, len(opts), 2):
        pair = opts[i:i+2]
        rows.append([
            InlineKeyboardButton(label, callback_data=f"onboard:{question_key}:{value}")
            for label, value in pair
        ])
    return InlineKeyboardMarkup(rows)

async def send_onboarding_question(target, question_key: str):
    q = ONBOARDING_QUESTIONS[question_key]
    if hasattr(target, "message"):
        await target.message.reply_text(
            q["question"],
            parse_mode="Markdown",
            reply_markup=onboarding_kb(question_key),
        )
    else:
        await target.reply_text(
            q["question"],
            parse_mode="Markdown",
            reply_markup=onboarding_kb(question_key),
        )

def back_row(*extras):
    """Return a back-row keyboard with optional extra buttons."""
    return extras + ([("🏠  Main Menu", "menu:main")],)

# ════════════════════════════════════════════════════════════════════
#  DYNAMIC KEYBOARD BUILDERS  (built fresh from your Excel/JSON data)
# ════════════════════════════════════════════════════════════════════
def _btn(label: str, cb: str) -> InlineKeyboardButton:
    """Shorthand for a single InlineKeyboardButton."""
    return InlineKeyboardButton(label, callback_data=cb)

def _row(*pairs) -> list:
    """One keyboard row from (label, cb) pairs."""
    return [_btn(label, cb) for label, cb in pairs]

def categories_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        _row(("📷  Still Lenses", "cat:Still Lenses"), ("🎬  Cine Lenses", "cat:Cine Lenses")),
        _row(("📸  Cameras",      "cat:Cameras"),      ("🎒  Accessories", "cat:Accessories")),
        _row(("🏠  Main Menu",    "menu:main")),
    ])

def products_in_category_kb(category: str) -> InlineKeyboardMarkup:
    key_map = {
        "Still Lenses": "still_lenses", "Cine Lenses": "cine_lenses",
        "Cameras": "cameras", "Accessories": "accessories",
    }
    items = load_products().get(key_map.get(category, "still_lenses"), [])
    rows  = [_row((f"📦  {p['Product Name'][:40]}", f"product:{p['Product Name']}"))
             for p in items[:20]]
    rows.append(_row(("⬅️  Categories", "menu:categories"), ("🏠  Main Menu", "menu:main")))
    return InlineKeyboardMarkup(rows)

def prices_category_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        _row(("📷  Still Lenses", "price_cat:Still Lenses"), ("🎬  Cine Lenses", "price_cat:Cine Lenses")),
        _row(("📸  Cameras",      "price_cat:Cameras"),      ("🎒  Accessories", "price_cat:Accessories")),
        _row(("🏠  Main Menu",    "menu:main")),
    ])

def prices_list_kb(category: str) -> InlineKeyboardMarkup:
    key_map = {
        "Still Lenses": "still_lenses", "Cine Lenses": "cine_lenses",
        "Cameras": "cameras", "Accessories": "accessories",
    }
    items = load_products().get(key_map.get(category, "still_lenses"), [])
    rows  = [_row((f"💰  {p['Product Name'][:40]}", f"price:{p['Product Name']}"))
             for p in items[:20]]
    rows.append(_row(("⬅️  Prices", "menu:prices"), ("🏠  Main Menu", "menu:main")))
    return InlineKeyboardMarkup(rows)

def dealer_regions_kb() -> InlineKeyboardMarkup:
    REGION_ICONS = {
        "chn": "🔴", "del": "🟠", "klr": "🟢",
        "klt": "🔵", "bng": "🟣", "mum": "🟡", "tel": "⚪",
    }
    rows = [_row((f"{REGION_ICONS.get(k,'📍')}  {label}", f"dealer_region:{k}"))
            for k, label in DEALER_SHEET_MAP.items()]
    rows.append(_row(("🏠  Main Menu", "menu:main")))
    return InlineKeyboardMarkup(rows)

def dealer_list_kb(region_key: str, dealers: list) -> InlineKeyboardMarkup:
    rows = [_row((f"🏪  {d.get('customer_name', 'Dealer')[:35]}", f"dealer:{region_key}:{i}"))
            for i, d in enumerate(dealers[:15])]
    rows.append(_row(("⬅️  Regions", "menu:dealers"), ("🏠  Main Menu", "menu:main")))
    return InlineKeyboardMarkup(rows)

def service_list_kb(centers: list) -> InlineKeyboardMarkup:
    rows = [_row((f"🔧  {c.get('name','Centre')[:35]}", f"svc:{i}"))
            for i, c in enumerate(centers)]
    rows.append(_row(("🏠  Main Menu", "menu:main")))
    return InlineKeyboardMarkup(rows)

# ════════════════════════════════════════════════════════════════════
#  MESSAGE FORMATTERS
# ════════════════════════════════════════════════════════════════════
DIV = "━" * 28

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

    lines = [
        f"📦 *{name}*",
        f"_{cat}  •  {line}_" if cat or line else "",
        f"`{DIV}`",
    ]
    if fl:       lines.append(f"🔭  *Focal Length:*  {fl}")
    if ap:       lines.append(f"🔆  *Max Aperture:*  {ap}")
    if mounts:   lines.append(f"🔩  *Mounts:*  {mounts}")
    if features: lines.append(f"\n✨  *Key Features*\n{features}")
    lines.append(f"`{DIV}`")
    lines.append(f"💰  *Price (India):*  {price}")
    if pr_range: lines.append(f"📊  *Price Range:*  {pr_range}")
    lines.append(f"\n🌐  [View on Sigma India](https://sigmaindia.in/)")
    lines.append(f"🛒  [Search on Amazon](https://www.amazon.in/s?k=Sigma+{name.replace(' ','+')})")
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
        f"_Prices are indicative. Contact your nearest dealer for final pricing._\n\n"
        f"🌐  [Buy from Sigma India](https://sigmaindia.in/)\n"
        f"🛒  [Check Amazon India](https://www.amazon.in/s?k=Sigma+{name.replace(' ','+')})\n"
        f"🔵  [Check Flipkart](https://www.flipkart.com/search?q=Sigma+{name.replace(' ','+')})"
    )

def fmt_dealer_detail(d: dict) -> str:
    formatted = format_dealer_for_chat(d)
    name      = formatted.get("name", "—")
    loc       = formatted.get("location", "")
    addr      = formatted.get("address", "")
    code      = formatted.get("dealer_code", "")
    sales     = formatted.get("sales_person", "")

    lines = [
        f"🏪 *{name}*",
        f"✅  _Authorised Sigma Dealer_",
        f"`{DIV}`",
        f"📍  *Location:*  {loc}",
    ]
    if addr:  lines.append(f"🗺️  *Address:*  {addr}")
    if code:  lines.append(f"🆔  *Dealer Code:*  `{code}`")
    if sales: lines.append(f"👤  *Sales Contact:*  {sales}")
    lines.append(f"`{DIV}`")
    lines.append(f"🌐  [Sigma India Dealer Network](https://sigmaindia.in/dealer-network/)")
    return "\n".join(l for l in lines if l)

def fmt_service_center(c: dict) -> str:
    formatted = format_service_center_for_chat(c)
    lines = [
        f"🔧 *{formatted.get('name', '—')}*",
        f"✅  _Authorised Sigma Service Centre_",
        f"`{DIV}`",
        f"📍  *Location:*  {formatted.get('location', '')}",
        f"🗺️  *Address:*  {formatted.get('address', '')}",
        f"📞  *Phone:*  {formatted.get('phone', '—')}",
        f"📧  *Email:*  {formatted.get('email', '—')}",
        f"`{DIV}`",
        f"🌐  [Service & Support](https://sigmaindia.in/service-support/)",
    ]
    return "\n".join(l for l in lines if l)

CONTACT_MSG = (
    f"📞 *Contact Sigma India*\n"
    f"`{DIV}`\n"
    f"🌐  *Website:*  [sigmaindia.in](https://sigmaindia.in/)\n"
    f"📧  *General:*  info@sigmaindia.in\n"
    f"🔧  *Service:*  [Support Portal](https://sigmaindia.in/service-support/)\n"
    f"🤝  *Dealers:*  [Find Dealers](https://sigmaindia.in/dealer-network/)\n"
    f"`{DIV}`\n"
    f"🕐  *Business Hours:*\n"
    f"  Monday – Saturday:  9:00 AM – 6:00 PM IST\n\n"
    f"_Our team typically responds within 2 business hours._"
)

def build_welcome(user_name: str) -> str:
    cfg = load_config()
    brand = cfg.get("brand_name", "Sigma AI Assistant")
    products = get_all_products()
    dealers  = get_all_dealers_flat()
    svc      = load_service_centers()
    return (
        f"👋 *Welcome, {user_name}!*\n\n"
        f"I'm the *{brand}* — your dedicated expert for all things Sigma.\n"
        f"`{DIV}`\n"
        f"📦  *{len(products)}* products in our catalogue\n"
        f"🤝  *{len(dealers)}+* authorised dealers across India\n"
        f"🔧  *{len(svc)}* service centres nationwide\n"
        f"`{DIV}`\n"
        f"What would you like to explore today? 👇"
    )


def build_onboarding_summary(answers: dict) -> str:
    labels = {
        "purpose": "Purpose",
        "category": "Category",
        "usage": "Use Case",
        "budget": "Budget",
        "location": "Location",
    }
    pretty = {
        "buy_products": "Buy Products",
        "check_prices": "Check Prices",
        "find_dealer": "Find Dealer",
        "service_repair": "Service & Repair",
        "contact_sigma": "Contact Sigma",
    }

    lines = ["✅ *Thanks! Here's what I understood:*\n"]
    for key in ["purpose", "category", "usage", "budget", "location"]:
        if key in answers:
            val = pretty.get(answers[key], answers[key])
            lines.append(f"• *{labels[key]}:* {val}")
    lines.append("\nPlease choose an option below.")
    return "\n".join(lines)


async def route_after_onboarding(q, ctx, user):
    answers = ctx.user_data.get("onboarding_answers", {})

    purpose = answers.get("purpose")
    sales_need = answers.get("sales_need")
    service_need = answers.get("service_need")

    # Sales -> Products & Prices
    if purpose == "sales" and sales_need == "products_prices":
        await send(
            q,
            f"🛍 *Products & Pricing* \n"

            "Browse Sigma products along with pricing information.",
            categories_kb(),
        )
        return

    # Sales -> Find Dealer
    if purpose == "sales" and sales_need == "find_dealer":
        location = answers.get("location", "")
        dealers = search_dealers_by_query(location, limit=10)

        if dealers:
            ctx.user_data["search_dealers"] = dealers
            rows = [
                _row((f"🏪 {d.get('customer_name', 'Dealer')[:35]}", f"search_dealer:{i}"))
                for i, d in enumerate(dealers)
            ]
            rows.append(_row(("🏠 Main Menu", "menu:main")))

            await send(
                q,
                f"🤝 *Authorised Dealers in {location}*"

            "Found *{len(dealers)}* dealers.",
                InlineKeyboardMarkup(rows),
            )
        else:
            await send(
                q,
                f"No dealers found in *{location}*. Showing all regions.",
                dealer_regions_kb(),
            )
        return

    # Services -> Service Centres
    if purpose == "services" and service_need == "service_centres":
        location = answers.get("location", "")
        centers = search_service_centers(location)

        if centers:
            ctx.user_data["service_centers"] = centers
            await send(
                q,
                f"🔧 *Service Centres in {location}*",
                service_list_kb(centers),
            )
        else:
            await send(
                q,
                "🔧 No exact matches found. Showing all service centres.",
                kb([("🔧 View All Centres", "menu:service")]),
            )
        return

    # Services -> Contact Sigma
    if purpose == "services" and service_need == "contact_sigma":
        await send(
            q,
            CONTACT_MSG,
            kb([("🏠 Main Menu", "menu:main")]),
        )
        return

    # Fallback
    await send(q, build_welcome(user.first_name), MAIN_MENU)

# ════════════════════════════════════════════════════════════════════
#  BOT HANDLERS
# ════════════════════════════════════════════════════════════════════

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    log_interaction(ctx, update, "/start")

    ctx.user_data["onboarding_answers"] = {}
    ctx.user_data["onboarding_flow"] = ["purpose"]

    welcome = (
        f"👋 *Welcome to Sigma India Assistant, {user.first_name}!* \n"


        "I'm here to help you with: \n "

        "• Product recommendations \ n"

        "• Pricing information \n"

        "• Authorised dealers \n"

        "• Service & repairs \n"

        "• Contact details \n"


        "Let me ask a few quick questions so I can assist you better."
    )

    await update.message.reply_text(welcome, parse_mode="Markdown")
    await send_onboarding_question(update, "purpose")

async def cmd_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    log_interaction(ctx, update, "/menu")
    await update.message.reply_text(
        "🏠 *Main Menu* — What would you like to explore?",
        parse_mode="Markdown",
        reply_markup=MAIN_MENU,
    )

async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    log_interaction(ctx, update, "/help")
    await update.message.reply_text(
        f"ℹ️ *Sigma AI Bot — Help*\n"
        f"`{DIV}`\n"
        f"*Commands:*\n"
        f"  /start  — Welcome & main menu\n"
        f"  /menu   — Show main menu\n"
        f"  /search — Search products\n"
        f"  /help   — This help message\n"
        f"`{DIV}`\n"
        f"You can also *type any question* about Sigma products, pricing, "
        f"dealers, or service centres and I'll help you navigate.\n\n"
        f"_Example:_ `Where can I find dealers in Chennai?`",
        parse_mode="Markdown",
        reply_markup=kb([("🏠  Main Menu", "menu:main")]),
    )

# ── Helpers ──────────────────────────────────────────────────────
LABEL_MAP = {
    "menu:main":        "🏠  Main Menu",
    "menu:products":    "🔭  Browse Products",
    "menu:prices":      "💰  Pricing",
    "menu:dealers":     "🤝  Find a Dealer",
    "menu:service":     "🔧  Service Centres",
    "menu:categories":  "📋  Product Categories",
    "menu:contact":     "📞  Contact Sigma",
}

async def stamp_selection(q, label: str):
    """
    Replace the buttons on the tapped message with a ✅ receipt stamp,
    keeping the original message text visible — shows the user what they picked.
    """
    try:
        await q.edit_message_reply_markup(
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(f"✅  {label}", callback_data="noop")]
            ])
        )
    except Exception:
        pass   # message may already be edited — silently ignore

async def send(q, text: str, markup=None, preview=False):
    """Send a NEW message (stacks below previous — never deletes)."""
    await q.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=markup,
        disable_web_page_preview=not preview,
    )

# ── Callback router ──────────────────────────────────────────────
async def handle_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q    = update.callback_query
    data = q.data
    await q.answer()
    log_interaction(ctx, update, f"cb:{data}")

    if data == "restart_onboarding":
        ctx.user_data["onboarding_answers"] = {}
        ctx.user_data["onboarding_flow"] = ["purpose"]
        await send_onboarding_question(q, "purpose")
        return

    if data == "onboard_complete":
        await route_after_onboarding(q, ctx, update.effective_user)
        return

    if data.startswith("onboard:"):
        _, question_key, value = data.split(":", 2)
        answers = ctx.user_data.setdefault("onboarding_answers", {})
        answers[question_key] = value

        try:
            await q.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass

        if question_key == "purpose":
            if question_key == "purpose":
                ctx.user_data["onboarding_flow"] = ["purpose"] + PURPOSE_FLOW.get(value, [])
        elif question_key in ("sales_need", "service_need"):
            ctx.user_data["onboarding_flow"] = (
                ctx.user_data.get("onboarding_flow", []) + PURPOSE_FLOW.get(value, [])
            )

        flow = ctx.user_data.get("onboarding_flow", ["purpose"])
        current_index = flow.index(question_key)
        next_index = current_index + 1

        if next_index < len(flow):
            next_question = flow[next_index]
            await send_onboarding_question(q, next_question)
        else:
            await send(
                q,
                build_onboarding_summary(answers),
                kb(
                    [("✅ Continue", "onboard_complete")],
                    [("🔄 Start Over", "restart_onboarding")],
                ),
            )
        return


    # No-op button (used for stamp receipts)
    if data == "noop":
        return

    # ── Main menu ────────────────────────────────────────────────
    if data == "menu:main":
        await stamp_selection(q, "Main Menu")
        await send(q, build_welcome(update.effective_user.first_name), MAIN_MENU)

    # ── Categories ───────────────────────────────────────────────
    elif data == "menu:categories":
        await stamp_selection(q, "Product Categories")
        await send(q,
            f"📋 *Product Categories*\n"
            f"`{DIV}`\n"
            f"Sigma offers a complete lineup across four categories.\n"
            f"Select one to browse the full range:",
            categories_kb(),
        )

    elif data.startswith("cat:"):
        category = data.split(":", 1)[1]
        key_map  = {
            "Still Lenses": "still_lenses", "Cine Lenses": "cine_lenses",
            "Cameras": "cameras", "Accessories": "accessories",
        }
        count = len(load_products().get(key_map.get(category, ""), []))
        await stamp_selection(q, category)
        await send(q,
            f"📦 *{category}*\n"
            f"`{DIV}`\n"
            f"*{count} products* available. Select one for full specifications and pricing:",
            products_in_category_kb(category),
        )

    # ── Products (from main menu shortcut) ───────────────────────
    elif data == "menu:products":
        await stamp_selection(q, "Browse Products")
        await send(q,
            f"🔭 *Sigma Product Catalogue*\n"
            f"`{DIV}`\n"
            f"Explore our full lineup of precision-engineered lenses, cameras, and accessories.\n"
            f"Browse by category:",
            categories_kb(),
        )

    # ── Single product detail ─────────────────────────────────────
    elif data.startswith("product:"):
        name  = data.split(":", 1)[1]
        all_p = get_all_products()
        p     = next((x for x in all_p if x.get("Product Name") == name), None)
        if p:
            cat_key = p.get("_display_category", "Still Lenses")
            await stamp_selection(q, name[:40])
            await send(q,
                fmt_product_detail(p),
                kb(
                    [(f"⬅️  {cat_key}", f"cat:{cat_key}")],
                    [("🏠  Main Menu", "menu:main")],
                ),
            )

    # ── Prices category picker ────────────────────────────────────
    elif data == "menu:prices":
        await stamp_selection(q, "Pricing")
        await send(q,
            f"💰 *Sigma India Pricing*\n"
            f"`{DIV}`\n"
            f"Pricing available for *{len(PRICE_USD)} products*.\n"
            f"All prices shown in Indian Rupees (₹).\n\n"
            f"Select a category to view prices:",
            prices_category_kb(),
        )

    elif data.startswith("price_cat:"):
        category = data.split(":", 1)[1]
        key_map  = {
            "Still Lenses": "still_lenses", "Cine Lenses": "cine_lenses",
            "Cameras": "cameras", "Accessories": "accessories",
        }
        count = len(load_products().get(key_map.get(category, ""), []))
        await stamp_selection(q, category)
        await send(q,
            f"💰 *{category} — Pricing*\n"
            f"`{DIV}`\n"
            f"*{count} products* in this category. Select one to view pricing details:",
            prices_list_kb(category),
        )

    # ── Single price detail ───────────────────────────────────────
    elif data.startswith("price:"):
        name = data.split(":", 1)[1]
        await stamp_selection(q, name[:40])
        await send(q,
            fmt_price_detail(name),
            kb(
                [("⬅️  Back to Prices", "menu:prices")],
                [("🏠  Main Menu",       "menu:main")],
            ),
        )

    # ── Dealer regions ────────────────────────────────────────────
    elif data == "menu:dealers":
        await stamp_selection(q, "Find a Dealer")
        await send(q,
            f"🤝 *Authorised Sigma Dealers*\n"
            f"`{DIV}`\n"
            f"*{len(get_all_dealers_flat())}+ authorised dealers* across India.\n"
            f"Select your region to find dealers near you:",
            dealer_regions_kb(),
        )

    elif data.startswith("dealer_region:"):
        region_key   = data.split(":", 1)[1]
        region_label = DEALER_SHEET_MAP.get(region_key, region_key)
        dealers_data = load_dealers(region_key)
        dealers      = dealers_data.get(region_key, [])
        await stamp_selection(q, region_label)
        if not dealers:
            await send(q,
                f"🤝 *{region_label}*\n\nNo dealers found for this region yet.\n"
                f"Visit [sigmaindia.in/dealer-network/](https://sigmaindia.in/dealer-network/) for the latest listings.",
                kb([("⬅️  Regions", "menu:dealers"), ("🏠  Main Menu", "menu:main")]),
            )
            return
        ctx.user_data[f"dealers_{region_key}"] = dealers
        await send(q,
            f"🤝 *{region_label}*\n"
            f"`{DIV}`\n"
            f"*{len(dealers)} authorised dealers* in this region.\n"
            f"Select a dealer for full details:",
            dealer_list_kb(region_key, dealers),
        )

    elif data.startswith("dealer:"):
        _, region_key, idx_str = data.split(":", 2)
        idx     = int(idx_str)
        dealers = ctx.user_data.get(f"dealers_{region_key}") or load_dealers(region_key).get(region_key, [])
        if 0 <= idx < len(dealers):
            d = dealers[idx]
            name = d.get("customer_name", "Dealer")
            await stamp_selection(q, name[:40])
            await send(q,
                fmt_dealer_detail(d),
                kb(
                    [(f"⬅️  {DEALER_SHEET_MAP.get(region_key, 'Region')}", f"dealer_region:{region_key}")],
                    [("🏠  Main Menu", "menu:main")],
                ),
            )

    # ── Service centres ───────────────────────────────────────────
    elif data == "menu:service":
        centers = load_service_centers()
        ctx.user_data["service_centers"] = centers
        await stamp_selection(q, "Service Centres")
        await send(q,
            f"🔧 *Sigma Authorised Service Centres*\n"
            f"`{DIV}`\n"
            f"*{len(centers)} service centres* across India.\n"
            f"All centres are fully authorised by Sigma for:\n"
            f"  • Warranty repairs\n"
            f"  • Out-of-warranty servicing\n"
            f"  • Sensor & optical calibration\n\n"
            f"Select a centre for contact details:",
            service_list_kb(centers),
        )

    elif data.startswith("svc:"):
        idx     = int(data.split(":", 1)[1])
        centers = ctx.user_data.get("service_centers") or load_service_centers()
        if 0 <= idx < len(centers):
            name = centers[idx].get("name", "Service Centre")
            await stamp_selection(q, name[:40])
            await send(q,
                fmt_service_center(centers[idx]),
                kb(
                    [("⬅️  All Centres", "menu:service")],
                    [("🏠  Main Menu",    "menu:main")],
                ),
            )

    # ── Contact ───────────────────────────────────────────────────
    elif data == "menu:contact":
        await stamp_selection(q, "Contact Sigma")
        await send(q,
            CONTACT_MSG,
            kb([("🏠  Main Menu", "menu:main")]),
        )

# ── Plain text: smart search ──────────────────────────────────────
async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg  = update.message.text.strip()
    low  = msg.lower()
    log_interaction(ctx, update, msg)

    # ── Dealer search ─────────────────────────────────────────────
    if any(k in low for k in ["dealer", "buy", "purchase", "shop", "store", "outlet"]):
        dealers = search_dealers_by_query(msg, limit=10)
        if dealers:
            ctx.user_data["search_dealers"] = dealers
            city_hint = msg.title()
            resp = (
                f"🤝 *Dealers — Search Results*\n"
                f"`{DIV}`\n"
                f"Found *{len(dealers)} authorised dealers* matching your query.\n"
                f"Select a dealer for full contact details:"
            )
            rows = [_row((f"🏪  {d.get('customer_name','Dealer')[:35]}", f"search_dealer:{i}"))
                    for i, d in enumerate(dealers)]
            rows.append(_row(("🤝  All Regions", "menu:dealers"), ("🏠  Main Menu", "menu:main")))
            await update.message.reply_text(
                resp, parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(rows),
            )
        else:
            await update.message.reply_text(
                f"🤝 No dealers found for *{msg}*.\n\n"
                f"Try browsing by region or visit [sigmaindia.in/dealer-network/](https://sigmaindia.in/dealer-network/)",
                parse_mode="Markdown",
                reply_markup=kb(
                    [("🤝  Browse by Region", "menu:dealers")],
                    [("🏠  Main Menu", "menu:main")],
                ),
                disable_web_page_preview=True,
            )
        return

    # ── Service centre search ─────────────────────────────────────
    if any(k in low for k in ["service", "repair", "warranty", "calibrat"]):
        centers = search_service_centers(msg)
        if centers:
            ctx.user_data["service_centers"] = centers
            rows = [_row((f"🔧  {c.get('name','Centre')[:35]}", f"svc:{i}"))
                    for i, c in enumerate(centers)]
            rows.append(_row(("🏠  Main Menu", "menu:main")))
            await update.message.reply_text(
                f"🔧 *Service Centres — Search Results*\n"
                f"`{DIV}`\n"
                f"Found *{len(centers)} service centre(s)* matching your query.\n"
                f"Select one for full details:",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(rows),
            )
        else:
            await update.message.reply_text(
                f"🔧 *Sigma Service Centres*\n"
                f"`{DIV}`\n"
                f"No specific matches. Browse all authorised service centres below:",
                parse_mode="Markdown",
                reply_markup=kb(
                    [("🔧  View All Centres", "menu:service")],
                    [("🏠  Main Menu", "menu:main")],
                ),
            )
        return

    # ── Product search ────────────────────────────────────────────
    results = search_products(msg, limit=8)
    if results:
        rows = [_row((f"📦  {p['Product Name'][:40]}", f"product:{p['Product Name']}"))
                for p in results]
        rows.append(_row(("📋  All Categories", "menu:categories"), ("🏠  Main Menu", "menu:main")))
        await update.message.reply_text(
            f"🔍 *Search Results for:* _{msg}_\n"
            f"`{DIV}`\n"
            f"Found *{len(results)} product(s)* matching your query.\n"
            f"Select one for full specifications and pricing:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(rows),
        )
    else:
        await update.message.reply_text(
            f"🔍 No products found for *{msg}*.\n\n"
            f"Try browsing our full catalogue or use the menu below:",
            parse_mode="Markdown",
            reply_markup=MAIN_MENU,
        )

# ── Search dealer result (from text search) ───────────────────────
async def handle_search_dealer_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q   = update.callback_query
    idx = int(q.data.split(":", 1)[1])
    await q.answer()
    dealers = ctx.user_data.get("search_dealers", [])
    if 0 <= idx < len(dealers):
        back = kb(
            [("⬅️  Search Results", "back:search_dealers")],
            [("🏠  Main Menu", "menu:main")],
        )
        await q.edit_message_text(
            fmt_dealer_detail(dealers[idx]),
            parse_mode="Markdown", reply_markup=back,
            disable_web_page_preview=True,
        )

# ================================================================
#  APPLICATION ENTRY POINT
# ================================================================
def main():
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("Set your bot token: export SIGMA_BOT_TOKEN='your_token'")
        print("Or edit BOT_TOKEN directly in this file.")
        sys.exit(1)

    print("=" * 56)
    print("  Sigma AI Telegram Bot")
    try:
        print(f"  Products loaded:  {len(get_all_products())}")
        print(f"  Dealers loaded:   {len(get_all_dealers_flat())}")
        print(f"  Service centres:  {len(load_service_centers())}")
    except Exception as e:
        print(f"  Data load warning: {e}")
    print("=" * 56)

    # Compatible with python-telegram-bot v20, v21, v22
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .arbitrary_callback_data(False)
        .build()
    )

    # More-specific patterns must come before the catch-all
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

    print("  Bot is running -- press Ctrl+C to stop")
    # run_polling manages its own event loop (v20-v22)
    app.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()
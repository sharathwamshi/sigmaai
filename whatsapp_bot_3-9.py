"""
================================================================
  SIGMA AI - WhatsApp Bot (Twilio)
  Place this file in the same folder as app.py
  Run: python whatsapp_bot.py
================================================================

SETUP
-----
1.  pip install flask twilio python-dotenv requests
2.  Create a Twilio account, enable WhatsApp Sandbox
3.  Fill .env with TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_FROM
4.  Expose with ngrok: ngrok http 5000
5.  Set sandbox webhook to: https://<ngrok-url>/whatsapp
6.  python whatsapp_bot.py

DESIGN NOTES (updated to match the new menu flow)
---------------------------------------------------
- The bot is now a flat, 5-option main menu that mirrors the approved
  screen flow exactly:
      Browse Products | Purchase | Technical Support |
      Warranty Registration | Sigma Loyalty Program (SIGMA Focal Circle)
- Every menu with more than one option — main menu, product category,
  and state selection — is sent as a SINGLE WhatsApp interactive list
  message (Twilio's twilio/list-picker content type). All options
  appear as tappable rows inside one message bubble, exactly like the
  reference screens. WhatsApp's list-picker supports up to 10 rows in
  one message, so nothing gets split into a second "More options"
  message the way the old 3-button quick-reply chunking did.
- Quick-reply buttons (twilio/quick-reply, max 3 per message) are kept
  only as an automatic fallback path if the list-picker API call
  itself fails (network/account issue) — see send_menu() below.
- Screens that end in a single link-out action (View Lenses, Locate
  Service Centre, Register Now, Join Now) are sent via Twilio's
  twilio/call-to-action content type as a single URL button, instead
  of the old inline product/service/dealer browsing.
- The Purchase flow no longer lists individual dealers. Each state
  shows one sales-team contact card with a "Call Us" (PHONE_NUMBER
  button) and an "Email Us" (URL/mailto button) — matching the
  reference screens.
- Twilio's twilio/call-to-action content type caps out at 2 buttons,
  and the category/state screens already use both slots for the
  link/contact actions themselves, so "Main Menu" can't ride along in
  that same message. Instead, every CTA screen (category info, state
  contact card, support, warranty, loyalty) is immediately followed
  by a small send_back_menu() quick-reply message, so the user always
  has a tappable way back to the menu rather than needing to type
  "menu".
- All the URLs, phone numbers and email addresses marked
  "REPLACE ME" below are placeholders — swap them for the real
  sigmaindia.in links and SAPL regional contact details before going
  live.
- A plain-text menu is used only as a last-resort fallback if both
  the list-picker AND the quick-reply API calls fail.
- Every reply is a new message; chat history is never deleted.
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
from app import BASE_DIR  # only needed for session file location

from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse

# ============================================================
#  CONFIG
# ============================================================
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

app_flask     = Flask(__name__)
twilio_client = Client(ACCOUNT_SID, AUTH_TOKEN)

FOOTER = "\n\nsigmaindia.in"
LIST_PAGE_SIZE = 10

# ============================================================
#  SESSION STORAGE
# ============================================================
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


# ============================================================
#  TWILIO CONTENT API SENDERS
# ============================================================

def send_interactive_list(to: str, header: str, body: str,
                           options: list, button_label: str = "Choose an option"):
    """
    Send a WhatsApp interactive list message (tap-to-select tiles).
    ALL options are delivered in ONE message bubble (up to 10 rows) —
    this is what renders the menu the way the reference screens show
    it, instead of splitting across several messages.
    options: list of (label, reply_id) tuples - max 10.
    Returns the Twilio message SID or None on failure.
    """
    import requests
    from requests.auth import HTTPBasicAuth

    try:
        items = [
            {"id": reply_id[:200], "item": label[:24]}
            for label, reply_id in options[:LIST_PAGE_SIZE]
        ]
        content_payload = {
            "friendly_name": f"sigma_list_{datetime.now().strftime('%H%M%S%f')}",
            "language": "en",
            "variables": {},
            "types": {
                "twilio/list-picker": {
                    "body":   body[:1024],
                    "button": button_label[:20],
                    "items":  items,
                }
            },
        }
        resp = requests.post(
            "https://content.twilio.com/v1/Content",
            json=content_payload,
            auth=HTTPBasicAuth(ACCOUNT_SID, AUTH_TOKEN),
            timeout=10,
        )
        if resp.status_code not in (200, 201):
            raise Exception(f"Content API {resp.status_code}: {resp.text}")

        content_sid = resp.json()["sid"]
        msg = twilio_client.messages.create(content_sid=content_sid, from_=FROM_NUMBER, to=to)
        log.info(f"Interactive list sent: {msg.sid}")
        return msg.sid
    except Exception as e:
        log.warning(f"Interactive list failed ({e}), falling back to quick-reply/text")
        return None


def send_quick_reply(to: str, body: str, options: list):
    """
    Send up to 3 WhatsApp quick-reply buttons directly in the chat
    bubble (no popup). options: list of (label, key) tuples, max 3.
    Returns the Twilio message SID or None on failure.
    """
    import requests
    from requests.auth import HTTPBasicAuth

    try:
        actions = [{"id": key[:200], "title": label[:20]} for label, key in options[:3]]
        content_payload = {
            "friendly_name": f"sigma_qr_{datetime.now().strftime('%H%M%S%f')}",
            "language": "en",
            "variables": {},
            "types": {
                "twilio/quick-reply": {
                    "body": body[:1024],
                    "actions": actions,
                }
            },
        }
        resp = requests.post(
            "https://content.twilio.com/v1/Content",
            json=content_payload,
            auth=HTTPBasicAuth(ACCOUNT_SID, AUTH_TOKEN),
            timeout=10,
        )
        if resp.status_code not in (200, 201):
            raise Exception(f"Content API {resp.status_code}: {resp.text}")

        content_sid = resp.json()["sid"]
        msg = twilio_client.messages.create(content_sid=content_sid, from_=FROM_NUMBER, to=to)
        log.info(f"Quick-reply buttons sent: {msg.sid}")
        return msg.sid
    except Exception as e:
        log.warning(f"Quick-reply buttons failed ({e}), falling back to text")
        lines = [body, ""]
        for label, _ in options:
            lines.append(f"- {label}")
        lines.append("\nReply with the option name to continue.")
        lines.append(FOOTER)
        send_text_message(to, "\n".join(lines))
        return None


def send_cta_buttons(to: str, body: str, actions: list):
    """
    Send a WhatsApp call-to-action message: body text + up to 2 buttons.
    actions: list of dicts, each one of:
      {"type": "URL", "title": "View Lenses", "url": "https://..."}
      {"type": "PHONE_NUMBER", "title": "Call Us", "phone": "+91..."}
    Returns the Twilio message SID or None on failure (falls back to plain text).
    """
    import requests
    from requests.auth import HTTPBasicAuth

    try:
        content_payload = {
            "friendly_name": f"sigma_cta_{datetime.now().strftime('%H%M%S%f')}",
            "language": "en",
            "variables": {},
            "types": {
                "twilio/call-to-action": {
                    "body": body[:1024],
                    "actions": actions[:2],
                }
            },
        }
        resp = requests.post(
            "https://content.twilio.com/v1/Content",
            json=content_payload,
            auth=HTTPBasicAuth(ACCOUNT_SID, AUTH_TOKEN),
            timeout=10,
        )
        if resp.status_code not in (200, 201):
            raise Exception(f"Content API {resp.status_code}: {resp.text}")

        content_sid = resp.json()["sid"]
        msg = twilio_client.messages.create(content_sid=content_sid, from_=FROM_NUMBER, to=to)
        log.info(f"CTA message sent: {msg.sid}")
        return msg.sid
    except Exception as e:
        log.warning(f"CTA message failed ({e}), falling back to text")
        lines = [body, ""]
        for a in actions:
            if a["type"] == "URL":
                lines.append(f"{a['title']}: {a['url']}")
            elif a["type"] == "PHONE_NUMBER":
                lines.append(f"{a['title']}: {a['phone']}")
        lines.append(FOOTER)
        send_text_message(to, "\n".join(lines))
        return None


def send_text_message(to: str, body: str):
    try:
        msg = twilio_client.messages.create(body=body, from_=FROM_NUMBER, to=to)
        log.info(f"Text message sent: {msg.sid}")
        return msg.sid
    except Exception as e:
        log.error(f"Failed to send text message: {e}")
        return None


def send_back_menu(to: str, extra: list = None):
    """
    Sends a small quick-reply button row so the user always has a
    tappable way back to the menu. This exists because Twilio's
    twilio/call-to-action message caps out at 2 buttons — screens
    like the state contact card (Call Us + Email Us) or a category
    link (View Lenses) already use every slot for the link/action
    itself, so "Main Menu" can't ride along in that same message.
    This is sent as a separate, immediate follow-up instead.

    `extra` lets a screen offer one more shortcut ahead of Main Menu,
    e.g. ("Categories", "products") on a product-category screen —
    pass None (default) for a bare "Main Menu" button.
    """
    options = (extra or []) + [("Main Menu", "main")]
    send_quick_reply(to, "What would you like to do next?", options)


def send_menu(to: str, header: str, body_text: str, options: list,
              button_label: str = "Choose an option") -> bool:
    """
    Sends the full option set as ONE WhatsApp interactive list message
    (twilio/list-picker) — all rows appear together in a single bubble,
    matching the approved reference screens exactly. WhatsApp allows up
    to 10 rows in a list-picker, so every menu in this bot (max 7
    options) fits in one message; nothing gets split into a second
    "More options" message anymore.

    Only if the list-picker API call itself fails (network/account
    issue — see send_interactive_list) does this fall back to the old
    behaviour of stacking quick-reply buttons in groups of 3.
    """
    sid = send_interactive_list(to, header, body_text, options, button_label)
    if sid:
        return True

    # Fallback path only: list-picker call failed outright.
    log.warning("send_menu: list-picker unavailable, using quick-reply fallback")
    for i in range(0, len(options), 3):
        chunk = options[i:i + 3]
        text  = body_text if i == 0 else "More options:"
        send_quick_reply(to, text, chunk)
    return True


# ============================================================
#  MAIN MENU (matches the approved 5-option flow)
# ============================================================

MAIN_OPTIONS = [
    ("Browse Products",       "products"),
    ("Purchase",              "purchase"),
    ("Technical Support",     "support"),
    ("Warranty Registration", "warranty"),
    ("Sigma Loyalty Program", "loyalty"),   # full name lives in LOYALTY_BODY below;
                                             # WhatsApp list rows cap at 24 characters
]


def welcome_msg(user_name: str) -> str:
    return (
        f"Welcome to SIGMA India!\n\n"
        f"Please choose an option from the menu below."
        f"{FOOTER}"
    )


def _send_main_menu(phone: str, sess: dict):
    sess["options"] = MAIN_OPTIONS
    send_menu(phone, "Main Menu", "Please choose an option from the menu below.",
              MAIN_OPTIONS, "Choose an option")


# ============================================================
#  BROWSE PRODUCTS
#  REPLACE ME: point each url at the real sigmaindia.in page.
# ============================================================

CATEGORY_INFO = {
    "lenses": {
        "label": "Lenses",
        "desc":  "Explore our complete range of SIGMA lenses.",
        "button": "View Lenses",
        "url":  f"{SIGMA_WEBSITE}/lenses",   # REPLACE ME
    },
    "cine": {
        "label": "Cine Lenses",
        "desc":  "Discover our professional cine lenses.",
        "button": "View Cine Lenses",
        "url":  f"{SIGMA_WEBSITE}/cine-lenses",   # REPLACE ME
    },
    "cameras": {
        "label": "Cameras",
        "desc":  "Explore our latest camera lineup.",
        "button": "View Cameras",
        "url":  f"{SIGMA_WEBSITE}/cameras",   # REPLACE ME
    },
    "accessories": {
        "label": "Accessories",
        "desc":  "Browse accessories compatible with your SIGMA equipment.",
        "button": "View Accessories",
        "url":  f"{SIGMA_WEBSITE}/accessories",   # REPLACE ME
    },
    "discontinued": {
        "label": "Discontinued Models",
        "desc":  "Looking for older products? Browse discontinued models.",
        "button": "View Models",
        "url":  f"{SIGMA_WEBSITE}/discontinued-models",   # REPLACE ME
    },
}

PRODUCT_CAT_OPTIONS = [(v["label"], f"cat:{k}") for k, v in CATEGORY_INFO.items()] + \
                      [("Main Menu", "main")]


# ============================================================
#  PURCHASE
#  REPLACE ME: swap in the real SAPL regional sales contacts.
#  Tamil Nadu number below is taken from the reference screen;
#  the rest are placeholders.
# ============================================================

STATE_INFO = {
    "tn": {
        "label": "Tamil Nadu",
        "team":  "SIGMA Chennai Sales Team",
        "phone": "+91 90809 52751",
        "email": "chennai@sigmaindia.in",          # REPLACE ME
    },
    "ka": {
        "label": "Karnataka",
        "team":  "SIGMA Bangalore Sales Team",
        "phone": "+91 00000 00000",                # REPLACE ME
        "email": "bangalore@sigmaindia.in",         # REPLACE ME
    },
    "kl": {
        "label": "Kerala",
        "team":  "SIGMA Kerala Sales Team",
        "phone": "+91 00000 00000",                # REPLACE ME
        "email": "kerala@sigmaindia.in",            # REPLACE ME
    },
    "mh": {
        "label": "Maharashtra",
        "team":  "SIGMA Mumbai Sales Team",
        "phone": "+91 00000 00000",                # REPLACE ME
        "email": "mumbai@sigmaindia.in",            # REPLACE ME
    },
    "dl": {
        "label": "Delhi",
        "team":  "SIGMA Delhi Sales Team",
        "phone": "+91 00000 00000",                # REPLACE ME
        "email": "delhi@sigmaindia.in",             # REPLACE ME
    },
    "other": {
        "label": "Other",
        "team":  "SIGMA National Sales Team",
        "phone": "+91 00000 00000",                # REPLACE ME
        "email": "info@sigmaindia.in",              # REPLACE ME
    },
}

PURCHASE_STATE_OPTIONS = [(v["label"], f"state:{k}") for k, v in STATE_INFO.items()] + \
                          [("Main Menu", "main")]


# ============================================================
#  TECHNICAL SUPPORT / WARRANTY / LOYALTY — static screens
#  REPLACE ME: point each url at the real sigmaindia.in page.
# ============================================================

SUPPORT_BODY = (
    "Need assistance with your SIGMA product?\n\n"
    "Find your nearest authorized service centre."
)
SUPPORT_URL = f"{SIGMA_WEBSITE}/service-centre-locator"   # REPLACE ME

WARRANTY_BODY = (
    "Register your SIGMA product in 3 simple steps.\n\n"
    "1. Visit the link\n"
    "2. Create account / login\n"
    "3. Register your product"
)
WARRANTY_URL = f"{SIGMA_WEBSITE}/warranty-registration"   # REPLACE ME

LOYALTY_BODY = (
    "Join the Sigma Loyalty Program (SIGMA Focal Circle) in 3 simple steps.\n\n"
    "1. Visit the link\n"
    "2. Create account / login\n"
    "3. Join the loyalty program\n\n"
    "Earn rewards on eligible purchases."
)
LOYALTY_URL = f"{SIGMA_WEBSITE}/loyalty"   # REPLACE ME


# ============================================================
#  CORE MESSAGE PROCESSOR
# ============================================================

def process_message(phone: str, user_name: str, body: str):
    sess = get_session(phone)
    body = body.strip()
    low  = body.lower()
    hist = sess.setdefault("history", [])
    hist.append({"ts": datetime.now(timezone.utc).isoformat(), "text": body})

    if low in ("hi", "hello", "hey", "start", "/start"):
        sess["menu"] = "main"
        sess["context"] = {}
        send_text_message(phone, welcome_msg(user_name))
        _send_main_menu(phone, sess)
        return

    if low in ("menu", "/menu", "0", "back", "home"):
        sess["menu"] = "main"
        sess["context"] = {}
        _send_main_menu(phone, sess)
        return

    current_options = sess.get("options", [])
    matched_key = None
    for label, key in current_options:
        if body == key:
            matched_key = key
            break
    if matched_key is None:
        for label, key in current_options:
            if low == label.strip().lower():
                matched_key = key
                break

    if matched_key is not None:
        route(phone, user_name, matched_key, sess)
        return

    # Anything that isn't a recognised menu tap goes back to the main menu.
    send_text_message(phone, "Sorry, I didn't understand that. Here's the main menu:")
    _send_main_menu(phone, sess)


def route(phone: str, user_name: str, key: str, sess: dict):
    # -- Main menu -------------------------------------------------------
    if key == "main":
        sess["menu"] = "main"
        sess["context"] = {}
        _send_main_menu(phone, sess)

    # -- Browse Products ---------------------------------------------------
    elif key == "products":
        sess["options"] = PRODUCT_CAT_OPTIONS
        send_menu(phone, "Browse Products", "Choose a product category.",
                  PRODUCT_CAT_OPTIONS, "Choose an option")

    elif key.startswith("cat:"):
        cat_key = key.split(":", 1)[1]
        info = CATEGORY_INFO.get(cat_key)
        if info:
            send_cta_buttons(phone, info["desc"], [
                {"type": "URL", "title": info["button"], "url": info["url"]},
            ])
            sess["options"] = [("Categories", "products"), ("Main Menu", "main")]
            send_back_menu(phone, [("Categories", "products")])
        else:
            _send_main_menu(phone, sess)

    # -- Purchase ------------------------------------------------------------
    elif key == "purchase":
        sess["options"] = PURCHASE_STATE_OPTIONS
        send_menu(phone, "Purchase", "Select your state.",
                  PURCHASE_STATE_OPTIONS, "Choose an option")

    elif key.startswith("state:"):
        state_key = key.split(":", 1)[1]
        info = STATE_INFO.get(state_key)
        if info:
            body = (
                f"{info['label']} Region\n\n"
                f"For sales enquiries, pricing, dealer information and product "
                f"availability, please contact the {info['team']}."
            )
            send_cta_buttons(phone, body, [
                {"type": "PHONE_NUMBER", "title": "Call Us", "phone": info["phone"]},
                {"type": "URL", "title": "Email Us", "url": f"mailto:{info['email']}"},
            ])
            sess["options"] = [("States", "purchase"), ("Main Menu", "main")]
            send_back_menu(phone, [("States", "purchase")])
        else:
            _send_main_menu(phone, sess)

    # -- Technical Support -----------------------------------------------------
    elif key == "support":
        send_cta_buttons(phone, SUPPORT_BODY, [
            {"type": "URL", "title": "Locate Service Centre", "url": SUPPORT_URL},
        ])
        sess["options"] = [("Main Menu", "main")]
        send_back_menu(phone)

    # -- Warranty Registration ---------------------------------------------------
    elif key == "warranty":
        send_cta_buttons(phone, WARRANTY_BODY, [
            {"type": "URL", "title": "Register Now", "url": WARRANTY_URL},
        ])
        sess["options"] = [("Main Menu", "main")]
        send_back_menu(phone)

    # -- Sigma Loyalty Program ---------------------------------------------------
    elif key == "loyalty":
        send_cta_buttons(phone, LOYALTY_BODY, [
            {"type": "URL", "title": "Join Now", "url": LOYALTY_URL},
        ])
        sess["options"] = [("Main Menu", "main")]
        send_back_menu(phone)

    # -- Fallback ------------------------------------------------------------------
    else:
        _send_main_menu(phone, sess)


# ============================================================
#  TWILIO WEBHOOK
# ============================================================

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
            send_text_message(from_number, "Something went wrong. Please send menu to restart.")
        except Exception:
            pass

    return str(MessagingResponse()), 200, {"Content-Type": "text/xml"}


@app_flask.route("/health", methods=["GET"])
def health():
    return {"status": "ok", "bot": "Sigma WhatsApp Bot"}, 200


# ============================================================
#  ENTRY POINT
# ============================================================

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
    print("  Sigma AI WhatsApp Bot (Twilio)")
    print("  Webhook URL: POST /whatsapp")
    print("  Health:      GET  /health")
    print("  Running on   http://0.0.0.0:5000")
    print("=" * 56)

    app_flask.run(host="0.0.0.0", port=5000, debug=False)


if __name__ == "__main__":
    main()
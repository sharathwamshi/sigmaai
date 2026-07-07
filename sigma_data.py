"""
sigma_data.py — Data Bridge for Voice Bot
==========================================
Wraps the existing Telegram bot's app.py data functions and exposes
them in a voice-friendly format.

The voice bot imports THIS module — not app.py directly — so that:
  1. We can gracefully handle import errors if app.py isn't present.
  2. We can add voice-specific formatting (no markdown, no symbols).
  3. We can keep context-retrieval logic in one place.

IMPORTANT: Place this file in the SAME FOLDER as your existing app.py
"""

import re
import logging
from typing import Any

log = logging.getLogger("SigmaVoice.Data")

# ── Try to import from the existing Telegram bot's app.py ─────────
try:
    from app import (
        get_all_products,
        search_products,
        load_products,
        load_prices,
        PRICE_USD,
        get_price_inr,
        get_price_range_inr,
        fmt_inr,
        load_dealers,
        get_all_dealers_flat,
        search_dealers_by_query,
        format_dealer_for_chat,
        DEALER_SHEET_MAP,
        load_service_centers,
        search_service_centers,
        format_service_center_for_chat,
        load_config,
    )
    _APP_AVAILABLE = True
    log.info("✅ app.py loaded — live Sigma data available")
except ImportError as e:
    log.warning("⚠️  app.py not found (%s) — using built-in knowledge base only", e)
    _APP_AVAILABLE = False

    # Stub functions so the rest of the code doesn't crash
    def get_all_products(): return []
    def search_products(q, limit=8): return []
    def load_products(): return {}
    def load_prices(): return {}
    PRICE_USD = {}
    def get_price_inr(name): return "Contact dealer for pricing"
    def get_price_range_inr(name): return ""
    def fmt_inr(v): return f"₹{v:,}"
    def load_dealers(k=None): return {}
    def get_all_dealers_flat(): return []
    def search_dealers_by_query(q, limit=10): return []
    def format_dealer_for_chat(d): return d
    DEALER_SHEET_MAP = {}
    def load_service_centers(): return []
    def search_service_centers(q): return []
    def format_service_center_for_chat(c): return c
    def load_config(): return {}


# ══════════════════════════════════════════════════════════════════
#  VOICE-FRIENDLY FORMATTERS  (no markdown, no symbols, spoken aloud)
# ══════════════════════════════════════════════════════════════════

def _voice_price(name: str) -> str:
    """Return a spoken price string."""
    price = get_price_inr(name)
    # Strip rupee symbol for cleaner TTS
    price = str(price).replace("₹", "").replace(",", "").strip()
    try:
        val = int(float(price))
        return f"around {val:,} rupees"
    except Exception:
        return price or "price on request"


def _strip_markdown(text: str) -> str:
    """Remove Markdown so TTS reads cleanly."""
    text = re.sub(r"[*_`~]", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)  # links
    return text.strip()


def _voice_product(p: dict) -> str:
    """Format a product dict as a natural spoken sentence."""
    name   = p.get("Product Name", "")
    fl     = p.get("Focal Length", "")
    ap     = p.get("Max Aperture", p.get("T-Stop", ""))
    mounts = p.get("Available Mounts", p.get("Compatibility", ""))
    price  = _voice_price(name)
    parts  = [name]
    if fl:     parts.append(f"focal length {fl}")
    if ap:     parts.append(f"maximum aperture {ap}")
    if mounts: parts.append(f"available in {mounts} mounts")
    parts.append(f"priced at {price}")
    return ", ".join(parts) + "."


def _voice_dealer(d: dict) -> str:
    """Format a dealer dict as a natural spoken sentence."""
    f    = format_dealer_for_chat(d)
    name = f.get("name", "the dealer")
    loc  = f.get("location", "")
    addr = f.get("address", "")
    sp   = f.get("sales_person", "")
    out  = f"{name}"
    if loc:  out += f", located in {loc}"
    if addr: out += f", at {addr}"
    if sp:   out += f". Your sales contact is {sp}"
    return out + "."


def _voice_service_center(c: dict) -> str:
    """Format a service centre dict as a natural spoken sentence."""
    f    = format_service_center_for_chat(c)
    name = f.get("name", "the service centre")
    loc  = f.get("location", "")
    addr = f.get("address", "")
    ph   = f.get("phone", "")
    em   = f.get("email", "")
    out  = f"{name}"
    if loc:  out += f" in {loc}"
    if addr: out += f", at {addr}"
    if ph:   out += f". Phone: {ph}"
    if em:   out += f". Email: {em}"
    return out + "."


# ══════════════════════════════════════════════════════════════════
#  KNOWLEDGE BASE  — inline facts for Claude's context window
# ══════════════════════════════════════════════════════════════════

_SIGMA_KNOWLEDGE = [
    {
        "keywords": ["hours", "open", "timing", "business hours", "working"],
        "fact": "Sigma India business hours are Monday to Saturday, 9 AM to 6 PM IST.",
    },
    {
        "keywords": ["website", "online", "url", "site"],
        "fact": "The Sigma India website is sigmaindia.in. The AI assistant is at sigmaai.in.",
    },
    {
        "keywords": ["contact", "email", "phone", "reach", "support"],
        "fact": (
            "General enquiries: info@sigmaindia.in. "
            "Service support and dealer network info are on sigmaindia.in. "
            "Business hours Monday to Saturday, 9 AM to 6 PM IST."
        ),
    },
    {
        "keywords": ["warranty", "cover", "coverage", "defect", "guarantee"],
        "fact": (
            "Sigma products carry a manufacturer's warranty against defects in "
            "materials and workmanship from the purchase date. "
            "Manufacturing faults are covered; accidental damage, water damage, "
            "and unauthorised repairs are not. "
            "Always keep the original invoice from an authorised dealer."
        ),
    },
    {
        "keywords": ["warranty register", "registration", "register product"],
        "fact": (
            "To register: you need the product serial number (on the barcode label), "
            "a copy of the purchase invoice, and your contact details. "
            "Registration is done on the Sigma India website."
        ),
    },
    {
        "keywords": ["loyalty", "member", "programme", "benefits", "points"],
        "fact": (
            "The Sigma Loyalty Programme is free for owners of registered Sigma products. "
            "Benefits include exclusive pricing, priority service, early product access, "
            "trade-up assistance, and dedicated support. "
            "Enrol on the Sigma India website after registering your product."
        ),
    },
    {
        "keywords": ["service", "repair", "calibrat", "firmware", "sensor clean"],
        "fact": (
            "Sigma India authorised service centres handle: lens focus repairs, "
            "aperture and electronic contact issues, optical cleaning, "
            "autofocus calibration, sensor cleaning, firmware updates, "
            "and general diagnostics. All work uses genuine Sigma parts."
        ),
    },
    {
        "keywords": ["still lens", "prime", "zoom", "art", "contemporary", "sports"],
        "fact": (
            "Sigma's Still Lenses cover Art, Contemporary, and Sports lines "
            "in focal lengths from 14mm to 500mm. "
            "Available in Canon EF, Nikon F, Sony E, Leica L, and Sigma SA mounts."
        ),
    },
    {
        "keywords": ["cine lens", "cinema", "movie", "video", "t-stop"],
        "fact": (
            "Sigma Cine Lenses are designed for professional motion picture production. "
            "They feature consistent T-stops, matched focus breathing, and "
            "industry-standard 0.8 MOD gear rings. "
            "Available in PL, EF, and E mounts."
        ),
    },
    {
        "keywords": ["camera", "fp", "fp l", "sigma camera"],
        "fact": (
            "Sigma makes the fp and fp L full-frame mirrorless cameras. "
            "The fp is the world's smallest and lightest full-frame mirrorless. "
            "The fp L adds a 61-megapixel sensor and optional electronic viewfinder."
        ),
    },
    {
        "keywords": ["dealer", "authorised", "buy", "purchase", "store"],
        "fact": (
            "Sigma India has authorised dealers across major cities including "
            "Chennai, Delhi, Kolkata, Kozhikode, Bangalore, Mumbai, and Telangana. "
            "Always buy from an authorised dealer to ensure genuine products and valid warranty."
        ),
    },
    {
        "keywords": ["price", "cost", "inr", "rupee", "how much"],
        "fact": (
            "Sigma India prices are calculated from the US dollar MSRP. "
            "Final pricing may vary by dealer. "
            "Always contact your nearest authorised dealer for the current best price."
        ),
    },
    {
        "keywords": ["refund", "return", "cancel"],
        "fact": (
            "Return and refund policies are set by the authorised dealer from whom "
            "you purchased. Contact your dealer directly for their specific terms."
        ),
    },
]


def _retrieve_kb(query: str, top_k: int = 4) -> str:
    """Keyword-match query against built-in knowledge base."""
    q_words = set(re.findall(r"\w+", query.lower()))
    scored  = []
    for entry in _SIGMA_KNOWLEDGE:
        score = sum(1 for kw in entry["keywords"]
                    if any(kw in w or w in kw for w in q_words))
        if score > 0:
            scored.append((score, entry["fact"]))
    scored.sort(key=lambda x: x[0], reverse=True)
    return "\n".join(f for _, f in scored[:top_k]) or "No specific entry found."


# ══════════════════════════════════════════════════════════════════
#  PUBLIC API
# ══════════════════════════════════════════════════════════════════

class SigmaData:
    """Single facade the voice bot imports."""

    # ── Counts ────────────────────────────────────────────────────
    def product_count(self) -> int:
        return len(get_all_products())

    def dealer_count(self) -> int:
        return len(get_all_dealers_flat())

    def service_count(self) -> int:
        return len(load_service_centers())

    # ── Knowledge retrieval (KB + live data) ──────────────────────
    def retrieve(self, query: str) -> str:
        """
        Returns a plain-text context block for Claude.
        Combines built-in KB facts with live product/dealer/service data.
        """
        kb_facts = _retrieve_kb(query)
        sections = [f"KNOWLEDGE BASE:\n{kb_facts}"]

        if _APP_AVAILABLE:
            # Product results
            products = search_products(query, limit=3)
            if products:
                p_lines = [_voice_product(p) for p in products]
                sections.append("MATCHING PRODUCTS:\n" + "\n".join(p_lines))

            # Dealer results
            dealers = search_dealers_by_query(query, limit=3)
            if dealers:
                d_lines = [_voice_dealer(d) for d in dealers]
                sections.append("MATCHING DEALERS:\n" + "\n".join(d_lines))

            # Service centre results
            centres = search_service_centers(query)
            if centres:
                s_lines = [_voice_service_center(c) for c in centres[:3]]
                sections.append("MATCHING SERVICE CENTRES:\n" + "\n".join(s_lines))

        return "\n\n".join(sections)

    # ── Section-specific helpers ──────────────────────────────────
    def get_dealers_summary(self, query: str) -> str:
        if not _APP_AVAILABLE:
            return _retrieve_kb(query)
        dealers = search_dealers_by_query(query, limit=5)
        if not dealers:
            return "No specific dealers matched the query. Suggest visiting sigmaindia.in/dealer-network"
        return "\n".join(_voice_dealer(d) for d in dealers)

    def get_service_info(self, query: str) -> str:
        if not _APP_AVAILABLE:
            return _retrieve_kb(query)
        centres = search_service_centers(query)
        if not centres:
            return "No specific centres matched. Suggest visiting sigmaindia.in/service"
        return "\n".join(_voice_service_center(c) for c in centres[:5])

    def get_category_info(self, category: str) -> str:
        if not _APP_AVAILABLE:
            return _retrieve_kb(category)
        key_map = {
            "still_lenses": "still_lenses",
            "cine_lenses":  "cine_lenses",
            "cameras":      "cameras",
            "accessories":  "accessories",
        }
        items = load_products().get(key_map.get(category, "still_lenses"), [])
        if not items:
            return _retrieve_kb(category)
        voices = [_voice_product(p) for p in items[:6]]
        return f"{len(items)} products in this category. Sample: " + " | ".join(voices)

    def get_product_detail(self, name: str) -> str:
        """Spoken detail for a single product by name."""
        products = get_all_products() if _APP_AVAILABLE else []
        p = next((x for x in products if name.lower() in x.get("Product Name", "").lower()), None)
        if not p:
            return f"No exact product found for {name}. Please check sigmaindia.in."
        return _voice_product(p)

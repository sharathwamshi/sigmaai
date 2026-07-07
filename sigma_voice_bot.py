"""
╔══════════════════════════════════════════════════════════════════╗
║         SIGMA AI — Twilio Voice Bot                              ║
║  Mirrors the Telegram bot: Sales / Services / Warranty / Loyalty ║
║  Run: python sigma_voice_bot.py                                  ║
╚══════════════════════════════════════════════════════════════════╝

VOICE CALL FLOW
───────────────
  Inbound call
    → Welcome greeting + "Say Sales, Services, Warranty, or Loyalty"
    → [Sales]    → Products / Pricing / Find a Dealer
    → [Services] → Find a Service Centre / What We Service / Contact
    → [Warranty] → Terms / Register / Check Status
    → [Loyalty]  → Benefits / How to Join / My Status
    → Free-text query at any point → Claude AI answers from Sigma KB
    → "Go back" / "Main menu" → returns to top
    → "Goodbye"  → professional farewell + hang-up

STACK (all free tiers)
──────────────────────
  • Twilio   — call routing, built-in STT via <Gather>, Polly voice
  • Flask    — lightweight webhook server
  • Claude   — Anthropic claude-sonnet-4-6 (intelligence layer)
  • gTTS     — Google Text-to-Speech MP3 fallback (no quota)
  • python-dotenv — env management
"""

import os, sys, logging
from pathlib import Path
from flask import Flask, request, Response, url_for
from twilio.twiml.voice_response import VoiceResponse, Gather, Say, Pause
from dotenv import load_dotenv
import anthropic

# ── sibling modules ────────────────────────────────────────────────
from sigma_data    import SigmaData
from voice_session import VoiceSessionManager
from voice_tts     import speak_or_say

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("SigmaVoice")

app   = Flask(__name__)
ai    = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
data  = SigmaData()
sess  = VoiceSessionManager()

AUDIO_DIR = Path("static/audio")
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

# ══════════════════════════════════════════════════════════════════
#  VOICE CONSTANTS  — polished, professional phrasing
# ══════════════════════════════════════════════════════════════════
VOICE    = "Polly.Joanna"   # Amazon Polly via Twilio — free, sounds great
LANG     = "en-US"
TIMEOUT  = 7                # seconds of silence before re-prompting

HOLD_MSG = (
    "Thank you for your patience. "
    "I'm looking that up for you now."
)
NO_INPUT_MSG = (
    "I'm sorry, I didn't catch that. "
    "Could you please repeat your request?"
)
FAREWELL_MSG = (
    "Thank you for calling Sigma India. "
    "It was a pleasure assisting you today. "
    "Have a wonderful day. Goodbye!"
)
MAIN_MENU_PROMPT = (
    "You can say Sales for products and pricing, "
    "Services for repairs and service centres, "
    "Warranty for coverage and registration, "
    "or Loyalty for our membership programme. "
    "You can also describe what you're looking for in your own words."
)
TRANSFER_MSG = (
    "I'm connecting you to our support team. "
    "Please stay on the line."
)

# ══════════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════════
def _say(response: VoiceResponse, text: str) -> None:
    """Append a <Say> with consistent Polly voice."""
    response.say(text, voice=VOICE, language=LANG)


def _gather(action: str, prompt: str,
            hints: str = "", timeout: int = TIMEOUT) -> Gather:
    """Return a configured <Gather> element."""
    g = Gather(
        input="speech",
        action=action,
        method="POST",
        timeout=timeout,
        speech_timeout="auto",
        language=LANG,
        hints=hints,
    )
    g.say(prompt, voice=VOICE, language=LANG)
    return g


def _hold(response: VoiceResponse) -> None:
    """Short 'hold' message while Claude processes."""
    response.say(HOLD_MSG, voice=VOICE, language=LANG)
    response.pause(length=1)


def _ai_answer(call_sid: str, question: str, context_hint: str = "") -> str:
    """
    Ask Claude about Sigma India using full session history + KB context.
    Returns a SHORT spoken-friendly answer (2–4 sentences).
    """
    history = sess.get_history(call_sid)
    kb_ctx  = data.retrieve(question)

    system = f"""You are the professional Sigma India voice assistant.
You answer callers' questions about Sigma lenses, cameras, accessories, 
dealers, service centres, pricing, warranty, and the loyalty programme.

RULES:
- Keep every answer to 2–4 spoken sentences — this is a phone call.
- No bullet points, markdown, asterisks, or special characters.
- Numbers: say rupees not the symbol. Say "around" before price ranges.
- If you don't know something, say so politely and suggest the website sigmaindia.in
- Never say "As an AI".
- Speak warmly and professionally at all times.

SIGMA KNOWLEDGE BASE:
{kb_ctx}

{f"CURRENT TOPIC: {context_hint}" if context_hint else ""}
"""
    msgs = history + [{"role": "user", "content": question}]
    resp = ai.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=250,
        system=system,
        messages=msgs,
    )
    answer = resp.content[0].text.strip()
    sess.add_turn(call_sid, question, answer)
    log.info("AI [%s] Q: %s | A: %s", call_sid[:8], question, answer[:80])
    return answer


def _detect_intent(text: str) -> str:
    """Map spoken words → intent key."""
    t = text.lower()

    # Farewell
    if any(w in t for w in ["bye", "goodbye", "hang up", "end call",
                             "that's all", "thats all", "no thanks",
                             "nothing else", "no thank you"]):
        return "bye"

    # Navigation — main menu
    if any(w in t for w in ["main menu", "go back", "back", "start over",
                             "beginning", "restart", "home"]):
        return "main_menu"

    # Human agent
    if any(w in t for w in ["human", "agent", "person", "representative",
                             "speak to someone", "transfer"]):
        return "transfer"

    # Top-level sections
    if "sales" in t or "buy" in t or "purchase" in t or "price" in t or \
       "product" in t or "lens" in t or "camera" in t or "accessory" in t or \
       "accessories" in t:
        return "sales"

    if "service" in t or "repair" in t or "fix" in t or "calibrat" in t or \
       "centre" in t or "center" in t:
        return "services"

    if "warrant" in t or "register" in t or "coverage" in t or "claim" in t:
        return "warranty"

    if "loyal" in t or "member" in t or "benefit" in t or "programme" in t:
        return "loyalty"

    # Sales sub-intents
    if "dealer" in t or "store" in t or "shop" in t or "outlet" in t or \
       "nearest" in t or "where can i" in t:
        return "dealers"

    if "still" in t and ("lens" in t or "lenses" in t):
        return "still_lenses"
    if "cine" in t and ("lens" in t or "lenses" in t):
        return "cine_lenses"

    # Warranty sub-intents
    if "terms" in t or "condition" in t or "cover" in t:
        return "warranty_terms"
    if "register" in t or "registration" in t:
        return "warranty_register"
    if "status" in t or "check" in t or "track" in t:
        return "warranty_status"

    # Loyalty sub-intents
    if "benefit" in t or "perk" in t or "offer" in t:
        return "loyalty_benefits"
    if "join" in t or "enrol" in t or "sign up" in t or "how to" in t:
        return "loyalty_join"

    # Contact
    if "contact" in t or "email" in t or "phone" in t or "call" in t:
        return "contact"

    return "freeform"


# ══════════════════════════════════════════════════════════════════
#  ROUTE: /voice/inbound  — entry point for every call
# ══════════════════════════════════════════════════════════════════
@app.route("/voice/inbound", methods=["GET","POST"])
def inbound():
    call_sid = request.values.get("CallSid", "unknown")
    caller   = request.values.get("From", "unknown")
    log.info("Inbound call | SID=%s | From=%s", call_sid, caller)

    sess.create(call_sid)

    response = VoiceResponse()

    # Language selection: English only (extendable later)
    g = Gather(
        input="speech dtmf",
        action=url_for("language_confirm", _external=True),
        method="POST",
        timeout=6,
        num_digits=1,
        language=LANG,
    )
    g.say(
        "Welcome to Sigma India. "
        "To continue in English, please say English, or press 1.",
        voice=VOICE, language=LANG,
    )
    response.append(g)
    # Fallback if no input: just proceed in English
    response.redirect(url_for("language_confirm", _external=True), method="POST")
    return Response(str(response), mimetype="text/xml")


# ══════════════════════════════════════════════════════════════════
#  ROUTE: /voice/language  — confirm language, enter main menu
# ══════════════════════════════════════════════════════════════════
@app.route("/voice/language", methods=["GET","POST"])
def language_confirm():
    call_sid = request.values.get("CallSid", "unknown")
    speech   = (request.values.get("SpeechResult") or "").lower()
    digits   = request.values.get("Digits", "").strip()

    log.info("Language confirm | SID=%s | speech=%r | digits=%r",
             call_sid, speech, digits)

    response = VoiceResponse()
    g = _gather(
        action=url_for("main_menu_input", _external=True),
        prompt=(
            "Thank you. You're connected to the Sigma India voice assistant. "
            + MAIN_MENU_PROMPT
        ),
        hints=(
            "Sales, Services, Warranty, Loyalty, products, pricing, "
            "dealer, service centre, lens, camera"
        ),
        timeout=8,
    )
    response.append(g)
    response.redirect(url_for("no_input", _external=True), method="POST")
    return Response(str(response), mimetype="text/xml")


# ══════════════════════════════════════════════════════════════════
#  ROUTE: /voice/menu  — main menu handler
# ══════════════════════════════════════════════════════════════════
@app.route("/voice/menu", methods=["GET","POST"])
def main_menu_input():
    call_sid = request.values.get("CallSid", "unknown")
    speech   = (request.values.get("SpeechResult") or "").strip()
    log.info("Main menu | SID=%s | speech=%r", call_sid, speech)

    if not speech:
        return _redirect_no_input()

    intent   = _detect_intent(speech)
    response = VoiceResponse()

    if intent == "bye":
        return _farewell()

    if intent == "sales":
        return _sales_intro(call_sid)

    if intent == "services":
        return _services_intro(call_sid)

    if intent == "warranty":
        return _warranty_intro(call_sid)

    if intent == "loyalty":
        return _loyalty_intro(call_sid)

    if intent == "transfer":
        response = VoiceResponse()
        _say(response, TRANSFER_MSG)
        response.hangup()
        return Response(str(response), mimetype="text/xml")

    # Freeform — let Claude answer
    _hold(response)
    try:
        answer = _ai_answer(call_sid, speech)
    except Exception as e:
        log.error("AI error: %s", e)
        answer = ("I'm sorry, I encountered a brief technical issue. "
                  "Please try again or visit sigmaindia.in for assistance.")

    g = _gather(
        action=url_for("main_menu_input", _external=True),
        prompt=answer + " Is there anything else I can help you with?",
        hints="Sales, Services, Warranty, Loyalty, goodbye",
    )
    response.append(g)
    response.redirect(url_for("no_input", _external=True), method="POST")
    return Response(str(response), mimetype="text/xml")


# ══════════════════════════════════════════════════════════════════
#  SALES SECTION
# ══════════════════════════════════════════════════════════════════
def _sales_intro(call_sid: str):
    products = data.product_count()
    dealers  = data.dealer_count()
    response = VoiceResponse()
    g = _gather(
        action=url_for("sales_input", _external=True),
        prompt=(
            f"Welcome to Sales. "
            f"We have {products} products across Still Lenses, Cine Lenses, "
            f"Cameras, and Accessories, with {dealers} authorised dealers across India. "
            "You can say: Browse Products, View Pricing, or Find a Dealer. "
            "You can also ask about any specific product by name."
        ),
        hints=(
            "Browse products, View pricing, Find a dealer, Still lenses, "
            "Cine lenses, Cameras, Accessories, main menu, back"
        ),
    )
    response.append(g)
    response.redirect(url_for("no_input", _external=True), method="POST")
    return Response(str(response), mimetype="text/xml")


@app.route("/voice/sales", methods=["GET","POST"])
def sales_input():
    call_sid = request.values.get("CallSid", "unknown")
    speech   = (request.values.get("SpeechResult") or "").strip()
    log.info("Sales | SID=%s | speech=%r", call_sid, speech)

    if not speech:
        return _redirect_no_input()

    intent   = _detect_intent(speech)
    response = VoiceResponse()

    if intent in ("bye", "main_menu"):
        return _handle_nav(intent, call_sid)

    if intent == "dealers":
        return _dealers_handler(call_sid, speech)

    if intent in ("still_lenses", "cine_lenses"):
        return _category_handler(call_sid, intent, speech)

    # Products / pricing / freeform product questions
    _hold(response)
    try:
        answer = _ai_answer(call_sid, speech, context_hint="Sales — Products and Pricing")
    except Exception as e:
        log.error("AI error: %s", e)
        answer = "I'm sorry, I couldn't retrieve that information right now. Please try again."

    g = _gather(
        action=url_for("sales_input", _external=True),
        prompt=answer + " Would you like to know anything else about our products or pricing?",
        hints="pricing, dealer, still lens, cine lens, camera, main menu, goodbye",
    )
    response.append(g)
    response.redirect(url_for("no_input", _external=True), method="POST")
    return Response(str(response), mimetype="text/xml")


def _dealers_handler(call_sid: str, speech: str):
    response = VoiceResponse()
    _hold(response)
    dealers_info = data.get_dealers_summary(speech)
    answer = _ai_answer(
        call_sid,
        f"The caller asked: {speech}. Use this dealer information: {dealers_info}",
        context_hint="Sales — Find a Dealer"
    )
    g = _gather(
        action=url_for("sales_input", _external=True),
        prompt=answer + " Can I help you find anything else?",
        hints="dealer, city, region, main menu, goodbye",
    )
    response.append(g)
    response.redirect(url_for("no_input", _external=True), method="POST")
    return Response(str(response), mimetype="text/xml")


def _category_handler(call_sid: str, category: str, speech: str):
    response = VoiceResponse()
    _hold(response)
    cat_info = data.get_category_info(category)
    answer = _ai_answer(
        call_sid,
        f"The caller asked: {speech}. Category info: {cat_info}",
        context_hint=f"Sales — {category.replace('_', ' ').title()}"
    )
    g = _gather(
        action=url_for("sales_input", _external=True),
        prompt=answer + " Would you like details on a specific lens?",
        hints="focal length, aperture, price, mount, main menu, goodbye",
    )
    response.append(g)
    response.redirect(url_for("no_input", _external=True), method="POST")
    return Response(str(response), mimetype="text/xml")


# ══════════════════════════════════════════════════════════════════
#  SERVICES SECTION
# ══════════════════════════════════════════════════════════════════
def _services_intro(call_sid: str):
    centers = data.service_count()
    response = VoiceResponse()
    g = _gather(
        action=url_for("services_input", _external=True),
        prompt=(
            f"Welcome to Services. "
            f"We have {centers} authorised service centres across India, "
            "all trained to Sigma's standards using genuine parts. "
            "You can say: Find a Service Centre, What We Service, or Contact Support. "
            "Or tell me your city and I'll find the nearest centre."
        ),
        hints=(
            "Find a service centre, What we service, Contact support, "
            "Mumbai, Delhi, Chennai, Bangalore, Kolkata, main menu, back"
        ),
    )
    response.append(g)
    response.redirect(url_for("no_input", _external=True), method="POST")
    return Response(str(response), mimetype="text/xml")


@app.route("/voice/services", methods=["GET","POST"])
def services_input():
    call_sid = request.values.get("CallSid", "unknown")
    speech   = (request.values.get("SpeechResult") or "").strip()
    log.info("Services | SID=%s | speech=%r", call_sid, speech)

    if not speech:
        return _redirect_no_input()

    intent   = _detect_intent(speech)
    response = VoiceResponse()

    if intent in ("bye", "main_menu"):
        return _handle_nav(intent, call_sid)

    if intent == "contact":
        return _contact_handler(call_sid)

    # Find service centre / what we service / freeform
    _hold(response)
    svc_info = data.get_service_info(speech)
    try:
        answer = _ai_answer(
            call_sid,
            f"The caller asked: {speech}. Service centre info: {svc_info}",
            context_hint="Services — Service Centres and Repairs"
        )
    except Exception as e:
        log.error("AI error: %s", e)
        answer = "I'm sorry, I couldn't retrieve that right now. Please visit sigmaindia.in."

    g = _gather(
        action=url_for("services_input", _external=True),
        prompt=answer + " Is there anything else I can help you with regarding service?",
        hints="service centre, repair, calibration, contact, main menu, goodbye",
    )
    response.append(g)
    response.redirect(url_for("no_input", _external=True), method="POST")
    return Response(str(response), mimetype="text/xml")


def _contact_handler(call_sid: str):
    response = VoiceResponse()
    g = _gather(
        action=url_for("services_input", _external=True),
        prompt=(
            "You can reach Sigma India at info@sigmaindia.in for general enquiries. "
            "For service support, visit our website at sigma india dot in. "
            "Our business hours are Monday to Saturday, 9 AM to 6 PM Indian Standard Time. "
            "Is there anything else I can help you with?"
        ),
        hints="service, dealer, warranty, main menu, goodbye",
    )
    response.append(g)
    response.redirect(url_for("no_input", _external=True), method="POST")
    return Response(str(response), mimetype="text/xml")


# ══════════════════════════════════════════════════════════════════
#  WARRANTY SECTION
# ══════════════════════════════════════════════════════════════════
def _warranty_intro(call_sid: str):
    response = VoiceResponse()
    g = _gather(
        action=url_for("warranty_input", _external=True),
        prompt=(
            "Welcome to Warranty. "
            "Every Sigma product sold through our authorised channels in India "
            "is backed by a manufacturer's warranty. "
            "You can say: Warranty Terms, Register Your Product, or Check Warranty Status. "
            "What would you like to know?"
        ),
        hints=(
            "Warranty terms, Register product, Check status, "
            "claim, coverage, repair, main menu, back"
        ),
    )
    response.append(g)
    response.redirect(url_for("no_input", _external=True), method="POST")
    return Response(str(response), mimetype="text/xml")


@app.route("/voice/warranty", methods=["GET","POST"])
def warranty_input():
    call_sid = request.values.get("CallSid", "unknown")
    speech   = (request.values.get("SpeechResult") or "").strip()
    log.info("Warranty | SID=%s | speech=%r", call_sid, speech)

    if not speech:
        return _redirect_no_input()

    intent   = _detect_intent(speech)
    response = VoiceResponse()

    if intent in ("bye", "main_menu"):
        return _handle_nav(intent, call_sid)

    # Map to sub-intent scripts
    if intent == "warranty_terms" or "term" in speech.lower() or "cover" in speech.lower():
        answer = (
            "Sigma products carry a standard manufacturer's warranty against defects "
            "in materials and workmanship from the date of purchase. "
            "Manufacturing faults in focusing mechanisms, electronics, and build quality "
            "are all covered. Accidental damage, water damage, and unauthorised repairs "
            "are outside the scope of the warranty. Always keep your original invoice "
            "from an authorised dealer as your primary proof of purchase."
        )
    elif intent == "warranty_register" or "register" in speech.lower():
        answer = (
            "Registering your Sigma product is quick and free. "
            "You'll need your product's serial number, found on the barcode label or lens barrel, "
            "along with a copy of your purchase invoice and your contact details. "
            "You can complete registration on the Sigma India website."
        )
    elif intent == "warranty_status" or "status" in speech.lower() or "check" in speech.lower():
        answer = (
            "To check your warranty or repair status, please have your product serial number, "
            "your service request or job sheet number if a repair is in progress, "
            "and the mobile number or email used at registration. "
            "Our support team can look this up for you, or you can use the warranty "
            "status lookup on the Sigma India website."
        )
    else:
        _hold(response)
        try:
            answer = _ai_answer(call_sid, speech, context_hint="Warranty")
        except Exception as e:
            log.error("AI error: %s", e)
            answer = "I'm sorry, I couldn't retrieve that right now. Please visit sigmaindia.in."

    g = _gather(
        action=url_for("warranty_input", _external=True),
        prompt=answer + " Is there anything else I can help you with regarding warranty?",
        hints="terms, register, status, claim, main menu, goodbye",
    )
    response.append(g)
    response.redirect(url_for("no_input", _external=True), method="POST")
    return Response(str(response), mimetype="text/xml")


# ══════════════════════════════════════════════════════════════════
#  LOYALTY SECTION
# ══════════════════════════════════════════════════════════════════
def _loyalty_intro(call_sid: str):
    response = VoiceResponse()
    g = _gather(
        action=url_for("loyalty_input", _external=True),
        prompt=(
            "Welcome to the Sigma Loyalty Programme. "
            "Joining is free for owners of registered Sigma products. "
            "You can say: Member Benefits, How to Join, or Check My Status. "
            "What would you like to know?"
        ),
        hints=(
            "Member benefits, How to join, Check my status, "
            "offers, priority, upgrade, main menu, back"
        ),
    )
    response.append(g)
    response.redirect(url_for("no_input", _external=True), method="POST")
    return Response(str(response), mimetype="text/xml")


@app.route("/voice/loyalty", methods=["GET","POST"])
def loyalty_input():
    call_sid = request.values.get("CallSid", "unknown")
    speech   = (request.values.get("SpeechResult") or "").strip()
    log.info("Loyalty | SID=%s | speech=%r", call_sid, speech)

    if not speech:
        return _redirect_no_input()

    intent = _detect_intent(speech)
    response = VoiceResponse()

    if intent in ("bye", "main_menu"):
        return _handle_nav(intent, call_sid)

    if intent == "loyalty_benefits" or "benefit" in speech.lower() or "perk" in speech.lower():
        answer = (
            "As a Sigma Loyalty member you'll enjoy exclusive members-only pricing and bundle deals, "
            "priority service with faster turnaround at authorised centres, "
            "early access to new product launches, "
            "preferential trade-up terms when upgrading your gear, "
            "and a dedicated support line for membership queries. "
            "Full details on benefit tiers are available on our website."
        )
    elif intent == "loyalty_join" or "join" in speech.lower() or "enrol" in speech.lower():
        answer = (
            "Joining is straightforward and completely free. "
            "First, register at least one Sigma product on our website. "
            "Then enrol in the Loyalty Programme using your registered details. "
            "Once verified, your membership benefits become active and you'll receive a confirmation."
        )
    elif "status" in speech.lower() or "check" in speech.lower():
        answer = (
            "To check your loyalty membership status, please have ready "
            "the mobile number or email used during enrolment, "
            "along with your membership ID if you have it. "
            "Our support team can verify your status, "
            "or you can log in to your account on the loyalty section of our website."
        )
    else:
        _hold(response)
        try:
            answer = _ai_answer(call_sid, speech, context_hint="Loyalty Programme")
        except Exception as e:
            log.error("AI error: %s", e)
            answer = "I'm sorry, I couldn't retrieve that right now. Please visit sigmaindia.in."

    g = _gather(
        action=url_for("loyalty_input", _external=True),
        prompt=answer + " Is there anything else about the loyalty programme I can help with?",
        hints="benefits, join, status, main menu, goodbye",
    )
    response.append(g)
    response.redirect(url_for("no_input", _external=True), method="POST")
    return Response(str(response), mimetype="text/xml")


# ══════════════════════════════════════════════════════════════════
#  SHARED FALLBACKS
# ══════════════════════════════════════════════════════════════════
@app.route("/voice/no_input", methods=["GET","POST"])
def no_input():
    call_sid = request.values.get("CallSid", "unknown")
    session  = sess.get(call_sid)
    strikes  = session.get("silence_strikes", 0) + 1
    sess.update(call_sid, silence_strikes=strikes)
    log.info("No input | SID=%s | strikes=%d", call_sid, strikes)

    response = VoiceResponse()
    if strikes >= 3:
        _say(response,
             "We haven't heard from you for a while. "
             "Thank you for calling Sigma India. Goodbye!")
        response.hangup()
        sess.close(call_sid)
    else:
        g = _gather(
            action=url_for("main_menu_input", _external=True),
            prompt=(
                "Are you still there? No problem — take your time. "
                + MAIN_MENU_PROMPT
            ),
            hints="Sales, Services, Warranty, Loyalty, goodbye",
            timeout=10,
        )
        response.append(g)
        response.redirect(url_for("no_input", _external=True), method="POST")

    return Response(str(response), mimetype="text/xml")


@app.route("/voice/status", methods=["GET","POST"])
def call_status():
    call_sid    = request.values.get("CallSid", "unknown")
    call_status = request.values.get("CallStatus", "")
    duration    = request.values.get("CallDuration", "0")
    log.info("Status | SID=%s | status=%s | duration=%ss",
             call_sid, call_status, duration)
    if call_status in ("completed", "failed", "busy", "no-answer"):
        sess.close(call_sid)
    return Response("", status=204)


@app.route("/health")
def health():
    return {
        "status": "ok",
        "service": "Sigma India Voice Assistant",
        "products": data.product_count(),
        "dealers":  data.dealer_count(),
        "service_centres": data.service_count(),
    }, 200


def _farewell():
    response = VoiceResponse()
    _say(response, FAREWELL_MSG)
    response.hangup()
    return Response(str(response), mimetype="text/xml")


def _redirect_no_input():
    response = VoiceResponse()
    response.redirect(url_for("no_input", _external=True), method="POST")
    return Response(str(response), mimetype="text/xml")


def _handle_nav(intent: str, call_sid: str):
    if intent == "bye":
        return _farewell()
    # main_menu
    response = VoiceResponse()
    g = _gather(
        action=url_for("main_menu_input", _external=True),
        prompt="Of course. " + MAIN_MENU_PROMPT,
        hints="Sales, Services, Warranty, Loyalty, goodbye",
    )
    response.append(g)
    response.redirect(url_for("no_input", _external=True), method="POST")
    return Response(str(response), mimetype="text/xml")


# ══════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    log.info("Sigma Voice Bot starting on port %d", port)
    log.info("Products: %d | Dealers: %d | Service Centres: %d",
             data.product_count(), data.dealer_count(), data.service_count())
    app.run(host="0.0.0.0", port=port, debug=False)
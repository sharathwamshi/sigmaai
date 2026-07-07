# 📞 Sigma India Voice Bot — Complete Setup Guide

## What This Does

Mirrors your Telegram bot as a phone call experience:

| Telegram | Voice Call |
|----------|-----------|
| Tap "🛒 Sales" button | Say "Sales" |
| Tap "🔧 Services" | Say "Services" |
| Tap "🛡️ Warranty" | Say "Warranty" |
| Tap "⭐ Loyalty" | Say "Loyalty" |
| Type a product name | Say the product name |
| Tap product → see specs/price | Hear specs and price read aloud |
| Tap dealer → see address | Hear dealer name and address |
| Tap "🏠 Main Menu" | Say "Main menu" or "Go back" |
| Close chat | Say "Goodbye" |

---

## Folder Structure

Place ALL these files in the SAME folder as your existing `app.py`:

```
your_project/
├── app.py                  ← your existing Telegram bot backend
├── sigma_telegram_bot.py   ← your existing Telegram bot
├── sigma_voice_bot.py      ← NEW: voice bot main server
├── sigma_data.py           ← NEW: data bridge (reads from app.py)
├── voice_session.py        ← NEW: call state management
├── voice_tts.py            ← NEW: text-to-speech helpers
├── requirements.txt        ← updated
└── .env                    ← add voice keys here
```

---

## Step 1 — Add Keys to Your `.env`

Open your existing `.env` (or create one) and add:

```bash
# Twilio
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_PHONE_NUMBER=+1XXXXXXXXXX

# Claude AI
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxxxxxxxxxx
```

---

## Step 2 — Get Your Twilio Credentials

1. Log in → https://console.twilio.com
2. Dashboard shows **Account SID** and **Auth Token** (click eye to reveal)
3. Go to **Phone Numbers → Manage → Buy a number**
4. Filter for **Voice** capability → Buy (around $1/month)
5. Copy the phone number into your `.env`

---

## Step 3 — Install Dependencies

```bash
# In your project folder (same venv as your Telegram bot)
pip install flask twilio anthropic python-dotenv gtts
```

---

## Step 4 — Run the Voice Bot Server

```bash
python sigma_voice_bot.py
```

You should see:
```
Sigma Voice Bot starting on port 5000
Products: 47 | Dealers: 83 | Service Centres: 12
```

---

## Step 5 — Expose to the Internet (Development)

Twilio needs a public HTTPS URL. Use ngrok:

```bash
# Install ngrok: https://ngrok.com/download
ngrok http 5000
```

Copy your HTTPS URL, e.g.: `https://a1b2c3d4.ngrok-free.app`

---

## Step 6 — Configure Twilio Webhooks

1. Go to: https://console.twilio.com/us1/develop/phone-numbers/manage/incoming
2. Click your phone number
3. Under **"A CALL COMES IN"**:
   - Type: **Webhook**
   - URL: `https://YOUR-NGROK-URL/voice/inbound`
   - Method: **HTTP POST**
4. Under **"Call Status Changes"**:
   - URL: `https://YOUR-NGROK-URL/voice/status`
   - Method: **HTTP POST**
5. Click **Save Configuration**

---

## Step 7 — Test It

Call your Twilio number. You'll hear:

> *"Welcome to Sigma India. To continue in English, please say English, or press 1."*

Say **"English"** → then try:
- **"Sales"** → hear product/dealer options
- **"Tell me about the 50mm Art lens"** → hear specs + price
- **"Find a dealer in Chennai"** → hear dealer details
- **"Services"** → service centre flow
- **"Warranty"** → warranty flow
- **"Loyalty"** → loyalty programme flow
- **"Goodbye"** → professional farewell

---

## Call Flow Diagram

```
INBOUND CALL
     │
     ▼
/voice/inbound
  "Welcome to Sigma India. Say English or press 1."
     │
     ▼
/voice/language
  "Thank you. You're connected to Sigma India voice assistant."
  "Say: Sales, Services, Warranty, or Loyalty."
     │
     ▼
/voice/menu ◄──────────────────────────────┐
  Detect intent from speech                 │
     │                                      │
     ├─ "Sales"    → /voice/sales ──────────┤
     ├─ "Services" → /voice/services ───────┤
     ├─ "Warranty" → /voice/warranty ───────┤
     ├─ "Loyalty"  → /voice/loyalty ────────┤
     ├─ Freeform   → Claude AI answers ─────┘
     │
     ▼
"Is there anything else I can help you with?"
     │
     └─ "Goodbye" → Farewell + Hang up
```

---

## Voice Prompts Reference

| User says | Bot does |
|-----------|----------|
| "Sales" / "buy" / "lens" / "camera" | Sales section |
| "Services" / "repair" / "service centre" | Services section |
| "Warranty" / "claim" / "register" | Warranty section |
| "Loyalty" / "member" / "benefits" | Loyalty section |
| "Find dealer in Mumbai" | Searches dealers, reads result |
| "How much is the 85mm Art?" | Reads price in rupees |
| "What service centres are in Delhi?" | Reads service centre details |
| "Main menu" / "go back" / "back" | Returns to main menu |
| "Speak to someone" / "agent" | Transfer message |
| "Goodbye" / "bye" / "that's all" | Professional farewell |
| Silence × 3 | Polite goodbye |

---

## Production Deployment

Replace ngrok with a real server. Options:

### Railway (easiest — free tier available)
```bash
pip install railway
railway login && railway up
```
Set env vars in the Railway dashboard.

### Render
- Connect GitHub repo at render.com
- Add env vars in the dashboard
- Deploy as Web Service

### Your Own Server (gunicorn)
```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 sigma_voice_bot:app
```
Update Twilio webhooks with your domain.

---

## Cost Breakdown (Free Tiers)

| Component | Cost |
|-----------|------|
| Twilio trial credit | $15 free (~150 min calls) |
| Twilio `<Say>` Polly.Joanna | Included in call cost |
| Twilio speech recognition | Included in call cost |
| Anthropic Claude Sonnet | ~$0.003 per call (very low) |
| Flask server | Free |
| gTTS fallback | Free |

After trial: Twilio Voice ~$0.0085/min inbound (US number).
Indian local number pricing varies — check Twilio console.

---

## Troubleshooting

**"No answer" when I call**
→ Check ngrok is running and the webhook URL in Twilio console matches

**"Application error"**
→ Check `python sigma_voice_bot.py` terminal for the traceback

**Caller hears nothing / silence**
→ Make sure Flask is running on port 5000 and ngrok tunnel is active

**Wrong data / prices**
→ Ensure `sigma_data.py` is in the same folder as your `app.py`

**"ModuleNotFoundError: anthropic"**
→ Run `pip install anthropic` in the same virtual environment

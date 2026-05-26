"""
Sigma AI Assistant — Full Stack
/       → Chatbot (Claude-powered)
/admin  → Admin panel (products, config, conversations, images, offers)
"""

import os, json, re, uuid, shutil
from datetime import datetime
from flask import (Flask, render_template, request, jsonify,
                   session, send_from_directory)
import openpyxl
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "sigma-assistant-2025-secret")

# ── PATHS ───────────────────────────────────────────────
BASE_DIR    = os.path.dirname(__file__)
XLSX_PATH   = os.path.join(BASE_DIR, "sigma_products.xlsx")
CONFIG_PATH = os.path.join(BASE_DIR, "data", "config.json")
CONV_PATH   = os.path.join(BASE_DIR, "data", "conversations.json")
IMAGES_DIR  = os.path.join(BASE_DIR, "static", "images")

for d in [os.path.join(BASE_DIR,"data"), IMAGES_DIR]:
    os.makedirs(d, exist_ok=True)

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "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")
CLAUDE_MODEL      = "claude-sonnet-4-20250514"
ALLOWED_EXT       = {"png","jpg","jpeg","webp","gif"}

# ═══════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════
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
    "updated_at": ""
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

# ═══════════════════════════════════════════════════════
# CONVERSATIONS
# ═══════════════════════════════════════════════════════
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
            c["message_count"] = len([m for m in messages if m["role"]=="user"])
            break
    else:
        convs.append({
            "session_id":   session_id,
            "started_at":   datetime.now().isoformat(),
            "updated_at":   datetime.now().isoformat(),
            "message_count":len([m for m in messages if m["role"]=="user"]),
            "messages":     messages
        })
    convs = sorted(convs, key=lambda x: x["updated_at"], reverse=True)[:500]
    with open(CONV_PATH, "w") as f:
        json.dump(convs, f, indent=2)

# ═══════════════════════════════════════════════════════
# PRICE HELPERS
# ═══════════════════════════════════════════════════════
PRICE_USD = {
    "14mm F1.8 DG HSM":1299,"14mm F1.4 DG DN":1599,
    "15mm F1.4 DG DN Diagonal Fisheye":1099,"20mm F1.4 DG DN":899,
    "24mm F1.4 DG DN":849,"28mm F1.4 DG HSM":799,
    "35mm F1.2 DG DN II":1599,"35mm F1.4 DG DN":899,"35mm F1.4 DG II":799,
    "50mm F1.2 DG DN":1299,"50mm F1.4 DG DN":949,"70mm F2.8 DG MACRO":599,
    "85mm F1.4 DG DN":999,"105mm F2.8 DG DN MACRO":849,"135mm F1.4 DG":1399,
    "14-24mm F2.8 DG DN":1299,"14-24mm F2.8 DG HSM":1299,"17-40mm F1.8 DC":999,
    "24-70mm F2.8 DG OS HSM":1099,"24-70mm F2.8 DG DN II":1099,
    "24-105mm F4 DG OS HSM":899,"28-45mm F1.8 DG DN":1499,
    "28-105mm F2.8 DG DN":1699,"50-100mm F1.8 DC HSM":1099,
    "17mm F4 DG":449,"20mm F2 DG":549,"24mm F2 DG":499,"24mm F3.5 DG":449,
    "35mm F2 DG":499,"45mm F2.8 DG":399,"50mm F2 DG":549,
    "65mm F2 DG":599,"90mm F2.8 DG":499,
    "12mm F1.4 DC":599,"15mm F1.4 DC":649,"16mm F1.4 DC DN":449,
    "23mm F1.4 DC DN":349,"30mm F1.4 DC DN":299,"56mm F1.4 DC DN":329,
    "10-18mm F2.8 DC DN":549,"16-28mm F2.8 DG DN":799,
    "18-50mm F2.8 DC DN":499,"16-300mm F3.5-6.7 DC OS":699,
    "20-200mm F3.5-6.3 DG":699,"28-70mm F2.8 DG DN":699,
    "100-400mm F5-6.3 DG DN OS":1099,"200mm F2 DG OS":2999,
    "500mm F5.6 DG DN OS":2199,"60-600mm F4.5-6.3 DG DN OS":2199,
    "60-600mm F4.5-6.3 DG OS HSM":1999,"70-200mm F2.8 DG DN OS":1499,
    "150-600mm F5-6.3 DG DN OS":1699,"300-600mm F4 DG OS":3999,
    "Sigma BF":1999,"Sigma fp L":2499,"Sigma fp":1499,
    "USB DOCK UD-11":59,"USB DOCK UD-01":59,
    "TELE CONVERTER TC-1401 / TC-2001":299,"TELE CONVERTER TC-1411 / TC-2011":299,
    "WR CIRCULAR PL FILTER":79,"WR UV FILTER":59,"PROTECTOR":49,
    "WR PROTECTOR":59,"WR CERAMIC PROTECTOR":99,
    "MOUNT CONVERTER MC-31":249,"MOUNT CONVERTER MC-21":249,
    "MOUNT CONVERTER MC-11":199,"FLASH USB DOCK FD-11":49,
    "ELECTRONIC VIEWFINDER EVF-11":399,"ELECTRONIC FLASH EF-630":299,
    "ELECTRONIC FLASH MACRO EM-140 DG":249,
}

def fmt_inr(usd, rate=None):
    r   = rate or load_config().get("usd_to_inr_rate", 84)
    inr = round(usd * r / 500) * 500
    return f"₹{inr/100000:.1f} Lakh" if inr>=100000 else f"₹{inr:,}"

def fmt_inr_range(usd, rate=None):
    r  = rate or load_config().get("usd_to_inr_rate", 84)
    lo = round(int(usd*r*0.96)/500)*500
    hi = round(int(usd*r*1.06)/500)*500
    f  = lambda v: f"₹{v/100000:.1f} Lakh" if v>=100000 else f"₹{v:,}"
    return f"{f(lo)} – {f(hi)}"

# ═══════════════════════════════════════════════════════
# PRODUCT DATA
# ═══════════════════════════════════════════════════════
SHEET_MAP = {
    "Still Lenses":"still_lenses",
    "Cine Lenses":"cine_lenses",
    "Cameras":"cameras",
    "Accessories":"accessories",
}

def _product_id(name):
    return re.sub(r"[^a-z0-9]","_", name.lower()).strip("_")

def _find_image(pid):
    for ext in ["jpg","jpeg","png","webp","gif"]:
        p = os.path.join(IMAGES_DIR, f"{pid}.{ext}")
        if os.path.exists(p):
            return f"/static/images/{pid}.{ext}"
    return ""

def load_products():
    products = {k:[] for k in SHEET_MAP.values()}
    try:
        wb = openpyxl.load_workbook(XLSX_PATH, read_only=True, data_only=True)
        for sheet_name, key in SHEET_MAP.items():
            if sheet_name not in wb.sheetnames: continue
            ws   = wb[sheet_name]
            rows = list(ws.iter_rows(values_only=True))
            if not rows: continue
            headers = [str(h).strip() if h else "" for h in rows[0]]
            for row in rows[1:]:
                if not any(row): continue
                item = {headers[i]: (str(row[i]).strip() if row[i] is not None else "")
                        for i in range(min(len(headers),len(row)))}
                name = item.get("Product Name","")
                if not name or name=="None": continue
                item["_category"]         = key
                item["_display_category"] = sheet_name
                item["_id"]               = _product_id(name)
                usd = PRICE_USD.get(name, 0)
                item["_price_inr"]        = fmt_inr(usd) if usd else "Contact dealer"
                item["_price_range_inr"]  = fmt_inr_range(usd) if usd else ""
                item["_price_usd"]        = usd
                item["_image"]            = _find_image(_product_id(name))
                products[key].append(item)
        wb.close()
    except Exception as e:
        print(f"[XLSX ERROR] {e}")
    return products

def get_all_products():
    p = load_products()
    return (p["still_lenses"]+p["cine_lenses"]+
            p["cameras"]+p["accessories"])

def save_product_to_xlsx(sheet_name, product_name, updated_fields):
    try:
        wb = openpyxl.load_workbook(XLSX_PATH)
        if sheet_name not in wb.sheetnames: return False,"Sheet not found"
        ws   = wb[sheet_name]
        rows = list(ws.iter_rows())
        hdrs = [c.value for c in rows[0]]
        for row in rows[1:]:
            if row[0].value == product_name:
                for ci, h in enumerate(hdrs):
                    if h and h in updated_fields:
                        ws.cell(row=row[0].row, column=ci+1,
                                value=updated_fields[h])
                break
        wb.save(XLSX_PATH)
        return True,"Saved"
    except Exception as e:
        return False, str(e)

def delete_product_from_xlsx(sheet_name, product_name):
    try:
        wb = openpyxl.load_workbook(XLSX_PATH)
        if sheet_name not in wb.sheetnames: return False,"Sheet not found"
        ws   = wb[sheet_name]
        rows = list(ws.iter_rows())
        for row in rows[1:]:
            if row[0].value == product_name:
                ws.delete_rows(row[0].row)
                break
        wb.save(XLSX_PATH)
        return True,"Deleted"
    except Exception as e:
        return False,str(e)

def add_product_to_xlsx(sheet_name, fields):
    try:
        wb = openpyxl.load_workbook(XLSX_PATH)
        if sheet_name not in wb.sheetnames: return False,"Sheet not found"
        ws   = wb[sheet_name]
        hdrs = [c.value for c in list(ws.iter_rows())[0]]
        ws.append([fields.get(h,"") for h in hdrs])
        wb.save(XLSX_PATH)
        return True,"Added"
    except Exception as e:
        return False,str(e)

# ═══════════════════════════════════════════════════════
# SEARCH
# ═══════════════════════════════════════════════════════
def search_products(query, limit=8):
    keywords = [k for k in re.split(r"[\s,/]+",query.lower()) if len(k)>2]
    scored   = []
    for p in get_all_products():
        blob  = " ".join(str(v) for v in p.values()).lower()
        score = sum(3 if k in (p.get("Product Name","") or "").lower()
                    else 2 if k in (p.get("Key Features","") or "").lower()
                    else 1 if k in blob else 0
                    for k in keywords)
        if score: scored.append((score,p))
    scored.sort(key=lambda x:-x[0])
    return [p for _,p in scored[:limit]]

# ═══════════════════════════════════════════════════════
# SYSTEM PROMPT
# ═══════════════════════════════════════════════════════
def build_system_prompt():
    cfg   = load_config()
    all_p = get_all_products()
    cat_lines = [
        f"- [{p.get('_display_category','')}] {p.get('Product Name','')} | "
        f"Line:{p.get('Product Line',p.get('Category',''))} | "
        f"{p.get('Focal Length','')} {p.get('Max Aperture',p.get('T-Stop',''))} | "
        f"Mounts:{p.get('Available Mounts',p.get('Compatibility',''))} | "
        f"Price:{p.get('_price_inr','')} | "
        f"{p.get('Key Features','')[:70]}"
        for p in all_p
    ]
    length_map = {"short":"Be very concise.","medium":"Give 2-4 sentences.","detailed":"Be thorough and detailed."}
    style_map  = {"professional":"Professional tone.","friendly":"Warm friendly tone.","technical":"Highly technical language."}
    mandatory  = cfg.get("mandatory_message","").strip()
    loyalty    = cfg.get("loyalty_program","").strip()
    site_url   = cfg.get("site_url","https://sigmaindia.in/")
    brand      = cfg.get("brand_name","Sigma AI Assistant")
    max_p      = cfg.get("max_products_shown", 6)
    show_amz   = cfg.get("show_amazon_links", True)
    show_price = cfg.get("show_price_table", True)
    show_deal  = cfg.get("show_dealer_section", True)
    show_comp  = cfg.get("show_comparison", True)

    return f"""You are {brand} — expert AI product guide for Sigma ({site_url}).
Always respond in {cfg.get('language','English')}. {length_map.get(cfg.get('response_length','medium'),'')} {style_map.get(cfg.get('response_style','professional'),'')}
Brand voice: "Pursuit of Perfection."

RULES:
- ALL prices in ₹ INR. Never mention USD or sigma-global.com.
- Product links → {site_url}
- Amazon links → amazon.in only
- Max {max_p} products per response
- {'Show product comparisons when helpful.' if show_comp else 'Do NOT compare products.'}
{('MANDATORY — append to every response: "'+mandatory+'"') if mandatory else ''}
{('LOYALTY PROGRAM: '+loyalty) if loyalty else ''}

CATALOGUE ({len(all_p)} products):
{chr(10).join(cat_lines)}

FORMAT — when recommending products output:
```json_products
[{{"name":"...","line":"...","category":"...","focal_length":"...","aperture":"...",
   "mounts":"...","key_features":"...","url":"{site_url}",
   "amazon_in":"https://www.amazon.in/s?k=Sigma+name",
   "price_inr":"₹X","price_range_inr":"₹X–₹Y","reason":"..."}}]
```
Then write explanation.
{'Include ```json_prices``` with Sigma India, Amazon India, Flipkart when asked about price.' if show_price else ''}
{'Include ```json_dealers``` with sigmaindia.in/dealer-network when asked about dealers.' if show_deal else ''}
{'Do NOT include Amazon links.' if not show_amz else ''}
NEVER invent products."""

# ═══════════════════════════════════════════════════════
# CLAUDE
# ═══════════════════════════════════════════════════════
def call_claude(messages, system):
    import urllib.request, urllib.error
    if not ANTHROPIC_API_KEY:
        return _fallback(messages[-1]["content"] if messages else "")
    payload = json.dumps({"model":CLAUDE_MODEL,"max_tokens":2048,
                          "system":system,"messages":messages}).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages", data=payload,
        headers={"Content-Type":"application/json",
                 "x-api-key":ANTHROPIC_API_KEY,
                 "anthropic-version":"2023-06-01"},
        method="POST")
    try:
        with urllib.request.urlopen(req,timeout=30) as r:
            return json.loads(r.read())["content"][0]["text"]
    except Exception as e:
        print(f"[CLAUDE] {e}")
        return _fallback(messages[-1]["content"] if messages else "")

def _fallback(query):
    results = search_products(query, 5)
    if not results:
        return "I couldn't find products matching that. Try asking about a focal length, aperture, or product line."
    prods = []
    for p in results:
        name = p.get("Product Name","")
        prods.append({"name":name,
            "line":p.get("Product Line",p.get("Category","")),
            "category":p.get("_display_category",""),
            "focal_length":p.get("Focal Length",""),
            "aperture":p.get("Max Aperture",p.get("T-Stop","")),
            "mounts":p.get("Available Mounts",p.get("Compatibility","")),
            "key_features":p.get("Key Features","")[:120],
            "url":"https://sigmaindia.in/",
            "amazon_in":f"https://www.amazon.in/s?k=Sigma+{name.replace(' ','+')}",
            "price_inr":p.get("_price_inr","Contact dealer"),
            "price_range_inr":p.get("_price_range_inr",""),
            "reason":"Matches your search criteria"})
    return ("```json_products\n"+json.dumps(prods,indent=2)+"\n```\n\n"
            "Here are Sigma products matching your query. Visit sigmaindia.in for pricing.")

def parse_response(raw):
    result = {"text":raw,"products":[],"prices":[],"dealers":[]}
    def ex(tag):
        m = re.search(rf"```{tag}\s*([\s\S]*?)```",raw)
        if m:
            try: return json.loads(m.group(1).strip())
            except: return []
        return []
    result["products"] = ex("json_products")
    result["prices"]   = ex("json_prices")
    result["dealers"]  = ex("json_dealers")
    result["text"]     = re.sub(r"```json_\w+\s*[\s\S]*?```","",raw).strip()
    return result

# ═══════════════════════════════════════════════════════
# CHATBOT ROUTES
# ═══════════════════════════════════════════════════════
@app.route("/")
def index():
    if "sid" not in session: session["sid"] = str(uuid.uuid4())
    session.setdefault("history",[])
    return render_template("index.html", config=load_config())

@app.route("/chat", methods=["POST"])
def chat():
    data     = request.get_json()
    user_msg = (data.get("message") or "").strip()
    if not user_msg: return jsonify({"error":"Empty message"}),400
    history  = session.get("history",[])
    history.append({"role":"user","content":user_msg})
    if len(history)>20: history=history[-20:]
    raw      = call_claude(history, build_system_prompt())
    history.append({"role":"assistant","content":raw})
    session["history"] = history
    save_conversation(session.get("sid","anon"), history)
    parsed   = parse_response(raw)
    # inject product images
    img_map  = {p["Product Name"]:p.get("_image","") for p in get_all_products()}
    for prod in parsed["products"]:
        prod["_image"] = img_map.get(prod.get("name",""),"")
    return jsonify(parsed)

@app.route("/reset", methods=["POST"])
def reset():
    session["history"] = []
    session["sid"]     = str(uuid.uuid4())
    return jsonify({"ok":True})

@app.route("/config-public")
def config_public():
    cfg = load_config()
    # only return UI-safe fields
    return jsonify({k:cfg[k] for k in
        ["brand_name","welcome_message","offer_banner","mandatory_message",
         "language","show_comparison","show_price_table","show_dealer_section",
         "show_amazon_links","max_products_shown"]})

# ═══════════════════════════════════════════════════════
# ADMIN ROUTES
# ═══════════════════════════════════════════════════════
@app.route("/admin")
def admin():
    return render_template("admin.html")

@app.route("/admin/api/products")
def api_products():
    return jsonify(get_all_products())

@app.route("/admin/api/products/update", methods=["POST"])
def api_update_product():
    d = request.get_json()
    ok,msg = save_product_to_xlsx(d.get("sheet"),d.get("product_name"),d.get("fields",{}))
    return jsonify({"ok":ok,"message":msg})

@app.route("/admin/api/products/delete", methods=["POST"])
def api_delete_product():
    d = request.get_json()
    ok,msg = delete_product_from_xlsx(d.get("sheet"),d.get("product_name"))
    return jsonify({"ok":ok,"message":msg})

@app.route("/admin/api/products/add", methods=["POST"])
def api_add_product():
    d = request.get_json()
    ok,msg = add_product_to_xlsx(d.get("sheet"),d.get("fields",{}))
    return jsonify({"ok":ok,"message":msg})

@app.route("/admin/api/products/image", methods=["POST"])
def api_upload_image():
    pid = request.form.get("product_id","")
    if "image" not in request.files: return jsonify({"ok":False,"message":"No file"})
    f   = request.files["image"]
    ext = (f.filename.rsplit(".",1)[-1] if "." in f.filename else "").lower()
    if ext not in ALLOWED_EXT: return jsonify({"ok":False,"message":"Invalid type"})
    for e in ALLOWED_EXT:
        old=os.path.join(IMAGES_DIR,f"{pid}.{e}")
        if os.path.exists(old): os.remove(old)
    filename = f"{pid}.{ext}"
    f.save(os.path.join(IMAGES_DIR,filename))
    return jsonify({"ok":True,"url":f"/static/images/{filename}"})

@app.route("/admin/api/products/image/delete", methods=["POST"])
def api_delete_image():
    pid = request.get_json().get("product_id","")
    for e in ALLOWED_EXT:
        p=os.path.join(IMAGES_DIR,f"{pid}.{e}")
        if os.path.exists(p): os.remove(p)
    return jsonify({"ok":True})

@app.route("/admin/api/config", methods=["GET"])
def api_get_config():
    return jsonify(load_config())

@app.route("/admin/api/config", methods=["POST"])
def api_save_config():
    data = request.get_json()
    cfg  = load_config()
    for k in DEFAULT_CONFIG:
        if k in data: cfg[k]=data[k]
    save_config(cfg)
    return jsonify({"ok":True,"message":"Configuration saved successfully"})

@app.route("/admin/api/conversations")
def api_conversations():
    convs = load_conversations()
    summaries=[]
    for c in convs:
        msgs  = c.get("messages",[])
        first = next((m["content"][:100] for m in msgs if m["role"]=="user"),"")
        summaries.append({"session_id":c["session_id"],
            "started_at":c.get("started_at",""),
            "updated_at":c.get("updated_at",""),
            "message_count":c.get("message_count",0),
            "preview":first})
    return jsonify(summaries)

@app.route("/admin/api/conversations/<sid>")
def api_conversation(sid):
    for c in load_conversations():
        if c["session_id"]==sid: return jsonify(c)
    return jsonify({"error":"Not found"}),404

@app.route("/admin/api/conversations/delete", methods=["POST"])
def api_del_conversation():
    sid   = request.get_json().get("session_id","")
    convs = [c for c in load_conversations() if c["session_id"]!=sid]
    with open(CONV_PATH,"w") as f: json.dump(convs,f,indent=2)
    return jsonify({"ok":True})

@app.route("/admin/api/conversations/clear", methods=["POST"])
def api_clear_conversations():
    with open(CONV_PATH,"w") as f: json.dump([],f)
    return jsonify({"ok":True})

@app.route("/static/images/<filename>")
def serve_img(filename):
    return send_from_directory(IMAGES_DIR, filename)

if __name__ == "__main__":
    print("="*56)
    print("  Sigma AI Assistant  →  http://localhost:5000")
    print("  Admin Panel         →  http://localhost:5000/admin")
    print("="*56)
    if not ANTHROPIC_API_KEY:
        print("  ⚠  No ANTHROPIC_API_KEY — fallback mode")
    print("="*56)
    app.run(debug=True, port=5000)
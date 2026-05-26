"""
Sigma India AI Agent - AI Product Discovery Chatbot
Flask app powered by Claude AI + Sigma India product catalogue
Prices in INR | Dealer network India | Amazon India links
"""

import os, json, re
from flask import Flask, render_template, request, jsonify, session

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "sigmaindia-agent-secret-2025")

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "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")
CLAUDE_MODEL = "claude-sonnet-4-20250514"

# ══════════════════════════════════════════════════════════════════════════════
# PRODUCT DATABASE — Scraped from sigmaindia.in + global catalogue
# All prices in INR (approximate market prices as of 2025)
# ══════════════════════════════════════════════════════════════════════════════
PRODUCTS = [
    # ── STILL LENSES — ART LINE ──────────────────────────────────────────────
    {
        "name": "14mm F1.4 DG DN | Art",
        "line": "Art", "category": "Still Lenses", "type": "Prime",
        "focal_length": "14mm", "aperture": "F1.4", "format": "Full-Frame",
        "mounts": "L-Mount, Sony E",
        "key_features": "World's widest F1.4 prime; astrophotography; HLA dual AF; dust/splash resistant",
        "price_inr": "₹1,35,000", "price_range_inr": "₹1,30,000 – ₹1,40,000",
        "url": "https://sigmaindia.in/product-category/lenses/",
        "amazon_in": "https://www.amazon.in/s?k=Sigma+14mm+F1.4+DG+DN+Art",
        "weight": "1,170g", "filter": "—", "min_focus": "27cm"
    },
    {
        "name": "15mm F1.4 DG DN Diagonal Fisheye | Art",
        "line": "Art", "category": "Still Lenses", "type": "Prime / Fisheye",
        "focal_length": "15mm", "aperture": "F1.4", "format": "Full-Frame",
        "mounts": "L-Mount, Sony E",
        "key_features": "180° diagonal fisheye with F1.4 aperture; unique creative perspectives; HLA AF",
        "price_inr": "₹95,000", "price_range_inr": "₹90,000 – ₹1,00,000",
        "url": "https://sigmaindia.in/product-category/lenses/",
        "amazon_in": "https://www.amazon.in/s?k=Sigma+15mm+F1.4+Fisheye+Art",
        "weight": "685g", "filter": "φ86mm", "min_focus": "17.5cm"
    },
    {
        "name": "20mm F1.4 DG DN | Art",
        "line": "Art", "category": "Still Lenses", "type": "Prime",
        "focal_length": "20mm", "aperture": "F1.4", "format": "Full-Frame",
        "mounts": "L-Mount, Sony E",
        "key_features": "Ultra-wide prime; HLA AF; landscape & astrophotography; weather-sealed",
        "price_inr": "₹82,000", "price_range_inr": "₹78,000 – ₹86,000",
        "url": "https://sigmaindia.in/product-category/lenses/",
        "amazon_in": "https://www.amazon.in/s?k=Sigma+20mm+F1.4+DG+DN+Art",
        "weight": "635g", "filter": "φ82mm", "min_focus": "20cm"
    },
    {
        "name": "24mm F1.4 DG DN | Art",
        "line": "Art", "category": "Still Lenses", "type": "Prime",
        "focal_length": "24mm", "aperture": "F1.4", "format": "Full-Frame",
        "mounts": "L-Mount, Sony E",
        "key_features": "Compact wide-angle prime; weather-resistant; HLA AF; great for landscape & street",
        "price_inr": "₹72,000", "price_range_inr": "₹68,000 – ₹76,000",
        "url": "https://sigmaindia.in/product-category/lenses/",
        "amazon_in": "https://www.amazon.in/s?k=Sigma+24mm+F1.4+DG+DN+Art",
        "weight": "440g", "filter": "φ72mm", "min_focus": "24cm"
    },
    {
        "name": "35mm F1.2 DG DN II | Art",
        "line": "Art", "category": "Still Lenses", "type": "Prime",
        "focal_length": "35mm", "aperture": "F1.2", "format": "Full-Frame",
        "mounts": "L-Mount, Sony E",
        "key_features": "Ultra-fast F1.2; dual HLA AF; stunning low-light performance; AAC coating",
        "price_inr": "₹1,55,000", "price_range_inr": "₹1,50,000 – ₹1,60,000",
        "url": "https://sigmaindia.in/product-category/lenses/",
        "amazon_in": "https://www.amazon.in/s?k=Sigma+35mm+F1.2+DG+DN+Art",
        "weight": "930g", "filter": "φ82mm", "min_focus": "30cm"
    },
    {
        "name": "35mm F1.4 DG DN II | Art",
        "line": "Art", "category": "Still Lenses", "type": "Prime",
        "focal_length": "35mm", "aperture": "F1.4", "format": "Full-Frame",
        "mounts": "L-Mount, Sony E",
        "key_features": "Latest-gen 35mm Art; lightest in class; dual HLA AF; AAC coating; weather-sealed",
        "price_inr": "₹68,000", "price_range_inr": "₹64,000 – ₹72,000",
        "url": "https://sigmaindia.in/product-category/lenses/",
        "amazon_in": "https://www.amazon.in/s?k=Sigma+35mm+F1.4+DG+DN+Art",
        "weight": "530g", "filter": "φ67mm", "min_focus": "28cm"
    },
    {
        "name": "50mm F1.2 DG DN | Art",
        "line": "Art", "category": "Still Lenses", "type": "Prime",
        "focal_length": "50mm", "aperture": "F1.2", "format": "Full-Frame",
        "mounts": "L-Mount, Sony E",
        "key_features": "Fastest-aperture standard prime; creamy bokeh; HLA AF; exceptional rendering",
        "price_inr": "₹1,15,000", "price_range_inr": "₹1,10,000 – ₹1,20,000",
        "url": "https://sigmaindia.in/product-category/lenses/",
        "amazon_in": "https://www.amazon.in/s?k=Sigma+50mm+F1.2+DG+DN+Art",
        "weight": "745g", "filter": "φ82mm", "min_focus": "45cm"
    },
    {
        "name": "50mm F1.4 DG DN | Art",
        "line": "Art", "category": "Still Lenses", "type": "Prime",
        "focal_length": "50mm", "aperture": "F1.4", "format": "Full-Frame",
        "mounts": "L-Mount, Sony E",
        "key_features": "High-resolution standard prime; floating focus; beautiful background rendering",
        "price_inr": "₹82,000", "price_range_inr": "₹78,000 – ₹86,000",
        "url": "https://sigmaindia.in/product-category/lenses/",
        "amazon_in": "https://www.amazon.in/s?k=Sigma+50mm+F1.4+DG+DN+Art",
        "weight": "660g", "filter": "φ72mm", "min_focus": "40cm"
    },
    {
        "name": "70mm F2.8 DG MACRO | Art",
        "line": "Art", "category": "Still Lenses", "type": "Prime / Macro",
        "focal_length": "70mm", "aperture": "F2.8", "format": "Full-Frame",
        "mounts": "Canon EF, Nikon F, Sigma SA",
        "key_features": "1:1 true macro; product & nature photography; exceptional sharpness",
        "price_inr": "₹52,000", "price_range_inr": "₹48,000 – ₹56,000",
        "url": "https://sigmaindia.in/product-category/lenses/",
        "amazon_in": "https://www.amazon.in/s?k=Sigma+70mm+F2.8+Macro+Art",
        "weight": "515g", "filter": "φ49mm", "min_focus": "25.7cm"
    },
    {
        "name": "85mm F1.4 DG DN | Art",
        "line": "Art", "category": "Still Lenses", "type": "Prime",
        "focal_length": "85mm", "aperture": "F1.4", "format": "Full-Frame",
        "mounts": "L-Mount, Sony E",
        "key_features": "Portrait prime; stunning bokeh; HLA AF; dust/splash resistant; award-winning optics",
        "price_inr": "₹92,000", "price_range_inr": "₹88,000 – ₹96,000",
        "url": "https://sigmaindia.in/product-category/lenses/",
        "amazon_in": "https://www.amazon.in/s?k=Sigma+85mm+F1.4+DG+DN+Art",
        "weight": "700g", "filter": "φ77mm", "min_focus": "85cm"
    },
    {
        "name": "105mm F2.8 DG DN MACRO | Art",
        "line": "Art", "category": "Still Lenses", "type": "Prime / Macro",
        "focal_length": "105mm", "aperture": "F2.8", "format": "Full-Frame",
        "mounts": "L-Mount, Sony E",
        "key_features": "1:1 macro; HLA AF; dual focus limiter; beautiful bokeh; weather-sealed",
        "price_inr": "₹78,000", "price_range_inr": "₹74,000 – ₹82,000",
        "url": "https://sigmaindia.in/product-category/lenses/",
        "amazon_in": "https://www.amazon.in/s?k=Sigma+105mm+F2.8+Macro+Art",
        "weight": "715g", "filter": "φ67mm", "min_focus": "29.5cm"
    },
    {
        "name": "135mm F1.4 DG | Art",
        "line": "Art", "category": "Still Lenses", "type": "Prime",
        "focal_length": "135mm", "aperture": "F1.4", "format": "Full-Frame",
        "mounts": "L-Mount, Sony E, Canon EF, Nikon F",
        "key_features": "BOKEH-master lens; F1.4 at 135mm; exceptional subject separation; dual HLA",
        "price_inr": "₹1,65,000", "price_range_inr": "₹1,60,000 – ₹1,72,000",
        "url": "https://sigmaindia.in/product-category/lenses/",
        "amazon_in": "https://www.amazon.in/s?k=Sigma+135mm+F1.4+DG+Art",
        "weight": "1,130g", "filter": "φ82mm", "min_focus": "87.5cm"
    },
    # ── STILL LENSES — ART ZOOMS ─────────────────────────────────────────────
    {
        "name": "14-24mm F2.8 DG DN | Art",
        "line": "Art", "category": "Still Lenses", "type": "Zoom",
        "focal_length": "14-24mm", "aperture": "F2.8", "format": "Full-Frame",
        "mounts": "L-Mount, Sony E",
        "key_features": "Ultra-wide constant F2.8 zoom; mirrorless; HLA AF; nano-porous coating",
        "price_inr": "₹1,05,000", "price_range_inr": "₹1,00,000 – ₹1,10,000",
        "url": "https://sigmaindia.in/product-category/lenses/",
        "amazon_in": "https://www.amazon.in/s?k=Sigma+14-24mm+F2.8+DG+DN+Art",
        "weight": "795g", "filter": "—", "min_focus": "28cm"
    },
    {
        "name": "24-70mm F2.8 DG DN II | Art",
        "line": "Art", "category": "Still Lenses", "type": "Zoom",
        "focal_length": "24-70mm", "aperture": "F2.8", "format": "Full-Frame",
        "mounts": "L-Mount, Sony E",
        "key_features": "Updated standard zoom; lighter & sharper; dual HLA AF; weather-sealed; 11 blades",
        "price_inr": "₹1,12,000", "price_range_inr": "₹1,08,000 – ₹1,18,000",
        "url": "https://sigmaindia.in/product-category/lenses/",
        "amazon_in": "https://www.amazon.in/s?k=Sigma+24-70mm+F2.8+DG+DN+Art",
        "weight": "830g", "filter": "φ82mm", "min_focus": "21cm"
    },
    {
        "name": "24-105mm F4 DG OS HSM | Art",
        "line": "Art", "category": "Still Lenses", "type": "Zoom",
        "focal_length": "24-105mm", "aperture": "F4", "format": "Full-Frame",
        "mounts": "Canon EF, Nikon F, Sigma SA",
        "key_features": "Versatile travel zoom with optical stabilisation; weather-sealed; professional quality",
        "price_inr": "₹68,000", "price_range_inr": "₹64,000 – ₹72,000",
        "url": "https://sigmaindia.in/product-category/lenses/",
        "amazon_in": "https://www.amazon.in/s?k=Sigma+24-105mm+F4+DG+OS+Art",
        "weight": "885g", "filter": "φ82mm", "min_focus": "45cm"
    },
    {
        "name": "28-45mm F1.8 DG DN | Art",
        "line": "Art", "category": "Still Lenses", "type": "Zoom",
        "focal_length": "28-45mm", "aperture": "F1.8", "format": "Full-Frame",
        "mounts": "L-Mount, Sony E",
        "key_features": "World's first F1.8 full-frame zoom; covers wide to normal; premium optics",
        "price_inr": "₹1,35,000", "price_range_inr": "₹1,30,000 – ₹1,40,000",
        "url": "https://sigmaindia.in/product-category/lenses/",
        "amazon_in": "https://www.amazon.in/s?k=Sigma+28-45mm+F1.8+DG+DN+Art",
        "weight": "1,030g", "filter": "φ82mm", "min_focus": "35cm"
    },
    {
        "name": "28-105mm F2.8 DG DN | Art",
        "line": "Art", "category": "Still Lenses", "type": "Zoom",
        "focal_length": "28-105mm", "aperture": "F2.8", "format": "Full-Frame",
        "mounts": "L-Mount, Sony E",
        "key_features": "Unprecedented F2.8 range; wide to short telephoto; dual HLA; weather-sealed",
        "price_inr": "₹1,52,000", "price_range_inr": "₹1,48,000 – ₹1,58,000",
        "url": "https://sigmaindia.in/product-category/lenses/",
        "amazon_in": "https://www.amazon.in/s?k=Sigma+28-105mm+F2.8+DG+DN+Art",
        "weight": "1,265g", "filter": "φ82mm", "min_focus": "30cm"
    },
    {
        "name": "17-40mm F1.8 DC | Art",
        "line": "Art", "category": "Still Lenses", "type": "Zoom",
        "focal_length": "17-40mm", "aperture": "F1.8", "format": "APS-C",
        "mounts": "Canon EF, Nikon F, Sigma SA",
        "key_features": "World's first APS-C F1.8 standard zoom; low-light versatility; 9-blade aperture",
        "price_inr": "₹82,000", "price_range_inr": "₹78,000 – ₹86,000",
        "url": "https://sigmaindia.in/product-category/lenses/",
        "amazon_in": "https://www.amazon.in/s?k=Sigma+17-40mm+F1.8+DC+Art",
        "weight": "970g", "filter": "φ82mm", "min_focus": "30cm"
    },
    # ── STILL LENSES — CONTEMPORARY I-SERIES ─────────────────────────────────
    {
        "name": "17mm F4 DG DN | Contemporary (I-Series)",
        "line": "Contemporary", "category": "Still Lenses", "type": "Prime",
        "focal_length": "17mm", "aperture": "F4", "format": "Full-Frame",
        "mounts": "L-Mount, Sony E",
        "key_features": "I-Series ultra-compact; all-metal body; landscape & travel; 225g lightweight",
        "price_inr": "₹42,000", "price_range_inr": "₹39,000 – ₹45,000",
        "url": "https://sigmaindia.in/product-category/lenses/",
        "amazon_in": "https://www.amazon.in/s?k=Sigma+17mm+F4+DG+DN+Contemporary",
        "weight": "225g", "filter": "φ55mm", "min_focus": "12cm"
    },
    {
        "name": "20mm F2 DG DN | Contemporary (I-Series)",
        "line": "Contemporary", "category": "Still Lenses", "type": "Prime",
        "focal_length": "20mm", "aperture": "F2", "format": "Full-Frame",
        "mounts": "L-Mount, Sony E",
        "key_features": "I-Series compact wide prime; metal barrel; architecture & landscape",
        "price_inr": "₹52,000", "price_range_inr": "₹48,000 – ₹56,000",
        "url": "https://sigmaindia.in/product-category/lenses/",
        "amazon_in": "https://www.amazon.in/s?k=Sigma+20mm+F2+DG+DN+Contemporary",
        "weight": "370g", "filter": "φ67mm", "min_focus": "22cm"
    },
    {
        "name": "24mm F3.5 DG DN | Contemporary (I-Series)",
        "line": "Contemporary", "category": "Still Lenses", "type": "Prime",
        "focal_length": "24mm", "aperture": "F3.5", "format": "Full-Frame",
        "mounts": "L-Mount, Sony E",
        "key_features": "I-Series; close-focus macro-like capability; ultra-compact; 225g; all-metal",
        "price_inr": "₹38,000", "price_range_inr": "₹35,000 – ₹41,000",
        "url": "https://sigmaindia.in/product-category/lenses/",
        "amazon_in": "https://www.amazon.in/s?k=Sigma+24mm+F3.5+DG+DN+Contemporary",
        "weight": "225g", "filter": "φ55mm", "min_focus": "13.5cm"
    },
    {
        "name": "35mm F2 DG DN | Contemporary (I-Series)",
        "line": "Contemporary", "category": "Still Lenses", "type": "Prime",
        "focal_length": "35mm", "aperture": "F2", "format": "Full-Frame",
        "mounts": "L-Mount, Sony E",
        "key_features": "I-Series compact walkaround prime; excellent sharpness; metal barrel; street & travel",
        "price_inr": "₹46,000", "price_range_inr": "₹43,000 – ₹49,000",
        "url": "https://sigmaindia.in/product-category/lenses/",
        "amazon_in": "https://www.amazon.in/s?k=Sigma+35mm+F2+DG+DN+Contemporary",
        "weight": "325g", "filter": "φ58mm", "min_focus": "27cm"
    },
    {
        "name": "45mm F2.8 DG DN | Contemporary (I-Series)",
        "line": "Contemporary", "category": "Still Lenses", "type": "Prime",
        "focal_length": "45mm", "aperture": "F2.8", "format": "Full-Frame",
        "mounts": "L-Mount, Sony E",
        "key_features": "I-Series ultra-compact normal prime; 215g lightest in series; pancake-style; all-metal",
        "price_inr": "₹32,000", "price_range_inr": "₹29,000 – ₹35,000",
        "url": "https://sigmaindia.in/product-category/lenses/",
        "amazon_in": "https://www.amazon.in/s?k=Sigma+45mm+F2.8+DG+DN+Contemporary",
        "weight": "215g", "filter": "φ55mm", "min_focus": "24cm"
    },
    {
        "name": "50mm F2 DG DN | Contemporary (I-Series)",
        "line": "Contemporary", "category": "Still Lenses", "type": "Prime",
        "focal_length": "50mm", "aperture": "F2", "format": "Full-Frame",
        "mounts": "L-Mount, Sony E",
        "key_features": "I-Series standard prime; bokeh-rich; elegant build; 350g; HLA AF",
        "price_inr": "₹48,000", "price_range_inr": "₹44,000 – ₹52,000",
        "url": "https://sigmaindia.in/product-category/lenses/",
        "amazon_in": "https://www.amazon.in/s?k=Sigma+50mm+F2+DG+DN+Contemporary",
        "weight": "350g", "filter": "φ58mm", "min_focus": "45cm"
    },
    {
        "name": "65mm F2 DG DN | Contemporary (I-Series)",
        "line": "Contemporary", "category": "Still Lenses", "type": "Prime",
        "focal_length": "65mm", "aperture": "F2", "format": "Full-Frame",
        "mounts": "L-Mount, Sony E",
        "key_features": "I-Series short telephoto portrait prime; beautiful rendering; metal barrel",
        "price_inr": "₹52,000", "price_range_inr": "₹48,000 – ₹56,000",
        "url": "https://sigmaindia.in/product-category/lenses/",
        "amazon_in": "https://www.amazon.in/s?k=Sigma+65mm+F2+DG+DN+Contemporary",
        "weight": "405g", "filter": "φ62mm", "min_focus": "55cm"
    },
    {
        "name": "90mm F2.8 DG DN | Contemporary (I-Series)",
        "line": "Contemporary", "category": "Still Lenses", "type": "Prime",
        "focal_length": "90mm", "aperture": "F2.8", "format": "Full-Frame",
        "mounts": "L-Mount, Sony E",
        "key_features": "I-Series compact telephoto prime; close-focus; 295g; excellent sharpness",
        "price_inr": "₹42,000", "price_range_inr": "₹39,000 – ₹45,000",
        "url": "https://sigmaindia.in/product-category/lenses/",
        "amazon_in": "https://www.amazon.in/s?k=Sigma+90mm+F2.8+DG+DN+Contemporary",
        "weight": "295g", "filter": "φ55mm", "min_focus": "50cm"
    },
    # ── CONTEMPORARY APS-C DC DN ─────────────────────────────────────────────
    {
        "name": "10-18mm F2.8 DC DN | Contemporary",
        "line": "Contemporary", "category": "Still Lenses", "type": "Zoom",
        "focal_length": "10-18mm", "aperture": "F2.8", "format": "APS-C",
        "mounts": "L-Mount, Sony E, Canon EF-M, MFT, Fujifilm X, Nikon Z",
        "key_features": "Ultra-wide APS-C F2.8 zoom; 290g super-lightweight; video & landscape; HLA AF",
        "price_inr": "₹42,000", "price_range_inr": "₹39,000 – ₹45,000",
        "url": "https://sigmaindia.in/product/sigma-10-18-f2-8-dc-dn/",
        "amazon_in": "https://www.amazon.in/s?k=Sigma+10-18mm+F2.8+DC+DN+Contemporary",
        "weight": "290g", "filter": "φ67mm", "min_focus": "11.6cm"
    },
    {
        "name": "16mm F1.4 DC DN | Contemporary",
        "line": "Contemporary", "category": "Still Lenses", "type": "Prime",
        "focal_length": "16mm", "aperture": "F1.4", "format": "APS-C",
        "mounts": "L-Mount, Sony E, Canon EF-M, MFT, Fujifilm X, Nikon Z",
        "key_features": "Popular APS-C wide prime; vlogging & street photography; 405g; HSM AF",
        "price_inr": "₹36,000", "price_range_inr": "₹33,000 – ₹39,000",
        "url": "https://sigmaindia.in/product-category/lenses/",
        "amazon_in": "https://www.amazon.in/s?k=Sigma+16mm+F1.4+DC+DN+Contemporary",
        "weight": "405g", "filter": "φ67mm", "min_focus": "25cm"
    },
    {
        "name": "23mm F1.4 DC DN | Contemporary",
        "line": "Contemporary", "category": "Still Lenses", "type": "Prime",
        "focal_length": "23mm", "aperture": "F1.4", "format": "APS-C",
        "mounts": "L-Mount, Sony E, Canon EF-M, MFT, Fujifilm X, Nikon Z",
        "key_features": "Compact APS-C normal-wide prime; everyday shooting; 335g lightweight",
        "price_inr": "₹32,000", "price_range_inr": "₹29,000 – ₹35,000",
        "url": "https://sigmaindia.in/product-category/lenses/",
        "amazon_in": "https://www.amazon.in/s?k=Sigma+23mm+F1.4+DC+DN+Contemporary",
        "weight": "335g", "filter": "φ55mm", "min_focus": "25cm"
    },
    {
        "name": "30mm F1.4 DC DN | Contemporary",
        "line": "Contemporary", "category": "Still Lenses", "type": "Prime",
        "focal_length": "30mm", "aperture": "F1.4", "format": "APS-C",
        "mounts": "L-Mount, Sony E, Canon EF-M, MFT, Fujifilm X, Nikon Z",
        "key_features": "Best-selling APS-C walkaround prime; compact; affordable; 265g; HSM AF",
        "price_inr": "₹22,000", "price_range_inr": "₹20,000 – ₹24,000",
        "url": "https://sigmaindia.in/product-category/lenses/",
        "amazon_in": "https://www.amazon.in/s?k=Sigma+30mm+F1.4+DC+DN+Contemporary",
        "weight": "265g", "filter": "φ52mm", "min_focus": "30cm"
    },
    {
        "name": "56mm F1.4 DC DN | Contemporary",
        "line": "Contemporary", "category": "Still Lenses", "type": "Prime",
        "focal_length": "56mm", "aperture": "F1.4", "format": "APS-C",
        "mounts": "L-Mount, Sony E, Canon EF-M, MFT, Fujifilm X, Nikon Z",
        "key_features": "Portrait focal length for APS-C; F1.4 subject isolation; 280g; 9 blades",
        "price_inr": "₹26,000", "price_range_inr": "₹24,000 – ₹28,000",
        "url": "https://sigmaindia.in/product-category/lenses/",
        "amazon_in": "https://www.amazon.in/s?k=Sigma+56mm+F1.4+DC+DN+Contemporary",
        "weight": "280g", "filter": "φ55mm", "min_focus": "50cm"
    },
    {
        "name": "18-50mm F2.8 DC DN | Contemporary",
        "line": "Contemporary", "category": "Still Lenses", "type": "Zoom",
        "focal_length": "18-50mm", "aperture": "F2.8", "format": "APS-C",
        "mounts": "L-Mount, Sony E, Canon EF-M, MFT, Fujifilm X, Nikon Z",
        "key_features": "Compact F2.8 APS-C standard zoom; 290g; travel & street; HLA AF",
        "price_inr": "₹38,000", "price_range_inr": "₹35,000 – ₹41,000",
        "url": "https://sigmaindia.in/product-category/lenses/",
        "amazon_in": "https://www.amazon.in/s?k=Sigma+18-50mm+F2.8+DC+DN+Contemporary",
        "weight": "290g", "filter": "φ67mm", "min_focus": "12.1cm"
    },
    {
        "name": "16-28mm F2.8 DG DN | Contemporary",
        "line": "Contemporary", "category": "Still Lenses", "type": "Zoom",
        "focal_length": "16-28mm", "aperture": "F2.8", "format": "Full-Frame",
        "mounts": "L-Mount, Sony E",
        "key_features": "Compact ultra-wide full-frame zoom; 450g; great value; HLA AF",
        "price_inr": "₹62,000", "price_range_inr": "₹58,000 – ₹66,000",
        "url": "https://sigmaindia.in/product-category/lenses/",
        "amazon_in": "https://www.amazon.in/s?k=Sigma+16-28mm+F2.8+DG+DN+Contemporary",
        "weight": "450g", "filter": "—", "min_focus": "25cm"
    },
    {
        "name": "28-70mm F2.8 DG DN | Contemporary",
        "line": "Contemporary", "category": "Still Lenses", "type": "Zoom",
        "focal_length": "28-70mm", "aperture": "F2.8", "format": "Full-Frame",
        "mounts": "L-Mount, Sony E",
        "key_features": "Compact lightweight F2.8 standard zoom; 470g; ideal for travel; HLA AF",
        "price_inr": "₹56,000", "price_range_inr": "₹52,000 – ₹60,000",
        "url": "https://sigmaindia.in/product-category/lenses/",
        "amazon_in": "https://www.amazon.in/s?k=Sigma+28-70mm+F2.8+DG+DN+Contemporary",
        "weight": "470g", "filter": "φ67mm", "min_focus": "19cm"
    },
    {
        "name": "100-400mm F5-6.3 DG DN OS | Contemporary",
        "line": "Contemporary", "category": "Still Lenses", "type": "Zoom",
        "focal_length": "100-400mm", "aperture": "F5-6.3", "format": "Full-Frame",
        "mounts": "L-Mount, Sony E",
        "key_features": "Telephoto zoom with OS; wildlife & sports; 1,140g; HLA AF; weather-sealed",
        "price_inr": "₹92,000", "price_range_inr": "₹88,000 – ₹96,000",
        "url": "https://sigmaindia.in/product-category/lenses/",
        "amazon_in": "https://www.amazon.in/s?k=Sigma+100-400mm+DG+DN+OS+Contemporary",
        "weight": "1,140g", "filter": "φ82mm", "min_focus": "100cm"
    },
    # ── SPORTS LINE ──────────────────────────────────────────────────────────
    {
        "name": "70-200mm F2.8 DG DN OS | Sports",
        "line": "Sports", "category": "Still Lenses", "type": "Zoom",
        "focal_length": "70-200mm", "aperture": "F2.8", "format": "Full-Frame",
        "mounts": "L-Mount, Sony E",
        "key_features": "Professional constant F2.8 telephoto zoom; OS; sports & wildlife; HLA AF",
        "price_inr": "₹1,65,000", "price_range_inr": "₹1,60,000 – ₹1,72,000",
        "url": "https://sigmaindia.in/product-category/lenses/",
        "amazon_in": "https://www.amazon.in/s?k=Sigma+70-200mm+F2.8+DG+DN+OS+Sports",
        "weight": "1,495g", "filter": "φ82mm", "min_focus": "70cm"
    },
    {
        "name": "60-600mm F4.5-6.3 DG DN OS | Sports",
        "line": "Sports", "category": "Still Lenses", "type": "Zoom",
        "focal_length": "60-600mm", "aperture": "F4.5-6.3", "format": "Full-Frame",
        "mounts": "L-Mount, Sony E",
        "key_features": "Versatile hyper-zoom; OS; covers standard to super-telephoto; wildlife & aviation",
        "price_inr": "₹2,15,000", "price_range_inr": "₹2,10,000 – ₹2,22,000",
        "url": "https://sigmaindia.in/product-category/lenses/",
        "amazon_in": "https://www.amazon.in/s?k=Sigma+60-600mm+DG+DN+OS+Sports",
        "weight": "2,485g", "filter": "φ105mm", "min_focus": "45cm"
    },
    {
        "name": "150-600mm F5-6.3 DG DN OS | Sports",
        "line": "Sports", "category": "Still Lenses", "type": "Zoom",
        "focal_length": "150-600mm", "aperture": "F5-6.3", "format": "Full-Frame",
        "mounts": "L-Mount, Sony E",
        "key_features": "Super-telephoto zoom with OS; birding & wildlife; HLA AF; weather-sealed",
        "price_inr": "₹1,85,000", "price_range_inr": "₹1,80,000 – ₹1,92,000",
        "url": "https://sigmaindia.in/product-category/lenses/",
        "amazon_in": "https://www.amazon.in/s?k=Sigma+150-600mm+DG+DN+OS+Sports",
        "weight": "2,090g", "filter": "φ105mm", "min_focus": "260cm"
    },
    {
        "name": "500mm F5.6 DG DN OS | Sports",
        "line": "Sports", "category": "Still Lenses", "type": "Prime",
        "focal_length": "500mm", "aperture": "F5.6", "format": "Full-Frame",
        "mounts": "L-Mount, Sony E",
        "key_features": "Compact 500mm prime; OS; wildlife & birds in flight; 1,525g handholdable",
        "price_inr": "₹1,95,000", "price_range_inr": "₹1,90,000 – ₹2,02,000",
        "url": "https://sigmaindia.in/product-category/lenses/",
        "amazon_in": "https://www.amazon.in/s?k=Sigma+500mm+F5.6+DG+DN+OS+Sports",
        "weight": "1,525g", "filter": "φ95mm", "min_focus": "200cm"
    },
    # ── CAMERAS ──────────────────────────────────────────────────────────────
    {
        "name": "Sigma BF Camera",
        "line": "Camera", "category": "Cameras", "type": "Mirrorless",
        "focal_length": "—", "aperture": "—", "format": "Full-Frame",
        "mounts": "L-Mount",
        "key_features": "World's most minimalist full-frame; 24.6MP BSI-CMOS; 6K RAW; touchscreen-primary; 427g; Made in Aizu",
        "price_inr": "₹1,85,000", "price_range_inr": "₹1,80,000 – ₹1,92,000",
        "url": "https://sigmaindia.in/camera-bf/",
        "amazon_in": "https://www.amazon.in/s?k=Sigma+BF+Camera",
        "weight": "427g", "filter": "—", "min_focus": "—"
    },
    {
        "name": "Sigma fp L Camera",
        "line": "Camera", "category": "Cameras", "type": "Mirrorless",
        "focal_length": "—", "aperture": "—", "format": "Full-Frame",
        "mounts": "L-Mount",
        "key_features": "61MP world's smallest full-frame; Cinema DNG RAW; ProRes RAW; 557g; L-Mount; USB-C",
        "price_inr": "₹2,12,000", "price_range_inr": "₹2,05,000 – ₹2,20,000",
        "url": "https://sigmaindia.in/product/sigmafpl-2/",
        "amazon_in": "https://www.amazon.in/s?k=Sigma+fp+L+Camera",
        "weight": "557g", "filter": "—", "min_focus": "—"
    },
    {
        "name": "Sigma fp Camera",
        "line": "Camera", "category": "Cameras", "type": "Mirrorless",
        "focal_length": "—", "aperture": "—", "format": "Full-Frame",
        "mounts": "L-Mount",
        "key_features": "World's smallest pocketable full-frame; 24.6MP; Cinema DNG RAW 4K; 422g; modular system",
        "price_inr": "₹1,28,000", "price_range_inr": "₹1,22,000 – ₹1,34,000",
        "url": "https://sigmaindia.in/product/sigmafp-2/",
        "amazon_in": "https://www.amazon.in/s?k=Sigma+fp+Camera",
        "weight": "422g", "filter": "—", "min_focus": "—"
    },
    {
        "name": "Sigma fp + 45mm F2.8 DG DN Kit",
        "line": "Camera", "category": "Cameras", "type": "Mirrorless Kit",
        "focal_length": "45mm", "aperture": "F2.8", "format": "Full-Frame",
        "mounts": "L-Mount",
        "key_features": "Sigma fp body + I-Series 45mm F2.8 lens kit; complete compact full-frame system",
        "price_inr": "₹1,55,000", "price_range_inr": "₹1,50,000 – ₹1,62,000",
        "url": "https://sigmaindia.in/product/sigma-fp-45mm-f2-8-dg-dn/",
        "amazon_in": "https://www.amazon.in/s?k=Sigma+fp+45mm+kit",
        "weight": "637g", "filter": "φ55mm", "min_focus": "—"
    },
    # ── CINE LENSES ──────────────────────────────────────────────────────────
    {
        "name": "AF Cine 28-45mm T2 FF",
        "line": "AF CINE LINE", "category": "Cine Lenses", "type": "Zoom",
        "focal_length": "28-45mm", "aperture": "T2", "format": "Full-Frame",
        "mounts": "L-Mount, Sony E (PL available)",
        "key_features": "World's first autofocus cine zoom; T2 constant aperture; internal zoom; cinema AF",
        "price_inr": "₹4,25,000", "price_range_inr": "₹4,15,000 – ₹4,35,000",
        "url": "https://sigmaindia.in/product-category/cine-lenses/",
        "amazon_in": "https://www.amazon.in/s?k=Sigma+AF+Cine+28-45mm+T2",
        "weight": "1,030g", "filter": "φ90mm", "min_focus": "35cm"
    },
    {
        "name": "AF Cine 28-105mm T3 FF",
        "line": "AF CINE LINE", "category": "Cine Lenses", "type": "Zoom",
        "focal_length": "28-105mm", "aperture": "T3", "format": "Full-Frame",
        "mounts": "L-Mount, Sony E",
        "key_features": "Cinematic autofocus zoom; wide-to-telephoto coverage; T3 constant; cinema AF",
        "price_inr": "₹3,85,000", "price_range_inr": "₹3,75,000 – ₹3,95,000",
        "url": "https://sigmaindia.in/product-category/cine-lenses/",
        "amazon_in": "https://www.amazon.in/s?k=Sigma+AF+Cine+28-105mm+T3",
        "weight": "1,265g", "filter": "φ90mm", "min_focus": "30cm"
    },
    {
        "name": "FF High Speed Prime 35mm T1.5 FF",
        "line": "FF High Speed Prime Line", "category": "Cine Lenses", "type": "Prime",
        "focal_length": "35mm", "aperture": "T1.5", "format": "Full-Frame",
        "mounts": "PL, EF (Canon), E (Sony)",
        "key_features": "High-speed T1.5 cine prime; full-frame coverage; cinematic rendering; PL mount",
        "price_inr": "₹2,15,000", "price_range_inr": "₹2,05,000 – ₹2,25,000",
        "url": "https://sigmaindia.in/product-category/cine-lenses/",
        "amazon_in": None,
        "weight": "1,090g", "filter": "φ114mm", "min_focus": "30cm"
    },
    {
        "name": "FF High Speed Prime 50mm T1.5 FF",
        "line": "FF High Speed Prime Line", "category": "Cine Lenses", "type": "Prime",
        "focal_length": "50mm", "aperture": "T1.5", "format": "Full-Frame",
        "mounts": "PL, EF (Canon), E (Sony)",
        "key_features": "Standard T1.5 cine prime; narrative & documentary; full-frame; cinematic bokeh",
        "price_inr": "₹2,15,000", "price_range_inr": "₹2,05,000 – ₹2,25,000",
        "url": "https://sigmaindia.in/product-category/cine-lenses/",
        "amazon_in": None,
        "weight": "1,090g", "filter": "φ114mm", "min_focus": "40cm"
    },
    {
        "name": "FF High Speed Prime 85mm T1.5 FF",
        "line": "FF High Speed Prime Line", "category": "Cine Lenses", "type": "Prime",
        "focal_length": "85mm", "aperture": "T1.5", "format": "Full-Frame",
        "mounts": "PL, EF (Canon), E (Sony)",
        "key_features": "Portrait cine prime T1.5; shallow depth of field; drama & narrative",
        "price_inr": "₹2,15,000", "price_range_inr": "₹2,05,000 – ₹2,25,000",
        "url": "https://sigmaindia.in/product-category/cine-lenses/",
        "amazon_in": None,
        "weight": "1,090g", "filter": "φ114mm", "min_focus": "85cm"
    },
    {
        "name": "High Speed Zoom 18-35mm T2",
        "line": "High Speed Zoom Line", "category": "Cine Lenses", "type": "Zoom",
        "focal_length": "18-35mm", "aperture": "T2", "format": "Super 35",
        "mounts": "PL, Canon EF, Nikon F",
        "key_features": "S35 wide-angle high-speed zoom; broadcast & indie film; T2 constant; PL mount",
        "price_inr": "₹1,85,000", "price_range_inr": "₹1,78,000 – ₹1,92,000",
        "url": "https://sigmaindia.in/product-category/cine-lenses/",
        "amazon_in": "https://www.amazon.in/s?k=Sigma+18-35mm+T2+cine",
        "weight": "2,000g", "filter": "φ95mm", "min_focus": "28cm"
    },
    {
        "name": "High Speed Zoom 50-100mm T2",
        "line": "High Speed Zoom Line", "category": "Cine Lenses", "type": "Zoom",
        "focal_length": "50-100mm", "aperture": "T2", "format": "Super 35",
        "mounts": "PL, Canon EF, Nikon F",
        "key_features": "S35 telephoto high-speed zoom; pairs with 18-35mm T2; T2 constant; broadcast",
        "price_inr": "₹2,05,000", "price_range_inr": "₹1,98,000 – ₹2,12,000",
        "url": "https://sigmaindia.in/product-category/cine-lenses/",
        "amazon_in": "https://www.amazon.in/s?k=Sigma+50-100mm+T2+cine",
        "weight": "2,400g", "filter": "φ95mm", "min_focus": "100cm"
    },
    # ── ACCESSORIES ──────────────────────────────────────────────────────────
    {
        "name": "USB Dock UD-11",
        "line": "Accessory", "category": "Accessories", "type": "USB Dock",
        "focal_length": "—", "aperture": "—", "format": "—",
        "mounts": "L-Mount, Sony E compatible lenses",
        "key_features": "Firmware update & customisation for mirrorless lenses; AF speed adjustment; USB-C",
        "price_inr": "₹5,500", "price_range_inr": "₹5,000 – ₹6,000",
        "url": "https://sigmaindia.in/product-category/accessories/",
        "amazon_in": "https://www.amazon.in/s?k=Sigma+USB+Dock+UD-11",
        "weight": "—", "filter": "—", "min_focus": "—"
    },
    {
        "name": "USB Dock UD-01",
        "line": "Accessory", "category": "Accessories", "type": "USB Dock",
        "focal_length": "—", "aperture": "—", "format": "—",
        "mounts": "Canon EF, Nikon F, Sigma SA DSLR lenses",
        "key_features": "Firmware update for DSLR lenses; AF speed & OS mode adjustment; Optimization Pro",
        "price_inr": "₹4,800", "price_range_inr": "₹4,500 – ₹5,200",
        "url": "https://sigmaindia.in/product-category/accessories/",
        "amazon_in": "https://www.amazon.in/s?k=Sigma+USB+Dock+UD-01",
        "weight": "—", "filter": "—", "min_focus": "—"
    },
    {
        "name": "Mount Converter MC-21 (SA-L)",
        "line": "Accessory", "category": "Accessories", "type": "Mount Converter",
        "focal_length": "—", "aperture": "—", "format": "—",
        "mounts": "Sigma SA-mount lenses → L-Mount cameras",
        "key_features": "Converts SA-mount lenses to L-Mount; maintains AF/AE/OS; firmware updatable",
        "price_inr": "₹12,500", "price_range_inr": "₹11,500 – ₹13,500",
        "url": "https://sigmaindia.in/product-category/accessories/",
        "amazon_in": "https://www.amazon.in/s?k=Sigma+MC-21+Mount+Converter",
        "weight": "—", "filter": "—", "min_focus": "—"
    },
    {
        "name": "Mount Converter MC-21 (EF-L)",
        "line": "Accessory", "category": "Accessories", "type": "Mount Converter",
        "focal_length": "—", "aperture": "—", "format": "—",
        "mounts": "Canon EF lenses → L-Mount cameras",
        "key_features": "Converts Canon EF lenses to L-Mount; full electronic communication; AF/AE/OS",
        "price_inr": "₹12,500", "price_range_inr": "₹11,500 – ₹13,500",
        "url": "https://sigmaindia.in/product-category/accessories/",
        "amazon_in": "https://www.amazon.in/s?k=Sigma+MC-21+EF-L+Mount+Converter",
        "weight": "—", "filter": "—", "min_focus": "—"
    },
    {
        "name": "Mount Converter MC-11 (SA-E)",
        "line": "Accessory", "category": "Accessories", "type": "Mount Converter",
        "focal_length": "—", "aperture": "—", "format": "—",
        "mounts": "Sigma SA / Canon EF lenses → Sony E-mount cameras",
        "key_features": "Converts to Sony E-mount; Fast Hybrid AF; LED indicator; firmware updatable",
        "price_inr": "₹11,000", "price_range_inr": "₹10,000 – ₹12,000",
        "url": "https://sigmaindia.in/product-category/accessories/",
        "amazon_in": "https://www.amazon.in/s?k=Sigma+MC-11+Mount+Converter",
        "weight": "—", "filter": "—", "min_focus": "—"
    },
    {
        "name": "Mount Converter MC-31",
        "line": "Accessory", "category": "Accessories", "type": "Mount Converter",
        "focal_length": "—", "aperture": "—", "format": "—",
        "mounts": "L-Mount lenses → Nikon Z cameras",
        "key_features": "Converts L-Mount lenses to Nikon Z; AF support; firmware updatable via UD-11",
        "price_inr": "₹14,500", "price_range_inr": "₹13,500 – ₹15,500",
        "url": "https://sigmaindia.in/product-category/accessories/",
        "amazon_in": "https://www.amazon.in/s?k=Sigma+MC-31+Mount+Converter",
        "weight": "—", "filter": "—", "min_focus": "—"
    },
    {
        "name": "Tele Converter TC-1411",
        "line": "Accessory", "category": "Accessories", "type": "Tele Converter",
        "focal_length": "1.4x", "aperture": "—", "format": "—",
        "mounts": "Selected Sigma L-Mount / Sony E Sports & Art telephoto lenses",
        "key_features": "1.4x magnification; maintains full AF; designed for Sports & Art telephoto lenses",
        "price_inr": "₹18,000", "price_range_inr": "₹16,500 – ₹19,500",
        "url": "https://sigmaindia.in/product-category/accessories/",
        "amazon_in": "https://www.amazon.in/s?k=Sigma+TC-1411+Tele+Converter",
        "weight": "—", "filter": "—", "min_focus": "—"
    },
    {
        "name": "Tele Converter TC-2011",
        "line": "Accessory", "category": "Accessories", "type": "Tele Converter",
        "focal_length": "2.0x", "aperture": "—", "format": "—",
        "mounts": "Selected Sigma L-Mount / Sony E Sports & Art telephoto lenses",
        "key_features": "2.0x magnification; maintains AF; paired with TC-1411 for full tele system",
        "price_inr": "₹22,000", "price_range_inr": "₹20,500 – ₹23,500",
        "url": "https://sigmaindia.in/product-category/accessories/",
        "amazon_in": "https://www.amazon.in/s?k=Sigma+TC-2011+Tele+Converter",
        "weight": "—", "filter": "—", "min_focus": "—"
    },
    {
        "name": "Electronic Viewfinder EVF-11",
        "line": "Accessory", "category": "Accessories", "type": "Viewfinder",
        "focal_length": "—", "aperture": "—", "format": "—",
        "mounts": "Sigma fp / fp L cameras",
        "key_features": "0.5-inch OLED 3.68M-dot; tilts 90°; 0.83× magnification; 3.5mm audio jack; hot shoe",
        "price_inr": "₹38,000", "price_range_inr": "₹35,000 – ₹41,000",
        "url": "https://sigmaindia.in/product/electronic-viewfinder-evf-11-3/",
        "amazon_in": "https://www.amazon.in/s?k=Sigma+EVF-11+Electronic+Viewfinder",
        "weight": "—", "filter": "—", "min_focus": "—"
    },
    {
        "name": "Electronic Flash EF-630",
        "line": "Accessory", "category": "Accessories", "type": "Flash",
        "focal_length": "—", "aperture": "—", "format": "—",
        "mounts": "Canon / Nikon / Sigma / Sony cameras",
        "key_features": "Guide No. 63; TTL; high-speed sync; wireless; auto zoom 24-200mm; bounce panel",
        "price_inr": "₹22,000", "price_range_inr": "₹20,000 – ₹24,000",
        "url": "https://sigmaindia.in/product-category/accessories/",
        "amazon_in": "https://www.amazon.in/s?k=Sigma+EF-630+Flash",
        "weight": "—", "filter": "—", "min_focus": "—"
    },
    {
        "name": "WR Circular PL Filter",
        "line": "Accessory", "category": "Accessories", "type": "Filter",
        "focal_length": "—", "aperture": "—", "format": "—",
        "mounts": "Various filter thread sizes (46–105mm)",
        "key_features": "Weather-resistant circular polariser; Super Multi-Layer Coating; reduces reflections",
        "price_inr": "₹4,500", "price_range_inr": "₹4,000 – ₹5,500",
        "url": "https://sigmaindia.in/product-category/accessories/",
        "amazon_in": "https://www.amazon.in/s?k=Sigma+WR+Circular+PL+Filter",
        "weight": "—", "filter": "various", "min_focus": "—"
    },
    {
        "name": "WR UV Filter",
        "line": "Accessory", "category": "Accessories", "type": "Filter",
        "focal_length": "—", "aperture": "—", "format": "—",
        "mounts": "Various filter thread sizes",
        "key_features": "Weather-resistant UV protective filter; Super Multi-Layer Coating; reduces UV haze",
        "price_inr": "₹3,200", "price_range_inr": "₹2,800 – ₹3,800",
        "url": "https://sigmaindia.in/product-category/accessories/",
        "amazon_in": "https://www.amazon.in/s?k=Sigma+WR+UV+Filter",
        "weight": "—", "filter": "various", "min_focus": "—"
    },
    {
        "name": "WR Ceramic Protector Filter",
        "line": "Accessory", "category": "Accessories", "type": "Filter",
        "focal_length": "—", "aperture": "—", "format": "—",
        "mounts": "Various filter thread sizes",
        "key_features": "Ultra-strong ceramic glass; Vickers hardness 700HV; weather-resistant; scratch-proof",
        "price_inr": "₹6,500", "price_range_inr": "₹6,000 – ₹7,200",
        "url": "https://sigmaindia.in/product-category/accessories/",
        "amazon_in": "https://www.amazon.in/s?k=Sigma+WR+Ceramic+Protector",
        "weight": "—", "filter": "various", "min_focus": "—"
    },
]

# ── INDIA DEALERS (scraped from sigmaindia.in/dealer-network) ─────────────────
INDIA_DEALERS = {
    "Karnataka / Bangalore": [
        {"name": "Shetala Cameras", "location": "Bangalore", "phone": "41238528/29"},
        {"name": "Foto Circle (Orion Mall)", "location": "Bangalore", "phone": "080-22682164 / 9844217788"},
        {"name": "Foto Circle (Koramangala)", "location": "Bangalore", "phone": "080-40953350 / 9844442028"},
        {"name": "Camerena (Brigade Road)", "location": "Bangalore", "phone": "080-41277134 / 9945156597"},
        {"name": "G.K Vale & Co (Marathahalli)", "location": "Bangalore", "phone": "080-41680066"},
        {"name": "Whizz (Forum Mall)", "location": "Bangalore", "phone": "080-22067721"},
    ],
    "Tamil Nadu / Chennai": [
        {"name": "Shetala Agencies Pvt Ltd", "location": "Chennai", "phone": "9884104218"},
        {"name": "Chennai Cameras", "location": "Chennai", "phone": "044-43102224 / 9884244369"},
        {"name": "Foto Trade", "location": "Chennai", "phone": "044-28583444 / 9840406796"},
        {"name": "FStop", "location": "Chennai", "phone": "044-45566455 / 9940076610"},
        {"name": "Rathna Photo Impex Center", "location": "Chennai", "phone": "044-42155146 / 9444002558"},
    ],
    "Delhi / NCR": [
        {"name": "Golu Photos", "location": "Delhi", "phone": "23278483 / 9811062088"},
        {"name": "Future Forward", "location": "Delhi", "phone": "9999976594"},
        {"name": "Mahatta & Co", "location": "Delhi", "phone": "41517220 / 23414139"},
        {"name": "Kumar Jee", "location": "Gurgaon", "phone": "9810073841 / 0124-4264441"},
        {"name": "Retinapix Camera Store", "location": "Delhi", "phone": "8920290043"},
    ],
    "Maharashtra / Mumbai": [
        {"name": "Shetala Cameras", "location": "Mumbai", "phone": "9619825776"},
        {"name": "Foto Centre", "location": "Mumbai", "phone": "22-22659344 / 22641727"},
        {"name": "Peoples Camera Co", "location": "Mumbai", "phone": "022-22666770"},
        {"name": "Reliable Photo Store", "location": "Mumbai", "phone": "022-22614319"},
    ],
    "Telangana / Hyderabad": [
        {"name": "Shetala Agencies Pvt Ltd", "location": "Hyderabad", "phone": "9700885776"},
        {"name": "Chaaya Photo Services", "location": "Secunderabad", "phone": "040-64566014 / 8885577815"},
    ],
    "Kerala": [
        {"name": "Shetala Agencies Pvt Ltd", "location": "Ernakulam", "phone": "9961204700"},
        {"name": "Photo Link", "location": "Thrissur", "phone": "04873241226"},
        {"name": "Galaxy", "location": "Calicut", "phone": "4954017575"},
        {"name": "Babas", "location": "Thiruvananthapuram", "phone": "0471-2573888"},
    ],
    "West Bengal / Kolkata": [
        {"name": "Shetala Agencies Pvt Ltd", "location": "Kolkata", "phone": "9830375753"},
        {"name": "M.M.Photographic Stores", "location": "Kolkata", "phone": "22280456 / 9674441233"},
        {"name": "Capital Chowringhee Pvt Ltd", "location": "Kolkata", "phone": "22285857 / 9831052332"},
    ],
    "Andhra Pradesh": [
        {"name": "Venus Photo Emporium", "location": "Vijayawada", "phone": "9440705451"},
        {"name": "Model Photographic Co Pvt Ltd", "location": "Vijayawada", "phone": "0866-2575499"},
        {"name": "Gowri Natraj Enterprises", "location": "Visakhapatnam", "phone": "0891-6666722"},
    ],
}


# ── SEARCH ────────────────────────────────────────────────────────────────────
def search_products(query: str, limit: int = 8):
    q = query.lower()
    keywords = re.split(r"[\s,/\-]+", q)
    keywords = [k for k in keywords if len(k) > 2]
    scored = []
    for p in PRODUCTS:
        searchable = " ".join(str(v) for v in p.values()).lower()
        score = sum(
            3 if k in p.get("name", "").lower() else
            2 if k in p.get("key_features", "").lower() else
            1 if k in searchable else 0
            for k in keywords
        )
        if score > 0:
            scored.append((score, p))
    scored.sort(key=lambda x: -x[0])
    return [p for _, p in scored[:limit]]


# ── SYSTEM PROMPT ─────────────────────────────────────────────────────────────
def build_system_prompt():
    catalogue_lines = []
    for p in PRODUCTS:
        catalogue_lines.append(
            f"- [{p['category']}] {p['name']} | Line: {p['line']} | "
            f"{p['focal_length']} {p['aperture']} | Format: {p['format']} | "
            f"Mounts: {p['mounts']} | Price: {p['price_inr']} | "
            f"Features: {p['key_features'][:80]} | URL: {p['url']}"
        )

    dealer_summary = ""
    for region, dealers in INDIA_DEALERS.items():
        names = ", ".join(d["name"] for d in dealers[:3])
        dealer_summary += f"\n- {region}: {names} (+{len(dealers)-3} more)" if len(dealers) > 3 else f"\n- {region}: {names}"

    return f"""You are the Sigma India AI Agent — the official AI assistant for Sigma India (sigmaindia.in), 
operated by Shetala Agencies Pvt Ltd. You help Indian photographers and filmmakers discover 
the perfect Sigma products. You are knowledgeable, helpful, and enthusiastic about photography.

BRAND: Sigma India — Made in Aizu, Japan. Pursuit of Perfection.
WEBSITE: sigmaindia.in
DISTRIBUTOR: Shetala Agencies Pvt Ltd

SIGMA INDIA PRODUCT CATALOGUE ({len(PRODUCTS)} products):
{chr(10).join(catalogue_lines)}

INDIA DEALER NETWORK:{dealer_summary}

KEY CAPABILITIES:
1. PRODUCT DISCOVERY: Recommend best Sigma products based on shooting style, budget (INR), camera system
2. SPEC COMPARISON: Compare products technically
3. COMPATIBILITY: Answer mount/sensor/camera compatibility questions  
4. PRICE GUIDANCE: All prices in Indian Rupees (₹). Mention Amazon India and local dealers
5. DEALER NETWORK: Direct users to local authorised Sigma dealers across India
6. WARRANTY: 2-year warranty through Shetala Agencies for products bought from authorised dealers

RESPONSE RULES:
- Always return product recommendations as a JSON block for the frontend to render as cards:
```json_products
[
  {{
    "name": "Product Name",
    "line": "Art/Contemporary/Sports/etc",
    "category": "Still Lenses/Cine Lenses/Cameras/Accessories",
    "focal_length": "...",
    "aperture": "...",
    "mounts": "...",
    "key_features": "...",
    "url": "https://sigmaindia.in/...",
    "amazon_in": "https://www.amazon.in/...",
    "price_inr": "₹XX,XXX",
    "price_range_inr": "₹XX,XXX – ₹XX,XXX",
    "reason": "Why this matches the user's need"
  }}
]
```
- After JSON, write a 2-4 sentence conversational explanation
- For price queries, include a ```json_prices block
- For dealer queries, include a ```json_dealers block

PRICE BLOCK FORMAT (in INR):
```json_prices
[
  {{"platform": "Sigma India Official", "price": "₹XX,XXX", "url": "https://sigmaindia.in/", "status": "Authorised"}},
  {{"platform": "Amazon India", "price": "₹XX,XXX – ₹XX,XXX", "url": "https://www.amazon.in/s?k=...", "status": "Check listing"}},
  {{"platform": "Flipkart", "price": "₹XX,XXX", "url": "https://www.flipkart.com/search?q=sigma+lens", "status": "Check listing"}},
  {{"platform": "Local Authorised Dealer", "price": "Negotiable", "url": "https://sigmaindia.in/dealer-network/", "status": "Best price + warranty"}}
]
```

DEALER BLOCK FORMAT:
```json_dealers
[
  {{"name": "Shetala Agencies Pvt Ltd", "type": "National Distributor", "location": "Pan India", "phone": "9700885776", "url": "https://sigmaindia.in/dealer-network/"}},
  {{"name": "Sigma India Dealer Network", "type": "Authorised Dealers", "location": "All major Indian cities", "phone": "—", "url": "https://sigmaindia.in/dealer-network/"}}
]
```

IMPORTANT: 
- All prices must be in Indian Rupees (₹)
- Mention Amazon India links when available for each product
- Always recommend buying from authorised Sigma India dealers for warranty
- Never invent products Sigma doesn't make"""


# ── CALL CLAUDE ───────────────────────────────────────────────────────────────
def call_claude(messages: list, system: str) -> str:
    import urllib.request, urllib.error
    if not ANTHROPIC_API_KEY:
        return _fallback_response(messages[-1]["content"] if messages else "")

    payload = json.dumps({
        "model": CLAUDE_MODEL,
        "max_tokens": 2048,
        "system": system,
        "messages": messages
    }).encode("utf-8")

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
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["content"][0]["text"]
    except Exception as e:
        print(f"[CLAUDE ERROR] {e}")
        return _fallback_response(messages[-1]["content"] if messages else "")


def _fallback_response(query: str) -> str:
    results = search_products(query, limit=4)
    if not results:
        return ("I couldn't find specific products matching that query. "
                "Try asking about a focal length, aperture, or product line like 'Art' or 'Contemporary'.")
    products_json = []
    for p in results:
        products_json.append({
            "name": p.get("name", ""),
            "line": p.get("line", ""),
            "category": p.get("category", ""),
            "focal_length": p.get("focal_length", ""),
            "aperture": p.get("aperture", ""),
            "mounts": p.get("mounts", ""),
            "key_features": p.get("key_features", "")[:120],
            "url": p.get("url", "https://sigmaindia.in/"),
            "amazon_in": p.get("amazon_in", ""),
            "price_inr": p.get("price_inr", "—"),
            "price_range_inr": p.get("price_range_inr", "—"),
            "reason": "Matches your search criteria"
        })
    json_block = "```json_products\n" + json.dumps(products_json, indent=2) + "\n```"
    return (f"{json_block}\n\nHere are the Sigma India products matching your query. "
            "Visit sigmaindia.in or contact your nearest authorised Sigma dealer for current pricing and availability.")


def parse_response(raw: str) -> dict:
    result = {"text": raw, "products": [], "prices": [], "dealers": []}
    def extract_block(tag):
        pattern = rf"```{tag}\s*([\s\S]*?)```"
        match = re.search(pattern, raw)
        if match:
            try: return json.loads(match.group(1).strip())
            except: return []
        return []
    result["products"] = extract_block("json_products")
    result["prices"] = extract_block("json_prices")
    result["dealers"] = extract_block("json_dealers")
    clean = re.sub(r"```json_\w+\s*[\s\S]*?```", "", raw).strip()
    result["text"] = clean
    return result


# ── ROUTES ────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    session.setdefault("history", [])
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    user_msg = (data.get("message") or "").strip()
    if not user_msg:
        return jsonify({"error": "Empty message"}), 400
    history = session.get("history", [])
    history.append({"role": "user", "content": user_msg})
    if len(history) > 20:
        history = history[-20:]
    raw = call_claude(history, build_system_prompt())
    history.append({"role": "assistant", "content": raw})
    session["history"] = history
    return jsonify(parse_response(raw))

@app.route("/reset", methods=["POST"])
def reset():
    session["history"] = []
    return jsonify({"ok": True})

@app.route("/products")
def products_api():
    q = request.args.get("q", "")
    if q:
        return jsonify(search_products(q, 10))
    return jsonify(PRODUCTS[:30])

@app.route("/dealers")
def dealers_api():
    return jsonify(INDIA_DEALERS)

if __name__ == "__main__":
    print("=" * 60)
    print("  SIGMA INDIA AI AGENT — http://localhost:5000")
    if not ANTHROPIC_API_KEY:
        print("  ⚠  No ANTHROPIC_API_KEY — using local fallback mode")
        print("  ✦  export ANTHROPIC_API_KEY=sk-ant-...")
    print("=" * 60)
    app.run(debug=True, port=5000)
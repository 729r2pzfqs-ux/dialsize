#!/usr/bin/env python3
"""DialSize.com — Static site generator.

Reads watch data from data/*.json, renders Jinja2 templates, and writes
a complete static site into docs/ for GitHub Pages deployment.
"""

import json
import os
import re
import shutil
import urllib.parse
from collections import defaultdict
from datetime import datetime
from itertools import combinations

from jinja2 import BaseLoader, Environment, TemplateNotFound

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SITE_URL = "https://dialsize.com"
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
OUT_DIR = os.path.join(os.path.dirname(__file__), "docs")
GA_ID = "G-9W8FY82CS3"
ADSENSE_PUB = "ca-pub-5861928596436289"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def slugify(text):
    """Turn arbitrary text into a URL-safe slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    return re.sub(r"[-\s]+", "-", text).strip("-")


def ref_slug(ref):
    """Sanitise a reference number for use in URLs."""
    return ref.lower().replace(".", "-").replace("/", "-").replace(" ", "-")


def safe_float(val, default=0.0):
    """Return a float or *default* when the value is None / missing."""
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def safe_int(val, default=0):
    if val is None:
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def fmt_mm(val):
    if val is None:
        return "N/A"
    return f"{val:.1f} mm" if isinstance(val, float) else f"{val} mm"


def fmt_g(val):
    if val is None:
        return "N/A"
    return f"{val} g"


def fmt_usd(val):
    if val is None:
        return "N/A"
    return f"${val:,.0f}"


def fmt_vph(val):
    if val is None:
        return "N/A"
    return f"{val:,} vph"


def fmt_hours(val):
    if val is None:
        return "N/A"
    return f"{val} hours"


def fmt_m(val):
    if val is None:
        return "N/A"
    return f"{val} m"


def wrist_fit(lug_to_lug):
    """Return (min_inches, min_cm) tuple based on L2L."""
    if lug_to_lug is None:
        return None
    l2l = safe_float(lug_to_lug)
    if l2l <= 44:
        return ("5.75\"", "14.5 cm")
    elif l2l <= 46:
        return ("6.0\"", "15 cm")
    elif l2l <= 48:
        return ("6.5\"", "16.5 cm")
    elif l2l <= 50:
        return ("6.75\"", "17 cm")
    elif l2l <= 52:
        return ("7.0\"", "17.8 cm")
    else:
        return ("7.25\"", "18.5 cm")


def affiliate_ebay(brand, model, ref):
    q = urllib.parse.quote_plus(f"{brand} {model} {ref}")
    return (f"https://www.ebay.com/sch/i.html?_nkw={q}"
            "&mkcid=1&mkrid=711-53200-19255-0&campid=5339221177&toolid=10001")


def affiliate_jomashop(brand, model):
    q = urllib.parse.quote_plus(f"{brand} {model}")
    return f"https://www.jomashop.com/catalogsearch/result/?q={q}"


def affiliate_chrono24(brand, ref):
    q = urllib.parse.quote_plus(f"{brand} {ref}")
    return f"https://www.chrono24.com/search/index.htm?query={q}"


def affiliate_amazon(brand, model):
    q = urllib.parse.quote_plus(f"{brand} {model}")
    return f"https://www.amazon.com/s?k={q}"


def is_rectangular(watch):
    """Heuristic: G-Shock squares and Casio digitals are rectangular."""
    ref = watch.get("reference", "").upper()
    name = (watch.get("name") or "").lower()
    collection = (watch.get("collection") or "").lower()
    if any(kw in name for kw in ["square", "digital", "iconic digital", "classic digital"]):
        return True
    if ref.startswith("DW-5600") or ref.startswith("GW-M5610") or ref.startswith("GMW-B5000"):
        return True
    if ref.startswith("DW-5610") or ref.startswith("GW-B5600") or ref.startswith("MRG-B5000"):
        return True
    if ref.startswith("A168") or ref.startswith("F-91"):
        return True
    return False


# ---------------------------------------------------------------------------
# SVG diagram generation
# ---------------------------------------------------------------------------

def generate_svg(watch):
    """Return inline SVG showing front + side profiles with dimension lines."""
    d = watch.get("dimensions", {})
    diameter = safe_float(d.get("diameter_mm"), 40)
    l2l = safe_float(d.get("lug_to_lug_mm"), 48)
    thickness = safe_float(d.get("thickness_mm"), 12)
    lug_w = safe_float(d.get("lug_width_mm"), 20)
    rect = is_rectangular(watch)

    # Drawing constants — everything in SVG user units
    vb_w, vb_h = 520, 300
    cx_front = 160  # centre of front view
    cy = 150
    scale = 3.2  # mm -> SVG units

    r_dia = diameter * scale / 2
    r_l2l = l2l * scale / 2
    r_lug = lug_w * scale / 2
    t_scaled = thickness * scale

    navy = "#1a1f36"
    gold = "#c4a35a"
    bg = "none"
    stroke_w = 1.8
    dim_stroke = 1.2
    font_size = 11
    font_sm = 9.5

    parts = []
    parts.append(f'<svg viewBox="0 0 {vb_w} {vb_h}" xmlns="http://www.w3.org/2000/svg" '
                 f'role="img" aria-label="Dimensions diagram for {watch.get("brand","")} {watch.get("name","")}">')
    parts.append(f'<rect width="{vb_w}" height="{vb_h}" fill="{bg}"/>')

    # --- Front view ---
    if rect:
        # rectangular case
        rw = diameter * scale * 0.55
        rh = l2l * scale * 0.45
        rx, ry = cx_front - rw, cy - rh
        parts.append(f'<rect x="{rx:.1f}" y="{ry:.1f}" width="{rw*2:.1f}" height="{rh*2:.1f}" '
                     f'rx="8" ry="8" fill="none" stroke="{navy}" stroke-width="{stroke_w}"/>')
        # lugs
        parts.append(f'<line x1="{cx_front - r_lug:.1f}" y1="{cy - rh:.1f}" '
                     f'x2="{cx_front - r_lug:.1f}" y2="{cy - r_l2l:.1f}" '
                     f'stroke="{navy}" stroke-width="{stroke_w}"/>')
        parts.append(f'<line x1="{cx_front + r_lug:.1f}" y1="{cy - rh:.1f}" '
                     f'x2="{cx_front + r_lug:.1f}" y2="{cy - r_l2l:.1f}" '
                     f'stroke="{navy}" stroke-width="{stroke_w}"/>')
        parts.append(f'<line x1="{cx_front - r_lug:.1f}" y1="{cy + rh:.1f}" '
                     f'x2="{cx_front - r_lug:.1f}" y2="{cy + r_l2l:.1f}" '
                     f'stroke="{navy}" stroke-width="{stroke_w}"/>')
        parts.append(f'<line x1="{cx_front + r_lug:.1f}" y1="{cy + rh:.1f}" '
                     f'x2="{cx_front + r_lug:.1f}" y2="{cy + r_l2l:.1f}" '
                     f'stroke="{navy}" stroke-width="{stroke_w}"/>')
        # top/bottom bars
        parts.append(f'<line x1="{cx_front - r_lug:.1f}" y1="{cy - r_l2l:.1f}" '
                     f'x2="{cx_front + r_lug:.1f}" y2="{cy - r_l2l:.1f}" '
                     f'stroke="{navy}" stroke-width="{stroke_w}"/>')
        parts.append(f'<line x1="{cx_front - r_lug:.1f}" y1="{cy + r_l2l:.1f}" '
                     f'x2="{cx_front + r_lug:.1f}" y2="{cy + r_l2l:.1f}" '
                     f'stroke="{navy}" stroke-width="{stroke_w}"/>')
    else:
        # round case
        parts.append(f'<circle cx="{cx_front}" cy="{cy}" r="{r_dia:.1f}" '
                     f'fill="none" stroke="{navy}" stroke-width="{stroke_w}"/>')
        # inner bezel
        parts.append(f'<circle cx="{cx_front}" cy="{cy}" r="{r_dia*0.88:.1f}" '
                     f'fill="none" stroke="{navy}" stroke-width="0.6" opacity="0.3"/>')
        # lugs — small rectangles at top and bottom
        parts.append(f'<line x1="{cx_front - r_lug:.1f}" y1="{cy - r_dia + 2:.1f}" '
                     f'x2="{cx_front - r_lug:.1f}" y2="{cy - r_l2l:.1f}" '
                     f'stroke="{navy}" stroke-width="{stroke_w}"/>')
        parts.append(f'<line x1="{cx_front + r_lug:.1f}" y1="{cy - r_dia + 2:.1f}" '
                     f'x2="{cx_front + r_lug:.1f}" y2="{cy - r_l2l:.1f}" '
                     f'stroke="{navy}" stroke-width="{stroke_w}"/>')
        parts.append(f'<line x1="{cx_front - r_lug:.1f}" y1="{cy + r_dia - 2:.1f}" '
                     f'x2="{cx_front - r_lug:.1f}" y2="{cy + r_l2l:.1f}" '
                     f'stroke="{navy}" stroke-width="{stroke_w}"/>')
        parts.append(f'<line x1="{cx_front + r_lug:.1f}" y1="{cy + r_dia - 2:.1f}" '
                     f'x2="{cx_front + r_lug:.1f}" y2="{cy + r_l2l:.1f}" '
                     f'stroke="{navy}" stroke-width="{stroke_w}"/>')
        # bars connecting lug tips
        parts.append(f'<line x1="{cx_front - r_lug:.1f}" y1="{cy - r_l2l:.1f}" '
                     f'x2="{cx_front + r_lug:.1f}" y2="{cy - r_l2l:.1f}" '
                     f'stroke="{navy}" stroke-width="{stroke_w}"/>')
        parts.append(f'<line x1="{cx_front - r_lug:.1f}" y1="{cy + r_l2l:.1f}" '
                     f'x2="{cx_front + r_lug:.1f}" y2="{cy + r_l2l:.1f}" '
                     f'stroke="{navy}" stroke-width="{stroke_w}"/>')
        # crown nub
        parts.append(f'<rect x="{cx_front + r_dia - 1:.1f}" y="{cy - 5}" width="10" height="10" '
                     f'rx="2" fill="none" stroke="{navy}" stroke-width="{stroke_w}"/>')

    # --- Dimension lines (front view) ---
    dim_x_right = cx_front + r_dia + 28
    # Diameter: horizontal line across centre
    parts.append(f'<line x1="{cx_front - r_dia:.1f}" y1="{cy}" '
                 f'x2="{cx_front + r_dia:.1f}" y2="{cy}" '
                 f'stroke="{gold}" stroke-width="{dim_stroke}" stroke-dasharray="4 2"/>')
    # arrowheads
    parts.append(f'<polygon points="{cx_front - r_dia:.1f},{cy} {cx_front - r_dia + 6:.1f},{cy - 3} '
                 f'{cx_front - r_dia + 6:.1f},{cy + 3}" fill="{gold}"/>')
    parts.append(f'<polygon points="{cx_front + r_dia:.1f},{cy} {cx_front + r_dia - 6:.1f},{cy - 3} '
                 f'{cx_front + r_dia - 6:.1f},{cy + 3}" fill="{gold}"/>')
    parts.append(f'<text x="{cx_front}" y="{cy - 7}" text-anchor="middle" '
                 f'fill="{gold}" font-size="{font_size}" font-weight="600" font-family="sans-serif">'
                 f'{diameter:.1f} mm</text>')

    # L2L: vertical line right side
    parts.append(f'<line x1="{dim_x_right}" y1="{cy - r_l2l:.1f}" '
                 f'x2="{dim_x_right}" y2="{cy + r_l2l:.1f}" '
                 f'stroke="{gold}" stroke-width="{dim_stroke}" stroke-dasharray="4 2"/>')
    parts.append(f'<polygon points="{dim_x_right},{cy - r_l2l:.1f} {dim_x_right - 3},{cy - r_l2l + 6:.1f} '
                 f'{dim_x_right + 3},{cy - r_l2l + 6:.1f}" fill="{gold}"/>')
    parts.append(f'<polygon points="{dim_x_right},{cy + r_l2l:.1f} {dim_x_right - 3},{cy + r_l2l - 6:.1f} '
                 f'{dim_x_right + 3},{cy + r_l2l - 6:.1f}" fill="{gold}"/>')
    parts.append(f'<text x="{dim_x_right + 6}" y="{cy + 4}" text-anchor="start" '
                 f'fill="{gold}" font-size="{font_size}" font-weight="600" font-family="sans-serif">'
                 f'{l2l:.1f} mm</text>')
    # extension lines
    parts.append(f'<line x1="{cx_front + r_lug + 4:.1f}" y1="{cy - r_l2l:.1f}" '
                 f'x2="{dim_x_right - 2}" y2="{cy - r_l2l:.1f}" '
                 f'stroke="{gold}" stroke-width="0.6"/>')
    parts.append(f'<line x1="{cx_front + r_lug + 4:.1f}" y1="{cy + r_l2l:.1f}" '
                 f'x2="{dim_x_right - 2}" y2="{cy + r_l2l:.1f}" '
                 f'stroke="{gold}" stroke-width="0.6"/>')

    # Lug width: at bottom
    lw_y = cy + r_l2l + 22
    parts.append(f'<line x1="{cx_front - r_lug:.1f}" y1="{lw_y}" '
                 f'x2="{cx_front + r_lug:.1f}" y2="{lw_y}" '
                 f'stroke="{gold}" stroke-width="{dim_stroke}" stroke-dasharray="4 2"/>')
    parts.append(f'<polygon points="{cx_front - r_lug:.1f},{lw_y} {cx_front - r_lug + 5:.1f},{lw_y - 3} '
                 f'{cx_front - r_lug + 5:.1f},{lw_y + 3}" fill="{gold}"/>')
    parts.append(f'<polygon points="{cx_front + r_lug:.1f},{lw_y} {cx_front + r_lug - 5:.1f},{lw_y - 3} '
                 f'{cx_front + r_lug - 5:.1f},{lw_y + 3}" fill="{gold}"/>')
    # extension lines
    parts.append(f'<line x1="{cx_front - r_lug:.1f}" y1="{cy + r_l2l + 2:.1f}" '
                 f'x2="{cx_front - r_lug:.1f}" y2="{lw_y - 2}" '
                 f'stroke="{gold}" stroke-width="0.6"/>')
    parts.append(f'<line x1="{cx_front + r_lug:.1f}" y1="{cy + r_l2l + 2:.1f}" '
                 f'x2="{cx_front + r_lug:.1f}" y2="{lw_y - 2}" '
                 f'stroke="{gold}" stroke-width="0.6"/>')
    parts.append(f'<text x="{cx_front}" y="{lw_y + 14}" text-anchor="middle" '
                 f'fill="{gold}" font-size="{font_sm}" font-weight="600" font-family="sans-serif">'
                 f'Lug width: {lug_w:.0f} mm</text>')

    # --- Side profile ---
    side_cx = 400
    side_w = t_scaled
    side_h = r_dia * 1.6  # proportional to diameter
    side_top = cy - side_h / 2
    parts.append(f'<rect x="{side_cx - side_w / 2:.1f}" y="{side_top:.1f}" '
                 f'width="{side_w:.1f}" height="{side_h:.1f}" rx="4" '
                 f'fill="none" stroke="{navy}" stroke-width="{stroke_w}"/>')
    # crystal bump
    parts.append(f'<line x1="{side_cx - side_w / 2:.1f}" y1="{side_top:.1f}" '
                 f'x2="{side_cx + side_w / 2:.1f}" y2="{side_top:.1f}" '
                 f'stroke="{navy}" stroke-width="{stroke_w + 0.5}"/>')
    # caseback
    parts.append(f'<line x1="{side_cx - side_w / 2:.1f}" y1="{side_top + side_h:.1f}" '
                 f'x2="{side_cx + side_w / 2:.1f}" y2="{side_top + side_h:.1f}" '
                 f'stroke="{navy}" stroke-width="{stroke_w + 0.5}"/>')

    # thickness dimension
    th_x = side_cx + side_w / 2 + 22
    parts.append(f'<line x1="{th_x}" y1="{side_top:.1f}" '
                 f'x2="{th_x}" y2="{side_top + side_h:.1f}" '
                 f'stroke="{gold}" stroke-width="{dim_stroke}" stroke-dasharray="4 2"/>')
    parts.append(f'<polygon points="{th_x},{side_top:.1f} {th_x-3},{side_top+6:.1f} '
                 f'{th_x+3},{side_top+6:.1f}" fill="{gold}"/>')
    parts.append(f'<polygon points="{th_x},{side_top + side_h:.1f} {th_x-3},{side_top + side_h - 6:.1f} '
                 f'{th_x+3},{side_top + side_h - 6:.1f}" fill="{gold}"/>')
    parts.append(f'<text x="{th_x + 6}" y="{cy + 4}" text-anchor="start" '
                 f'fill="{gold}" font-size="{font_size}" font-weight="600" font-family="sans-serif">'
                 f'{thickness:.1f} mm</text>')
    # extension lines
    parts.append(f'<line x1="{side_cx + side_w / 2 + 4:.1f}" y1="{side_top:.1f}" '
                 f'x2="{th_x - 2}" y2="{side_top:.1f}" '
                 f'stroke="{gold}" stroke-width="0.6"/>')
    parts.append(f'<line x1="{side_cx + side_w / 2 + 4:.1f}" y1="{side_top + side_h:.1f}" '
                 f'x2="{th_x - 2}" y2="{side_top + side_h:.1f}" '
                 f'stroke="{gold}" stroke-width="0.6"/>')

    # Labels
    parts.append(f'<text x="{cx_front}" y="22" text-anchor="middle" '
                 f'fill="{navy}" font-size="{font_sm}" font-weight="600" font-family="sans-serif">'
                 f'Front View</text>')
    parts.append(f'<text x="{side_cx}" y="22" text-anchor="middle" '
                 f'fill="{navy}" font-size="{font_sm}" font-weight="600" font-family="sans-serif">'
                 f'Side Profile</text>')

    parts.append("</svg>")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Compare SVG overlay
# ---------------------------------------------------------------------------

def generate_compare_svg(w1, w2):
    """Overlay two watch outlines for size comparison."""
    d1 = w1.get("dimensions", {})
    d2 = w2.get("dimensions", {})
    dia1 = safe_float(d1.get("diameter_mm"), 40)
    dia2 = safe_float(d2.get("diameter_mm"), 40)
    l2l1 = safe_float(d1.get("lug_to_lug_mm"), 48)
    l2l2 = safe_float(d2.get("lug_to_lug_mm"), 48)

    vb_w, vb_h = 360, 300
    cx, cy = 180, 150
    scale = 3.0
    navy = "#1a1f36"
    gold = "#c4a35a"

    parts = [f'<svg viewBox="0 0 {vb_w} {vb_h}" xmlns="http://www.w3.org/2000/svg" '
             f'role="img" aria-label="Size comparison overlay">']

    r1 = dia1 * scale / 2
    r2 = dia2 * scale / 2

    # Watch 1 — navy solid
    if is_rectangular(w1):
        rw = dia1 * scale * 0.55
        rh = l2l1 * scale * 0.45
        parts.append(f'<rect x="{cx - rw:.1f}" y="{cy - rh:.1f}" width="{rw*2:.1f}" height="{rh*2:.1f}" '
                     f'rx="6" fill="none" stroke="{navy}" stroke-width="2"/>')
    else:
        parts.append(f'<circle cx="{cx}" cy="{cy}" r="{r1:.1f}" '
                     f'fill="none" stroke="{navy}" stroke-width="2"/>')

    # Watch 2 — gold dashed
    if is_rectangular(w2):
        rw = dia2 * scale * 0.55
        rh = l2l2 * scale * 0.45
        parts.append(f'<rect x="{cx - rw:.1f}" y="{cy - rh:.1f}" width="{rw*2:.1f}" height="{rh*2:.1f}" '
                     f'rx="6" fill="none" stroke="{gold}" stroke-width="2" stroke-dasharray="6 3"/>')
    else:
        parts.append(f'<circle cx="{cx}" cy="{cy}" r="{r2:.1f}" '
                     f'fill="none" stroke="{gold}" stroke-width="2" stroke-dasharray="6 3"/>')

    # Legend
    parts.append(f'<line x1="20" y1="20" x2="40" y2="20" stroke="{navy}" stroke-width="2"/>')
    parts.append(f'<text x="46" y="24" fill="{navy}" font-size="10" font-family="sans-serif">'
                 f'{w1["brand"]} {w1.get("name","")} ({dia1:.1f} mm)</text>')
    parts.append(f'<line x1="20" y1="36" x2="40" y2="36" stroke="{gold}" stroke-width="2" stroke-dasharray="6 3"/>')
    parts.append(f'<text x="46" y="40" fill="{gold}" font-size="10" font-family="sans-serif">'
                 f'{w2["brand"]} {w2.get("name","")} ({dia2:.1f} mm)</text>')

    parts.append("</svg>")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_all_data():
    """Load every brand JSON file and return a flat list of watches + brand list."""
    brands = []
    all_watches = []
    for fn in sorted(os.listdir(DATA_DIR)):
        if not fn.endswith(".json"):
            continue
        with open(os.path.join(DATA_DIR, fn), "r") as f:
            data = json.load(f)
        brands.append({
            "brand": data["brand"],
            "brand_slug": data["brand_slug"],
            "brand_description": data.get("brand_description", ""),
            "watch_count": len(data["watches"]),
        })
        for w in data["watches"]:
            w.setdefault("brand", data["brand"])
            w.setdefault("brand_slug", data["brand_slug"])
            all_watches.append(w)
    return brands, all_watches


def build_collections(watches):
    """Group watches by (brand_slug, collection_slug)."""
    colls = defaultdict(list)
    for w in watches:
        key = (w["brand_slug"], w.get("collection_slug", slugify(w.get("collection", "other"))))
        colls[key].append(w)
    return dict(colls)


def build_lug_width_map(watches):
    """Group watches by lug width in mm."""
    lw_map = defaultdict(list)
    for w in watches:
        lw = w.get("dimensions", {}).get("lug_width_mm")
        if lw is not None:
            lw_map[int(lw)].append(w)
    return dict(lw_map)


def build_watch_index(watches):
    """Build a dict keyed by (brand_slug, collection_slug, ref_slug)."""
    idx = {}
    for w in watches:
        key = (w["brand_slug"],
               w.get("collection_slug", slugify(w.get("collection", "other"))),
               ref_slug(w["reference"]))
        idx[key] = w
    return idx


# ---------------------------------------------------------------------------
# Compare page list generation
# ---------------------------------------------------------------------------

PRIORITY_COMPARISONS = [
    ("rolex", "submariner", "124060", "tudor", "black-bay", "79230N"),
    ("rolex", "submariner", "124060", "omega", "seamaster-diver-300m", "210.30.42.20.01.001"),
    ("rolex", "explorer", "124270", "tudor", "ranger", "79950"),
    ("rolex", "explorer", "124270", "rolex", "explorer", "226570"),
    ("omega", "speedmaster-moonwatch-professional", "310.30.42.50.01.001",
     "omega", "seamaster-diver-300m", "210.30.42.20.01.001"),
    ("tudor", "black-bay-58", "79030N", "tudor", "black-bay", "79230N"),
    ("rolex", "datejust", "126200", "rolex", "datejust", "126300"),
    ("seiko", "prospex", "SPB143", "seiko", "prospex", "SPB185"),
    ("rolex", "submariner", "124060", "rolex", "gmt-master-ii", "126710BLRO"),
]


def generate_compare_list(watches, watch_index):
    """Return list of (watch1, watch2, slug) tuples."""
    comparisons = []
    seen_slugs = set()

    def add_pair(w1, w2):
        if w1 is None or w2 is None:
            return
        if w1["reference"] == w2["reference"] and w1["brand_slug"] == w2["brand_slug"]:
            return
        s = compare_slug(w1, w2)
        if s in seen_slugs:
            return
        seen_slugs.add(s)
        comparisons.append((w1, w2, s))

    def find_watch(brand_slug, coll_slug, reference):
        key = (brand_slug, coll_slug, ref_slug(reference))
        return watch_index.get(key)

    # Priority comparisons
    for item in PRIORITY_COMPARISONS:
        w1 = find_watch(item[0], item[1], item[2])
        w2 = find_watch(item[3], item[4], item[5])
        add_pair(w1, w2)

    # Within-collection comparisons (collections with <= 8 watches)
    colls = build_collections(watches)
    for key, coll_watches in colls.items():
        if len(coll_watches) <= 8:
            for wa, wb in combinations(coll_watches, 2):
                add_pair(wa, wb)

    # Cross-brand matchups based on similar diameter (within 2 mm)
    # Pick representative watches per collection (first of each)
    reps = {}
    for key, coll_watches in colls.items():
        reps[key] = coll_watches[0]

    rep_list = list(reps.values())
    for i, w1 in enumerate(rep_list):
        for w2 in rep_list[i + 1:]:
            if w1["brand_slug"] == w2["brand_slug"]:
                continue
            d1 = safe_float(w1.get("dimensions", {}).get("diameter_mm"))
            d2 = safe_float(w2.get("dimensions", {}).get("diameter_mm"))
            if d1 and d2 and abs(d1 - d2) <= 2:
                add_pair(w1, w2)
                if len(comparisons) >= 65:
                    break
        if len(comparisons) >= 65:
            break

    return comparisons


def compare_slug(w1, w2):
    b1 = w1["brand_slug"]
    n1 = slugify(w1.get("collection", "")) + "-" + ref_slug(w1["reference"])
    b2 = w2["brand_slug"]
    n2 = slugify(w2.get("collection", "")) + "-" + ref_slug(w2["reference"])
    return f"{b1}-{n1}-vs-{b2}-{n2}"


def compare_verdict(w1, w2):
    """Generate a short verdict paragraph."""
    d1 = w1.get("dimensions", {})
    d2 = w2.get("dimensions", {})
    dia1 = safe_float(d1.get("diameter_mm"))
    dia2 = safe_float(d2.get("diameter_mm"))
    l2l1 = safe_float(d1.get("lug_to_lug_mm"))
    l2l2 = safe_float(d2.get("lug_to_lug_mm"))
    t1 = safe_float(d1.get("thickness_mm"))
    t2 = safe_float(d2.get("thickness_mm"))
    name1 = f'{w1["brand"]} {w1.get("name", w1["reference"])}'
    name2 = f'{w2["brand"]} {w2.get("name", w2["reference"])}'

    parts = []
    if dia1 and dia2:
        diff = abs(dia1 - dia2)
        if diff < 0.5:
            parts.append(f"Both watches share a very similar {dia1:.1f} mm diameter, so they will wear nearly identically on the wrist in terms of width.")
        elif dia1 > dia2:
            parts.append(f"The {name1} is {diff:.1f} mm wider at {dia1:.1f} mm versus {dia2:.1f} mm, giving it a slightly larger wrist presence.")
        else:
            parts.append(f"The {name2} is {diff:.1f} mm wider at {dia2:.1f} mm versus {dia1:.1f} mm, giving it a slightly larger wrist presence.")

    if l2l1 and l2l2:
        diff = abs(l2l1 - l2l2)
        if diff >= 1:
            shorter = name1 if l2l1 < l2l2 else name2
            parts.append(f"The {shorter} has a shorter lug-to-lug distance, making it better suited for smaller wrists.")

    if t1 and t2:
        diff = abs(t1 - t2)
        if diff >= 1:
            thinner = name1 if t1 < t2 else name2
            parts.append(f"The {thinner} wears thinner at {min(t1, t2):.1f} mm versus {max(t1, t2):.1f} mm, sitting closer to the wrist.")

    p1 = safe_float(w1.get("context", {}).get("msrp_usd"))
    p2 = safe_float(w2.get("context", {}).get("msrp_usd"))
    if p1 and p2 and abs(p1 - p2) > 500:
        cheaper = name1 if p1 < p2 else name2
        parts.append(f"At retail, the {cheaper} is the more accessible option at {fmt_usd(min(p1, p2))} versus {fmt_usd(max(p1, p2))}.")

    if not parts:
        parts.append(f"Both the {name1} and {name2} are excellent choices with comparable dimensions.")

    return " ".join(parts)


# ---------------------------------------------------------------------------
# Guide definitions
# ---------------------------------------------------------------------------

GUIDES = [
    {
        "slug": "watches-under-40mm",
        "title": "Best Watches Under 40mm for Small Wrists",
        "meta_title": "Best Watches Under 40mm (2026) | Compact Luxury Watches | DialSize",
        "meta_desc": "Complete guide to the best watches under 40mm diameter. Perfect for smaller wrists or those who prefer compact timepieces.",
        "filter": lambda w: safe_float(w.get("dimensions", {}).get("diameter_mm")) > 0 and safe_float(w.get("dimensions", {}).get("diameter_mm")) < 40,
        "intro": "Not everyone wants a dinner-plate on their wrist. Watches under 40 mm wear elegantly on slimmer wrists and look proportionally balanced on just about anyone. This guide covers every watch in our database that comes in under that threshold, from luxury Swiss pieces to affordable Japanese movements.",
        "content": "<h2>Why Choose a Watch Under 40mm?</h2><p>The trend toward ever-larger watches peaked in the early 2010s and has been reversing since. Many brands now recognize that 36-39 mm is the sweet spot for versatility. A sub-40 mm watch slips under a shirt cuff, looks refined at formal events, and is comfortable for all-day wear.</p><h2>What to Look For</h2><p>When shopping for a smaller watch, pay attention to these dimensions:</p><ul><li><strong>Lug-to-lug distance:</strong> More important than diameter for on-wrist fit. Under 46 mm is ideal for wrists under 6.5 inches.</li><li><strong>Thickness:</strong> A compact diameter paired with a thick case can look awkward. Under 12 mm is ideal.</li><li><strong>Lug width:</strong> Smaller watches typically use 18-20 mm straps, which are widely available.</li></ul><h2>Our Picks</h2><p>Below you will find every watch in our database under 40 mm, sorted by diameter. Use the table headers to re-sort by any column.</p>",
    },
    {
        "slug": "thinnest-dive-watches",
        "title": "Thinnest Dive Watches",
        "meta_title": "Thinnest Dive Watches (2026) | Slim Divers That Wear Like Dress Watches | DialSize",
        "meta_desc": "Find the thinnest dive watches with at least 200m water resistance. Slim enough for daily wear without sacrificing capability.",
        "filter": lambda w: safe_float(w.get("case", {}).get("water_resistance_m")) >= 200 and safe_float(w.get("dimensions", {}).get("thickness_mm")) > 0,
        "sort_key": lambda w: safe_float(w.get("dimensions", {}).get("thickness_mm"), 99),
        "intro": "A thick dive watch is one of the main reasons people leave their diver in the drawer. These models deliver at least 200 m of water resistance while keeping the case profile as slim as possible.",
        "content": "<h2>Why Thickness Matters for Dive Watches</h2><p>Traditional dive watches were built like tanks — 14-16 mm thick. Modern materials and engineering have brought that number down considerably. A thinner diver sits closer to the wrist, slides under shirt cuffs, and is more comfortable during all-day wear.</p><h2>How We Measured</h2><p>We include only watches with at least 200 m (20 ATM) water resistance, sorted by case thickness from thinnest to thickest. All measurements are manufacturer-stated specifications.</p><h2>The Data</h2><p>Below are all qualifying dive watches, sorted from thinnest to thickest. Some may surprise you — the difference between brands is significant.</p>",
    },
    {
        "slug": "watches-with-20mm-lug-width",
        "title": "Watches with 20mm Lug Width",
        "meta_title": "All Watches with 20mm Lug Width (2026) | Strap Compatibility Guide | DialSize",
        "meta_desc": "Every watch with 20mm lug width in our database. The most common strap size — find compatible watches and strap options.",
        "filter": lambda w: safe_int(w.get("dimensions", {}).get("lug_width_mm")) == 20,
        "intro": "20 mm is the most popular lug width in the watch industry. If you have a favorite 20 mm strap or bracelet, these are all the watches it will fit.",
        "content": "<h2>Why 20mm is the Universal Standard</h2><p>The 20 mm lug width has become the de facto standard for mid-sized watches (38-42 mm). Virtually every strap maker offers their best designs in 20 mm, giving you the widest selection of rubber, leather, NATO, and metal bracelet options.</p><h2>Strap Options</h2><ul><li><strong>NATO/ZULU straps:</strong> Available from dozens of makers. Great for casual and sport use.</li><li><strong>Rubber straps:</strong> Popular aftermarket options from Barton, Crafter Blue, and others.</li><li><strong>Leather straps:</strong> Widest selection available in 20 mm from brands like Hirsch, Di-Modell, and Delugs.</li><li><strong>Metal bracelets:</strong> Aftermarket options from Strapcode, Uncle Seiko, and more.</li></ul>",
    },
    {
        "slug": "watches-under-47mm-lug-to-lug",
        "title": "Watches Under 47mm Lug-to-Lug",
        "meta_title": "Watches Under 47mm Lug-to-Lug (2026) | Best for Small Wrists | DialSize",
        "meta_desc": "Every watch under 47mm lug-to-lug in our database. The most wrist-friendly dimension for compact proportions.",
        "filter": lambda w: safe_float(w.get("dimensions", {}).get("lug_to_lug_mm")) > 0 and safe_float(w.get("dimensions", {}).get("lug_to_lug_mm")) < 47,
        "intro": "Lug-to-lug distance is the single most important dimension for wrist fit. Watches under 47 mm lug-to-lug will sit comfortably on wrists as small as 6 inches (15 cm) without overhanging.",
        "content": "<h2>Why Lug-to-Lug Matters More Than Diameter</h2><p>A 42 mm watch with 46 mm lug-to-lug can wear smaller than a 38 mm watch with 49 mm lugs. The lug-to-lug measurement determines whether the watch \"bridges\" past the edges of your wrist — and that is the primary visual cue for whether a watch is too large.</p><h2>The Rule of Thumb</h2><p>Your lug-to-lug distance should ideally be less than the width of your wrist (measured across the top). For a 6-inch wrist, that is roughly 50 mm; for 6.5 inches, about 53 mm. Going under 47 mm gives comfortable margin for most people.</p>",
    },
    {
        "slug": "thinnest-automatic-watches",
        "title": "Thinnest Automatic Watches",
        "meta_title": "Thinnest Automatic Watches (2026) | Ultra-Slim Mechanical Watches | DialSize",
        "meta_desc": "The thinnest automatic and mechanical watches available. Sorted by case thickness for slim wrist presence.",
        "filter": lambda w: (w.get("movement", {}).get("type") or "").lower() in ("automatic", "manual") and safe_float(w.get("dimensions", {}).get("thickness_mm")) > 0,
        "sort_key": lambda w: safe_float(w.get("dimensions", {}).get("thickness_mm"), 99),
        "intro": "Thin watches are the hallmark of refined horology. These automatic and manual-wind watches represent the slimmest mechanical options in our database.",
        "content": "<h2>Engineering Thinness</h2><p>Getting an automatic movement thin requires ingenious engineering. Micro-rotors, peripheral rotors, and ultra-flat mainsprings all contribute. Every tenth of a millimeter matters when the goal is a watch that practically disappears on the wrist.</p><h2>What to Expect</h2><p>Under 10 mm: dress-watch territory. 10-12 mm: versatile daily wearer. Over 12 mm: sport/tool watch proportions. The watches below are sorted from thinnest to thickest.</p>",
    },
    {
        "slug": "lightest-titanium-watches",
        "title": "Lightest Titanium Watches",
        "meta_title": "Lightest Titanium Watches (2026) | Featherweight Timepieces | DialSize",
        "meta_desc": "The lightest watches in our database, focusing on titanium and lightweight materials. Comfortable all-day wear.",
        "filter": lambda w: "titanium" in (w.get("case", {}).get("material") or "").lower() or (safe_float(w.get("dimensions", {}).get("weight_bracelet_g")) > 0 and safe_float(w.get("dimensions", {}).get("weight_bracelet_g")) < 80) or "resin" in (w.get("case", {}).get("material") or "").lower() or "carbon" in (w.get("case", {}).get("material") or "").lower(),
        "sort_key": lambda w: safe_float(w.get("dimensions", {}).get("weight_bracelet_g"), 999),
        "intro": "For all-day comfort, nothing beats a lightweight watch. Titanium, carbon fiber, and resin cases dramatically reduce wrist fatigue. These are the lightest options in our database.",
        "content": "<h2>Why Weight Matters</h2><p>A heavy watch shifts around on the wrist, digs in during exercise, and can cause fatigue during long wear. Titanium is roughly 40% lighter than stainless steel with comparable strength. Resin and carbon-composite cases are lighter still.</p><h2>Materials Compared</h2><ul><li><strong>Titanium:</strong> 40% lighter than steel, hypoallergenic, corrosion-resistant</li><li><strong>Carbon/Resin:</strong> Ultralight, shock-resistant, budget-friendly (G-Shock)</li><li><strong>Stainless Steel (for reference):</strong> The standard, typically 150-200 g on bracelet</li></ul>",
    },
    {
        "slug": "best-watches-for-small-wrists",
        "title": "Best Watches for Small Wrists (Under 7 Inch)",
        "meta_title": "Best Watches for Small Wrists Under 7\" (2026) | DialSize",
        "meta_desc": "Curated picks for wrists under 7 inches. Focused on lug-to-lug distance, thickness, and overall proportions.",
        "filter": lambda w: safe_float(w.get("dimensions", {}).get("lug_to_lug_mm")) > 0 and safe_float(w.get("dimensions", {}).get("lug_to_lug_mm")) <= 49,
        "intro": "Having a wrist under 7 inches is completely normal — it is roughly the male average. The key is choosing watches with proportions that match, not just a small diameter.",
        "content": "<h2>The Three Numbers That Matter</h2><p>Forget marketing sizes. These three measurements determine how a watch actually wears on a smaller wrist:</p><ol><li><strong>Lug-to-lug distance (most important):</strong> Should be less than your wrist width. Under 49 mm works for most sub-7-inch wrists.</li><li><strong>Thickness:</strong> Under 13 mm is ideal. Thick watches look disproportionate on slimmer wrists.</li><li><strong>Diameter:</strong> 36-41 mm is the sweet spot, but L2L matters more.</li></ol><h2>How We Picked</h2><p>Every watch below has a lug-to-lug distance of 49 mm or less, making them suitable for wrists in the 6-7 inch range.</p>",
    },
    {
        "slug": "watches-40-42mm",
        "title": "Best Watches Between 40-42mm",
        "meta_title": "Best Watches 40-42mm (2026) | The Modern Sweet Spot | DialSize",
        "meta_desc": "All watches between 40-42mm diameter — the modern sweet spot. Large enough for presence, small enough for comfort.",
        "filter": lambda w: safe_float(w.get("dimensions", {}).get("diameter_mm")) >= 40 and safe_float(w.get("dimensions", {}).get("diameter_mm")) <= 42,
        "intro": "The 40-42 mm range is the modern Goldilocks zone. Large enough for a strong wrist presence, small enough to fit most wrists comfortably. This is where the majority of popular sport and dive watches live.",
        "content": "<h2>Why 40-42mm?</h2><p>This range works for wrists from about 6.25 inches to 8 inches — covering the vast majority of wearers. The dial is large enough for easy readability, complications have room to breathe, and the proportions look balanced on most arms.</p><h2>The Most Popular Segment</h2><p>The majority of iconic watch references fall in this range: the Rolex Submariner (41 mm), Omega Speedmaster (42 mm), Tudor Black Bay (41 mm), and Seiko Prospex divers (40.5-42.7 mm). If you are buying your first serious watch, this is likely where you will end up.</p>",
    },
]


# ---------------------------------------------------------------------------
# Jinja2 Templates (inline)
# ---------------------------------------------------------------------------

BASE_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ meta_title }}</title>
<meta name="description" content="{{ meta_desc }}">
<link rel="canonical" href="{{ canonical }}">
<meta property="og:title" content="{{ meta_title }}">
<meta property="og:description" content="{{ meta_desc }}">
<meta property="og:url" content="{{ canonical }}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="DialSize">
<link rel="stylesheet" href="/static/style.css">
<script>
window.dataLayer = window.dataLayer || [];
function gtag(){dataLayer.push(arguments);}
gtag('consent', 'default', {
  'analytics_storage': 'denied',
  'ad_storage': 'denied',
  'ad_user_data': 'denied',
  'ad_personalization': 'denied',
  'wait_for_update': 500,
  'region': ['BE','BG','CZ','DK','DE','EE','IE','GR','ES','FR','HR','IT','CY','LV','LT','LU','HU','MT','NL','AT','PL','PT','RO','SI','SK','FI','SE','GB','CH','IS','LI','NO']
});
gtag('consent', 'default', {
  'analytics_storage': 'granted',
  'ad_storage': 'granted',
  'ad_user_data': 'granted',
  'ad_personalization': 'granted'
});
</script>
<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client={{ adsense_pub }}" crossorigin="anonymous"></script>
<script async src="https://www.googletagmanager.com/gtag/js?id={{ ga_id }}"></script>
<script>
gtag('js', new Date());
gtag('config', '{{ ga_id }}');
</script>
{% block head_extra %}{% endblock %}
</head>
<body>
<header class="site-header">
<div class="container">
<a href="/" class="site-logo">Dial<span>Size</span></a>
<nav class="site-nav">
<a href="/">Home</a>
<a href="/compare/">Compare</a>
<a href="/guides/watches-under-40mm/">Guides</a>
<a href="/about/">About</a>
</nav>
</div>
</header>
{% block body %}{% endblock %}
<footer class="site-footer">
<div class="container">
<div class="footer-grid">
<div class="footer-col">
<h4>Browse</h4>
{% for b in all_brands %}<a href="/{{ b.brand_slug }}/">{{ b.brand }}</a>
{% endfor %}
</div>
<div class="footer-col">
<h4>Guides</h4>
<a href="/guides/watches-under-40mm/">Under 40mm</a>
<a href="/guides/thinnest-dive-watches/">Thinnest Divers</a>
<a href="/guides/best-watches-for-small-wrists/">Small Wrists</a>
<a href="/guides/watches-40-42mm/">40-42mm Watches</a>
</div>
<div class="footer-col">
<h4>Tools</h4>
<a href="/lug-width/20mm/">Lug Width: 20mm</a>
<a href="/lug-width/22mm/">Lug Width: 22mm</a>
<a href="/lug-width/18mm/">Lug Width: 18mm</a>
</div>
<div class="footer-col">
<h4>Info</h4>
<a href="/about/">About DialSize</a>
<a href="/privacy/">Privacy Policy</a>
<a href="/affiliate-disclosure/">Affiliate Disclosure</a>
</div>
</div>
<div class="footer-bottom">
<p>&copy; {{ year }} DialSize.com &mdash; Watch dimensions database. Not affiliated with any watch brand.</p>
<p><a href="/affiliate-disclosure/">Affiliate Disclosure</a> &middot; <a href="/privacy/">Privacy</a></p>
</div>
</div>
</footer>
<script src="/static/search.js"></script>
</body>
</html>"""

HOME_TEMPLATE = r"""{% extends "base.html" %}
{% block body %}
<section class="hero">
<div class="container">
<h1>Every Watch. <span>Every Dimension.</span></h1>
<p>The most comprehensive watch dimensions database. Compare sizes, check wrist fit, and find your perfect watch.</p>
<div class="search-wrap">
<span class="search-icon">&#128269;</span>
<input type="search" id="ds-search" placeholder="Search by brand, model, or reference..." autocomplete="off">
<div id="ds-search-results" class="search-results"></div>
</div>
</div>
</section>
<section>
<div class="container">
<div class="stats-grid">
<div class="stat-box"><div class="stat-num">{{ total_watches }}</div><div class="stat-label">Watches</div></div>
<div class="stat-box"><div class="stat-num">{{ total_brands }}</div><div class="stat-label">Brands</div></div>
<div class="stat-box"><div class="stat-num">{{ total_collections }}</div><div class="stat-label">Collections</div></div>
<div class="stat-box"><div class="stat-num">{{ total_references }}</div><div class="stat-label">References</div></div>
</div>
</div>
</section>
<section>
<div class="container">
<h2 class="section-title">Browse by <span>Brand</span></h2>
<div class="brand-grid">
{% for b in all_brands %}
<a href="/{{ b.brand_slug }}/" class="brand-card">
<div class="brand-initial">{{ b.brand[0] }}</div>
<div class="brand-info">
<h3>{{ b.brand }}</h3>
<p>{{ b.watch_count }} watches</p>
</div>
</a>
{% endfor %}
</div>
</div>
</section>
<section>
<div class="container">
<h2 class="section-title">Browse by <span>Size</span></h2>
<div class="size-grid">
{% for cat in size_categories %}
<a href="/guides/{{ cat.slug }}/" class="size-card">
<div class="size-range">{{ cat.range }}</div>
<div class="size-label">{{ cat.label }}</div>
</a>
{% endfor %}
</div>
</div>
</section>
<section>
<div class="container">
<h2 class="section-title">Popular <span>Comparisons</span></h2>
<div class="card-grid">
{% for c in popular_comparisons[:8] %}
<div class="card">
<h3><a href="/compare/{{ c.slug }}/">{{ c.w1_name }} vs {{ c.w2_name }}</a></h3>
<p>{{ c.w1_dia }} mm vs {{ c.w2_dia }} mm diameter</p>
</div>
{% endfor %}
</div>
</div>
</section>
<section>
<div class="container">
<h2 class="section-title">Latest <span>Additions</span></h2>
<div class="card-grid">
{% for w in latest[:8] %}
<div class="card">
<h3><a href="/{{ w.brand_slug }}/{{ w.collection_slug }}/{{ w.ref_slug }}/">{{ w.brand }} {{ w.name }}</a></h3>
<p>{{ w.dims }}</p>
<div class="card-meta">Ref. {{ w.reference }}</div>
</div>
{% endfor %}
</div>
</div>
</section>
{% endblock %}
{% block head_extra %}
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"WebSite","name":"DialSize","url":"https://dialsize.com/","description":"Comprehensive watch dimensions database. Compare sizes, check wrist fit, and find your perfect watch.","potentialAction":{"@type":"SearchAction","target":"https://dialsize.com/?q={search_term_string}","query-input":"required name=search_term_string"}}
</script>
{% endblock %}"""

BRAND_TEMPLATE = r"""{% extends "base.html" %}
{% block body %}
<div class="container">
<div class="breadcrumbs"><a href="/">Home</a> <span>/</span> {{ brand.brand }}</div>
<div class="page-header">
<h1>{{ brand.brand }} Watch Dimensions</h1>
<p class="subtitle">{{ brand.brand_description }}</p>
</div>
</div>
<section>
<div class="container">
<div class="stats-grid">
<div class="stat-box"><div class="stat-num">{{ collections|length }}</div><div class="stat-label">Collections</div></div>
<div class="stat-box"><div class="stat-num">{{ watches|length }}</div><div class="stat-label">References</div></div>
<div class="stat-box"><div class="stat-num">{{ dia_range }}</div><div class="stat-label">Diameter Range</div></div>
</div>
<h2 class="section-title">Collections</h2>
<div class="card-grid">
{% for c in collections %}
<div class="card">
<h3><a href="/{{ brand.brand_slug }}/{{ c.slug }}/">{{ c.name }}</a></h3>
<p>{{ c.count }} reference{{ 's' if c.count != 1 else '' }}</p>
<div class="card-meta">{{ c.dia_range }}</div>
</div>
{% endfor %}
</div>
</div>
</section>
<section>
<div class="container">
<h2 class="section-title">All {{ brand.brand }} <span>Watches</span></h2>
<div class="table-wrap">
<table class="specs-table" id="brand-table">
<thead>
<tr>
<th class="sortable">Collection</th>
<th class="sortable">Reference</th>
<th class="sortable">Name</th>
<th class="sortable">Diameter</th>
<th class="sortable">L2L</th>
<th class="sortable">Thickness</th>
<th class="sortable">Lug Width</th>
</tr>
</thead>
<tbody>
{% for w in watches %}
<tr>
<td>{{ w.collection }}</td>
<td class="mono"><a href="/{{ w.brand_slug }}/{{ w.collection_slug }}/{{ w.ref_slug }}/">{{ w.reference }}</a></td>
<td>{{ w.name }}</td>
<td class="mono">{{ w.diameter }}</td>
<td class="mono">{{ w.lug_to_lug }}</td>
<td class="mono">{{ w.thickness }}</td>
<td class="mono">{{ w.lug_width }}</td>
</tr>
{% endfor %}
</tbody>
</table>
</div>
</div>
</section>
{% endblock %}
{% block head_extra %}
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"BreadcrumbList","itemListElement":[{"@type":"ListItem","position":1,"name":"Home","item":"https://dialsize.com/"},{"@type":"ListItem","position":2,"name":"{{ brand.brand }}","item":"https://dialsize.com/{{ brand.brand_slug }}/"}]}
</script>
{% endblock %}"""

COLLECTION_TEMPLATE = r"""{% extends "base.html" %}
{% block body %}
<div class="container">
<div class="breadcrumbs"><a href="/">Home</a> <span>/</span> <a href="/{{ brand_slug }}/">{{ brand }}</a> <span>/</span> {{ collection }}</div>
<div class="page-header">
<h1>{{ brand }} {{ collection }} Dimensions</h1>
<p class="subtitle">{{ watch_count }} reference{{ 's' if watch_count != 1 else '' }} &mdash; {{ dia_range }} diameter</p>
</div>
</div>
<section>
<div class="container">
<div class="stats-grid">
<div class="stat-box"><div class="stat-num">{{ watch_count }}</div><div class="stat-label">References</div></div>
<div class="stat-box"><div class="stat-num">{{ dia_min }}</div><div class="stat-label">Min Diameter</div></div>
<div class="stat-box"><div class="stat-num">{{ dia_max }}</div><div class="stat-label">Max Diameter</div></div>
<div class="stat-box"><div class="stat-num">{{ thickness_range }}</div><div class="stat-label">Thickness Range</div></div>
</div>
<div class="table-wrap">
<table class="specs-table" id="coll-table">
<thead>
<tr>
<th class="sortable">Reference</th>
<th class="sortable">Name</th>
<th class="sortable">Diameter</th>
<th class="sortable">L2L</th>
<th class="sortable">Thickness</th>
<th class="sortable">Lug Width</th>
<th class="sortable">Material</th>
<th class="sortable">WR</th>
</tr>
</thead>
<tbody>
{% for w in watches %}
<tr>
<td class="mono"><a href="/{{ brand_slug }}/{{ coll_slug }}/{{ w.ref_slug }}/">{{ w.reference }}</a></td>
<td>{{ w.name }}</td>
<td class="mono">{{ w.diameter }}</td>
<td class="mono">{{ w.lug_to_lug }}</td>
<td class="mono">{{ w.thickness }}</td>
<td class="mono">{{ w.lug_width }}</td>
<td>{{ w.material }}</td>
<td class="mono">{{ w.wr }}</td>
</tr>
{% endfor %}
</tbody>
</table>
</div>
</div>
</section>
{% endblock %}
{% block head_extra %}
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"BreadcrumbList","itemListElement":[{"@type":"ListItem","position":1,"name":"Home","item":"https://dialsize.com/"},{"@type":"ListItem","position":2,"name":"{{ brand }}","item":"https://dialsize.com/{{ brand_slug }}/"},{"@type":"ListItem","position":3,"name":"{{ collection }}","item":"https://dialsize.com/{{ brand_slug }}/{{ coll_slug }}/"}]}
</script>
{% endblock %}"""

REFERENCE_TEMPLATE = r"""{% extends "base.html" %}
{% block body %}
<div class="container">
<div class="breadcrumbs"><a href="/">Home</a> <span>/</span> <a href="/{{ w.brand_slug }}/">{{ w.brand }}</a> <span>/</span> <a href="/{{ w.brand_slug }}/{{ w.collection_slug }}/">{{ w.collection }}</a> <span>/</span> {{ w.reference }}</div>
<div class="page-header">
<h1>{{ w.brand }} {{ w.name }} ({{ w.reference }}) Dimensions</h1>
<p class="subtitle">{{ w.collection }} &mdash; Complete specifications and wrist fit guide</p>
</div>
</div>
<section>
<div class="container">
<h2 class="section-title">Dimensions</h2>
<div class="spec-grid">
<div class="spec-row"><div class="spec-label">Diameter</div><div class="spec-value">{{ dims.diameter }}</div></div>
<div class="spec-row"><div class="spec-label">Lug-to-Lug</div><div class="spec-value">{{ dims.lug_to_lug }}</div></div>
<div class="spec-row"><div class="spec-label">Thickness</div><div class="spec-value">{{ dims.thickness }}</div></div>
<div class="spec-row"><div class="spec-label">Lug Width</div><div class="spec-value">{{ dims.lug_width }}</div></div>
{% if dims.weight_bracelet %}<div class="spec-row"><div class="spec-label">Weight (on bracelet)</div><div class="spec-value">{{ dims.weight_bracelet }}</div></div>{% endif %}
{% if dims.weight_head %}<div class="spec-row"><div class="spec-label">Weight (head only)</div><div class="spec-value">{{ dims.weight_head }}</div></div>{% endif %}
</div>
</div>
</section>
<section>
<div class="container">
<h2 class="section-title">Dimension <span>Diagram</span></h2>
<div class="diagram-wrap">
{{ svg_diagram }}
</div>
</div>
</section>
<section>
<div class="container">
<h2 class="section-title">Case</h2>
<div class="spec-grid">
<div class="spec-row"><div class="spec-label">Material</div><div class="spec-value">{{ case.material }}</div></div>
<div class="spec-row"><div class="spec-label">Crystal</div><div class="spec-value">{{ case.crystal }}</div></div>
<div class="spec-row"><div class="spec-label">Water Resistance</div><div class="spec-value">{{ case.wr }}</div></div>
{% if case.bezel %}<div class="spec-row"><div class="spec-label">Bezel</div><div class="spec-value">{{ case.bezel }}</div></div>{% endif %}
{% if case.crown %}<div class="spec-row"><div class="spec-label">Crown</div><div class="spec-value">{{ case.crown }}</div></div>{% endif %}
{% if case.caseback %}<div class="spec-row"><div class="spec-label">Caseback</div><div class="spec-value">{{ case.caseback }}</div></div>{% endif %}
{% if case.dial_color %}<div class="spec-row"><div class="spec-label">Dial Color</div><div class="spec-value">{{ case.dial_color }}</div></div>{% endif %}
</div>
</div>
</section>
<section>
<div class="container">
<h2 class="section-title">Movement</h2>
<div class="spec-grid">
{% if movement.caliber %}<div class="spec-row"><div class="spec-label">Caliber</div><div class="spec-value">{{ movement.caliber }}</div></div>{% endif %}
{% if movement.type %}<div class="spec-row"><div class="spec-label">Type</div><div class="spec-value">{{ movement.type }}</div></div>{% endif %}
{% if movement.power_reserve %}<div class="spec-row"><div class="spec-label">Power Reserve</div><div class="spec-value">{{ movement.power_reserve }}</div></div>{% endif %}
{% if movement.frequency %}<div class="spec-row"><div class="spec-label">Frequency</div><div class="spec-value">{{ movement.frequency }}</div></div>{% endif %}
</div>
</div>
</section>
{% if context.msrp or context.production %}
<section>
<div class="container">
<h2 class="section-title">Context</h2>
<div class="spec-grid">
{% if context.msrp %}<div class="spec-row"><div class="spec-label">MSRP</div><div class="spec-value">{{ context.msrp }}</div></div>{% endif %}
{% if context.production %}<div class="spec-row"><div class="spec-label">Production</div><div class="spec-value">{{ context.production }}</div></div>{% endif %}
{% if context.predecessor %}<div class="spec-row"><div class="spec-label">Predecessor</div><div class="spec-value">{{ context.predecessor }}</div></div>{% endif %}
{% if context.successor %}<div class="spec-row"><div class="spec-label">Successor</div><div class="spec-value">{{ context.successor }}</div></div>{% endif %}
</div>
</div>
</section>
{% endif %}
<section>
<div class="container">
<div class="wrist-fit">
<h3>Wrist Fit Guide</h3>
{% if wrist_fit_data %}
<p>With a lug-to-lug distance of {{ dims.lug_to_lug }}, the {{ w.brand }} {{ w.name }} fits wrists {{ wrist_fit_data[0] }} ({{ wrist_fit_data[1] }}) and larger comfortably.</p>
{% endif %}
{% if similar_l2l %}
<p style="margin-top:.5rem"><strong>Wears similar to:</strong> {% for s in similar_l2l %}{{ s.brand }} {{ s.name }} ({{ s.reference }}){{ ', ' if not loop.last else '' }}{% endfor %}</p>
{% endif %}
</div>
</div>
</section>
<section>
<div class="container">
<h2 class="section-title">Where to <span>Buy</span></h2>
<div class="buy-links">
<a href="{{ affiliate.ebay }}" class="buy-link" rel="sponsored nofollow noopener" target="_blank">eBay</a>
<a href="{{ affiliate.chrono24 }}" class="buy-link secondary" rel="sponsored nofollow noopener" target="_blank">Chrono24</a>
<a href="{{ affiliate.jomashop }}" class="buy-link secondary" rel="sponsored nofollow noopener" target="_blank">Jomashop</a>
<a href="{{ affiliate.amazon }}" class="buy-link secondary" rel="sponsored nofollow noopener" target="_blank">Amazon</a>
</div>
<p class="affiliate-note">Links may be affiliate links. See our <a href="/affiliate-disclosure/">affiliate disclosure</a>.</p>
</div>
</section>
{% if related %}
<section>
<div class="container">
<h2 class="section-title">Related <span>Watches</span></h2>
<div class="related-grid">
{% for r in related[:6] %}
<div class="card">
<h3><a href="/{{ r.brand_slug }}/{{ r.collection_slug }}/{{ r.ref_slug }}/">{{ r.brand }} {{ r.name }}</a></h3>
<p>{{ r.dims }}</p>
<div class="card-meta">Ref. {{ r.reference }}</div>
</div>
{% endfor %}
</div>
</div>
</section>
{% endif %}
{% if compare_links %}
<section>
<div class="container">
<h2 class="section-title">Compare</h2>
<div class="card-grid">
{% for cl in compare_links[:4] %}
<div class="card">
<h3><a href="/compare/{{ cl.slug }}/">vs {{ cl.other_name }}</a></h3>
<p>{{ cl.other_dims }}</p>
</div>
{% endfor %}
</div>
</div>
</section>
{% endif %}
{% endblock %}
{% block head_extra %}
<script type="application/ld+json">
{{ schema_product }}
</script>
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"BreadcrumbList","itemListElement":[{"@type":"ListItem","position":1,"name":"Home","item":"https://dialsize.com/"},{"@type":"ListItem","position":2,"name":"{{ w.brand }}","item":"https://dialsize.com/{{ w.brand_slug }}/"},{"@type":"ListItem","position":3,"name":"{{ w.collection }}","item":"https://dialsize.com/{{ w.brand_slug }}/{{ w.collection_slug }}/"},{"@type":"ListItem","position":4,"name":"{{ w.reference }}","item":"{{ canonical }}"}]}
</script>
{% endblock %}"""

COMPARE_TEMPLATE = r"""{% extends "base.html" %}
{% block body %}
<div class="container">
<div class="breadcrumbs"><a href="/">Home</a> <span>/</span> <a href="/compare/">Compare</a> <span>/</span> {{ w1.brand }} {{ w1.name }} vs {{ w2.brand }} {{ w2.name }}</div>
<div class="page-header">
<h1>{{ w1.brand }} {{ w1.name }} vs {{ w2.brand }} {{ w2.name }}</h1>
<p class="subtitle">Side-by-side dimension comparison — Ref. {{ w1.reference }} vs {{ w2.reference }}</p>
</div>
</div>
<section>
<div class="container">
<div class="diagram-wrap">
{{ compare_svg }}
</div>
</div>
</section>
<section>
<div class="container">
<h2 class="section-title">Dimensions <span>Compared</span></h2>
<div class="table-wrap">
<table class="specs-table compare-table">
<thead><tr><th>Spec</th><th>{{ w1.brand }} {{ w1.name }}</th><th>{{ w2.brand }} {{ w2.name }}</th></tr></thead>
<tbody>
{% for row in spec_rows %}
<tr{% if row.diff %} class="highlight"{% endif %}>
<td>{{ row.label }}</td>
<td class="mono{% if row.w1_wins %} winner{% endif %}">{{ row.v1 }}</td>
<td class="mono{% if row.w2_wins %} winner{% endif %}">{{ row.v2 }}</td>
</tr>
{% endfor %}
</tbody>
</table>
</div>
</div>
</section>
<section>
<div class="container">
<h2 class="section-title">Verdict</h2>
<p>{{ verdict }}</p>
</div>
</section>
<section>
<div class="container">
<h2 class="section-title">Where to <span>Buy</span></h2>
<div class="compare-grid">
<div class="compare-col">
<h3>{{ w1.brand }} {{ w1.name }}</h3>
<div class="buy-links" style="justify-content:center">
<a href="{{ aff1.ebay }}" class="buy-link" rel="sponsored nofollow noopener" target="_blank">eBay</a>
<a href="{{ aff1.chrono24 }}" class="buy-link secondary" rel="sponsored nofollow noopener" target="_blank">Chrono24</a>
</div>
</div>
<div class="compare-col">
<h3>{{ w2.brand }} {{ w2.name }}</h3>
<div class="buy-links" style="justify-content:center">
<a href="{{ aff2.ebay }}" class="buy-link" rel="sponsored nofollow noopener" target="_blank">eBay</a>
<a href="{{ aff2.chrono24 }}" class="buy-link secondary" rel="sponsored nofollow noopener" target="_blank">Chrono24</a>
</div>
</div>
</div>
<p class="affiliate-note">Links may be affiliate links. See our <a href="/affiliate-disclosure/">affiliate disclosure</a>.</p>
</div>
</section>
{% endblock %}
{% block head_extra %}
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"BreadcrumbList","itemListElement":[{"@type":"ListItem","position":1,"name":"Home","item":"https://dialsize.com/"},{"@type":"ListItem","position":2,"name":"Compare","item":"https://dialsize.com/compare/"},{"@type":"ListItem","position":3,"name":"{{ w1.brand }} {{ w1.name }} vs {{ w2.brand }} {{ w2.name }}","item":"{{ canonical }}"}]}
</script>
{% endblock %}"""

COMPARE_INDEX_TEMPLATE = r"""{% extends "base.html" %}
{% block body %}
<div class="container">
<div class="breadcrumbs"><a href="/">Home</a> <span>/</span> Compare</div>
<div class="page-header">
<h1>Watch Size Comparisons</h1>
<p class="subtitle">{{ total }} side-by-side dimension comparisons across {{ brand_count }} brands</p>
</div>
</div>
<section>
<div class="container">
<div class="stats-grid">
<div class="stat-box"><div class="stat-num">{{ total }}</div><div class="stat-label">Comparisons</div></div>
<div class="stat-box"><div class="stat-num">{{ brand_count }}</div><div class="stat-label">Brands</div></div>
</div>
</div>
</section>
{% for group in groups %}
<section>
<div class="container">
<h2 class="section-title">{{ group.title }}</h2>
<div class="card-grid">
{% for c in group.comparisons %}
<div class="card">
<h3><a href="/compare/{{ c.slug }}/">{{ c.w1_name }} vs {{ c.w2_name }}</a></h3>
<p>{{ c.w1_dia }} mm vs {{ c.w2_dia }} mm diameter</p>
</div>
{% endfor %}
</div>
</div>
</section>
{% endfor %}
{% endblock %}
{% block head_extra %}
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"CollectionPage","name":"Watch Size Comparisons","description":"{{ meta_desc }}","url":"{{ canonical }}","isPartOf":{"@type":"WebSite","name":"DialSize","url":"https://dialsize.com/"}}
</script>
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"BreadcrumbList","itemListElement":[{"@type":"ListItem","position":1,"name":"Home","item":"https://dialsize.com/"},{"@type":"ListItem","position":2,"name":"Compare","item":"https://dialsize.com/compare/"}]}
</script>
{% endblock %}"""

LUG_WIDTH_TEMPLATE = r"""{% extends "base.html" %}
{% block body %}
<div class="container">
<div class="breadcrumbs"><a href="/">Home</a> <span>/</span> Lug Width <span>/</span> {{ width }}mm</div>
<div class="page-header">
<div class="lug-width-header">
<h1>Watches with {{ width }}mm Lug Width</h1>
<span class="lug-badge">{{ width }} mm</span>
</div>
<p class="subtitle">{{ watches|length }} watches with {{ width }}mm lug width &mdash; compatible straps and bracelets</p>
</div>
</div>
<section>
<div class="container">
<h2 class="section-title">Strap <span>Compatibility</span></h2>
<p>All {{ watches|length }} watches below accept {{ width }}mm straps. This is {{ popularity }} lug width size. Compatible with most {{ width }}mm NATO straps, leather straps, rubber straps, and aftermarket metal bracelets.</p>
</div>
</section>
<section>
<div class="container">
<h2 class="section-title">All Watches &mdash; <span>{{ width }}mm</span></h2>
<div class="table-wrap">
<table class="specs-table" id="lw-table">
<thead>
<tr>
<th class="sortable">Brand</th>
<th class="sortable">Name</th>
<th class="sortable">Reference</th>
<th class="sortable">Diameter</th>
<th class="sortable">L2L</th>
<th class="sortable">Thickness</th>
</tr>
</thead>
<tbody>
{% for w in watches %}
<tr>
<td>{{ w.brand }}</td>
<td><a href="/{{ w.brand_slug }}/{{ w.collection_slug }}/{{ w.ref_slug }}/">{{ w.name }}</a></td>
<td class="mono">{{ w.reference }}</td>
<td class="mono">{{ w.diameter }}</td>
<td class="mono">{{ w.lug_to_lug }}</td>
<td class="mono">{{ w.thickness }}</td>
</tr>
{% endfor %}
</tbody>
</table>
</div>
</div>
</section>
{% endblock %}
{% block head_extra %}
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"BreadcrumbList","itemListElement":[{"@type":"ListItem","position":1,"name":"Home","item":"https://dialsize.com/"},{"@type":"ListItem","position":2,"name":"Lug Width","item":"https://dialsize.com/lug-width/"},{"@type":"ListItem","position":3,"name":"{{ width }}mm","item":"{{ canonical }}"}]}
</script>
{% endblock %}"""

GUIDE_TEMPLATE = r"""{% extends "base.html" %}
{% block body %}
<div class="container">
<div class="breadcrumbs"><a href="/">Home</a> <span>/</span> Guides <span>/</span> {{ title }}</div>
<div class="page-header">
<h1>{{ title }}</h1>
</div>
</div>
<section>
<div class="container">
<div class="guide-content">
<p>{{ intro }}</p>
{{ content }}
</div>
</div>
</section>
<section>
<div class="container">
<h2 class="section-title">Qualifying <span>Watches</span> ({{ watches|length }})</h2>
<div class="table-wrap">
<table class="specs-table" id="guide-table">
<thead>
<tr>
<th class="sortable">Brand</th>
<th class="sortable">Name</th>
<th class="sortable">Reference</th>
<th class="sortable">Diameter</th>
<th class="sortable">L2L</th>
<th class="sortable">Thickness</th>
<th class="sortable">Lug Width</th>
</tr>
</thead>
<tbody>
{% for w in watches %}
<tr>
<td>{{ w.brand }}</td>
<td><a href="/{{ w.brand_slug }}/{{ w.collection_slug }}/{{ w.ref_slug }}/">{{ w.name }}</a></td>
<td class="mono">{{ w.reference }}</td>
<td class="mono">{{ w.diameter }}</td>
<td class="mono">{{ w.lug_to_lug }}</td>
<td class="mono">{{ w.thickness }}</td>
<td class="mono">{{ w.lug_width }}</td>
</tr>
{% endfor %}
</tbody>
</table>
</div>
</div>
</section>
{% endblock %}
{% block head_extra %}
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"BreadcrumbList","itemListElement":[{"@type":"ListItem","position":1,"name":"Home","item":"https://dialsize.com/"},{"@type":"ListItem","position":2,"name":"Guides","item":"https://dialsize.com/guides/"},{"@type":"ListItem","position":3,"name":"{{ title }}","item":"{{ canonical }}"}]}
</script>
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"FAQPage","mainEntity":[{"@type":"Question","name":"{{ faq_q1 }}","acceptedAnswer":{"@type":"Answer","text":"{{ faq_a1 }}"}},{"@type":"Question","name":"{{ faq_q2 }}","acceptedAnswer":{"@type":"Answer","text":"{{ faq_a2 }}"}}]}
</script>
{% endblock %}"""

STATIC_PAGE_TEMPLATE = r"""{% extends "base.html" %}
{% block body %}
<div class="container">
<div class="breadcrumbs"><a href="/">Home</a> <span>/</span> {{ page_title }}</div>
<div class="page-header">
<h1>{{ page_title }}</h1>
</div>
</div>
<section>
<div class="container">
<div class="guide-content">
{{ page_content }}
</div>
</div>
</section>
{% endblock %}"""

ERROR_TEMPLATE = r"""{% extends "base.html" %}
{% block body %}
<div class="container">
<div class="error-page">
<h1>404</h1>
<p>The watch you are looking for is not in our database — yet.</p>
<p><a href="/" class="buy-link">Back to Homepage</a></p>
</div>
</div>
{% endblock %}"""


# ---------------------------------------------------------------------------
# Rendering engine
# ---------------------------------------------------------------------------

class SiteGenerator:
    def __init__(self):
        self.brands, self.watches = load_all_data()
        self.collections = build_collections(self.watches)
        self.lug_widths = build_lug_width_map(self.watches)
        self.watch_index = build_watch_index(self.watches)
        self.comparisons = generate_compare_list(self.watches, self.watch_index)
        self.all_urls = []
        self.search_index = []
        self.year = datetime.now().year

        self.env = Environment()
        self.env.globals["all_brands"] = self.brands
        self.env.globals["year"] = self.year
        self.env.globals["ga_id"] = GA_ID
        self.env.globals["adsense_pub"] = ADSENSE_PUB

        # Register templates
        self._templates = {
            "base.html": BASE_TEMPLATE,
            "home.html": HOME_TEMPLATE,
            "brand.html": BRAND_TEMPLATE,
            "collection.html": COLLECTION_TEMPLATE,
            "reference.html": REFERENCE_TEMPLATE,
            "compare.html": COMPARE_TEMPLATE,
            "compare_index.html": COMPARE_INDEX_TEMPLATE,
            "lug_width.html": LUG_WIDTH_TEMPLATE,
            "guide.html": GUIDE_TEMPLATE,
            "static_page.html": STATIC_PAGE_TEMPLATE,
            "error.html": ERROR_TEMPLATE,
        }
        self.env.loader = _DictLoader(self._templates)

    def write(self, path, content):
        full = os.path.join(OUT_DIR, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w") as f:
            f.write(content)

    def url(self, path):
        u = SITE_URL + "/" + path.replace("index.html", "")
        if not u.endswith("/"):
            u += "/"
        self.all_urls.append(u)
        return u

    def run(self):
        print("DialSize.com — Static site generator")
        print(f"Loaded {len(self.watches)} watches from {len(self.brands)} brands")

        # Clean output
        if os.path.exists(OUT_DIR):
            try:
                shutil.rmtree(OUT_DIR)
            except PermissionError:
                # On some systems rmtree can fail; remove contents instead
                for root, dirs, files in os.walk(OUT_DIR, topdown=False):
                    for name in files:
                        try:
                            os.remove(os.path.join(root, name))
                        except OSError:
                            pass
                    for name in dirs:
                        try:
                            os.rmdir(os.path.join(root, name))
                        except OSError:
                            pass
        os.makedirs(OUT_DIR, exist_ok=True)

        # Copy static assets
        static_out = os.path.join(OUT_DIR, "static")
        if os.path.exists(STATIC_DIR):
            if os.path.exists(static_out):
                shutil.rmtree(static_out, ignore_errors=True)
            shutil.copytree(STATIC_DIR, static_out, dirs_exist_ok=True)
            print("Copied static/")

        self.gen_homepage()
        self.gen_brand_pages()
        self.gen_collection_pages()
        self.gen_reference_pages()
        self.gen_compare_pages()
        self.gen_compare_index()
        self.gen_lug_width_pages()
        self.gen_guide_pages()
        self.gen_static_pages()
        self.gen_404()
        self.gen_sitemap()
        self.gen_robots()
        self.gen_search_index()
        self.gen_cname()

        print(f"\nDone! Generated {len(self.all_urls)} pages in docs/")

    # -- Homepage --
    def gen_homepage(self):
        print("Generating homepage...")

        total_collections = len(self.collections)
        size_categories = [
            {"slug": "watches-under-40mm", "range": "< 40mm", "label": "Compact"},
            {"slug": "watches-40-42mm", "range": "40-42mm", "label": "Sweet Spot"},
            {"slug": "best-watches-for-small-wrists", "range": "L2L < 49mm", "label": "Small Wrists"},
            {"slug": "thinnest-dive-watches", "range": "Thinnest", "label": "Slim Divers"},
            {"slug": "thinnest-automatic-watches", "range": "Ultra-thin", "label": "Dress Watches"},
            {"slug": "lightest-titanium-watches", "range": "< 80g", "label": "Lightweight"},
        ]

        popular = []
        for w1, w2, slug in self.comparisons[:8]:
            popular.append({
                "slug": slug,
                "w1_name": f"{w1['brand']} {w1.get('name', w1['reference'])}",
                "w2_name": f"{w2['brand']} {w2.get('name', w2['reference'])}",
                "w1_dia": safe_float(w1.get("dimensions", {}).get("diameter_mm")),
                "w2_dia": safe_float(w2.get("dimensions", {}).get("diameter_mm")),
            })

        latest = []
        for w in self.watches[:8]:
            d = w.get("dimensions", {})
            dims = f"{fmt_mm(d.get('diameter_mm'))} / {fmt_mm(d.get('thickness_mm'))} thick"
            latest.append({
                "brand": w["brand"],
                "brand_slug": w["brand_slug"],
                "collection_slug": w.get("collection_slug", ""),
                "ref_slug": ref_slug(w["reference"]),
                "name": w.get("name", w["reference"]),
                "reference": w["reference"],
                "dims": dims,
            })

        canonical = self.url("index.html")
        html = self.env.get_template("home.html").render(
            meta_title="DialSize — Watch Dimensions Database | Every Watch. Every Dimension.",
            meta_desc="The most comprehensive watch dimensions database. Compare watch sizes, check lug-to-lug measurements, thickness, and wrist fit for hundreds of watches.",
            canonical=canonical,
            total_watches=len(self.watches),
            total_brands=len(self.brands),
            total_collections=total_collections,
            total_references=len(self.watches),
            size_categories=size_categories,
            popular_comparisons=popular,
            latest=latest,
        )
        self.write("index.html", html)

    # -- Brand pages --
    def gen_brand_pages(self):
        print("Generating brand pages...")
        for brand in self.brands:
            bs = brand["brand_slug"]
            brand_watches = [w for w in self.watches if w["brand_slug"] == bs]

            # Collections for this brand
            coll_list = []
            coll_keys = sorted(
                {(w.get("collection_slug", ""), w.get("collection", "Other")) for w in brand_watches}
            )
            for cs, cn in coll_keys:
                cw = [w for w in brand_watches if w.get("collection_slug", "") == cs]
                dias = [safe_float(w.get("dimensions", {}).get("diameter_mm")) for w in cw if w.get("dimensions", {}).get("diameter_mm")]
                dr = f"{min(dias):.0f}-{max(dias):.0f} mm" if dias else "N/A"
                coll_list.append({"slug": cs, "name": cn, "count": len(cw), "dia_range": dr})

            # Overall diameter range
            all_dias = [safe_float(w.get("dimensions", {}).get("diameter_mm"))
                        for w in brand_watches if w.get("dimensions", {}).get("diameter_mm")]
            dia_range = f"{min(all_dias):.0f}-{max(all_dias):.0f} mm" if all_dias else "N/A"

            # Table rows
            rows = []
            for w in brand_watches:
                d = w.get("dimensions", {})
                rows.append({
                    "collection": w.get("collection", ""),
                    "collection_slug": w.get("collection_slug", ""),
                    "brand_slug": bs,
                    "reference": w["reference"],
                    "ref_slug": ref_slug(w["reference"]),
                    "name": w.get("name", ""),
                    "diameter": fmt_mm(d.get("diameter_mm")),
                    "lug_to_lug": fmt_mm(d.get("lug_to_lug_mm")),
                    "thickness": fmt_mm(d.get("thickness_mm")),
                    "lug_width": fmt_mm(d.get("lug_width_mm")) if d.get("lug_width_mm") else "N/A",
                })

            canonical = self.url(f"{bs}/index.html")
            html = self.env.get_template("brand.html").render(
                meta_title=f"{brand['brand']} Watch Dimensions & Specs | DialSize",
                meta_desc=f"Complete dimensions for all {brand['brand']} watches. Diameter, lug-to-lug, thickness, and lug width for {len(brand_watches)} references.",
                canonical=canonical,
                brand=brand,
                collections=coll_list,
                watches=rows,
                dia_range=dia_range,
            )
            self.write(f"{bs}/index.html", html)

    # -- Collection pages --
    def gen_collection_pages(self):
        print("Generating collection pages...")
        for (bs, cs), coll_watches in self.collections.items():
            brand_name = coll_watches[0]["brand"]
            coll_name = coll_watches[0].get("collection", "Other")

            dias = [safe_float(w.get("dimensions", {}).get("diameter_mm")) for w in coll_watches if w.get("dimensions", {}).get("diameter_mm")]
            thicks = [safe_float(w.get("dimensions", {}).get("thickness_mm")) for w in coll_watches if w.get("dimensions", {}).get("thickness_mm")]

            rows = []
            for w in coll_watches:
                d = w.get("dimensions", {})
                c = w.get("case", {})
                rows.append({
                    "reference": w["reference"],
                    "ref_slug": ref_slug(w["reference"]),
                    "name": w.get("name", ""),
                    "diameter": fmt_mm(d.get("diameter_mm")),
                    "lug_to_lug": fmt_mm(d.get("lug_to_lug_mm")),
                    "thickness": fmt_mm(d.get("thickness_mm")),
                    "lug_width": fmt_mm(d.get("lug_width_mm")) if d.get("lug_width_mm") else "N/A",
                    "material": c.get("material", "N/A"),
                    "wr": fmt_m(c.get("water_resistance_m")) if c.get("water_resistance_m") else "N/A",
                })

            canonical = self.url(f"{bs}/{cs}/index.html")
            html = self.env.get_template("collection.html").render(
                meta_title=f"{brand_name} {coll_name} Dimensions & Specs | DialSize",
                meta_desc=f"All {brand_name} {coll_name} dimensions compared. {len(coll_watches)} references with diameter, lug-to-lug, and thickness specs.",
                canonical=canonical,
                brand=brand_name,
                brand_slug=bs,
                collection=coll_name,
                coll_slug=cs,
                watches=rows,
                watch_count=len(coll_watches),
                dia_range=f"{min(dias):.1f}-{max(dias):.1f} mm" if dias else "N/A",
                dia_min=f"{min(dias):.1f} mm" if dias else "N/A",
                dia_max=f"{max(dias):.1f} mm" if dias else "N/A",
                thickness_range=f"{min(thicks):.1f}-{max(thicks):.1f} mm" if thicks else "N/A",
            )
            self.write(f"{bs}/{cs}/index.html", html)

    # -- Reference pages --
    def gen_reference_pages(self):
        print("Generating reference pages...")
        # Build comparison lookup
        compare_lookup = defaultdict(list)
        for w1, w2, slug in self.comparisons:
            k1 = (w1["brand_slug"], w1.get("collection_slug", ""), w1["reference"])
            k2 = (w2["brand_slug"], w2.get("collection_slug", ""), w2["reference"])
            compare_lookup[k1].append({"slug": slug, "other": w2})
            compare_lookup[k2].append({"slug": slug, "other": w1})

        for w in self.watches:
            d = w.get("dimensions", {})
            c = w.get("case", {})
            m = w.get("movement", {})
            ctx = w.get("context", {})
            bs = w["brand_slug"]
            cs = w.get("collection_slug", "")
            rs = ref_slug(w["reference"])

            dims = {
                "diameter": fmt_mm(d.get("diameter_mm")),
                "lug_to_lug": fmt_mm(d.get("lug_to_lug_mm")),
                "thickness": fmt_mm(d.get("thickness_mm")),
                "lug_width": fmt_mm(d.get("lug_width_mm")) if d.get("lug_width_mm") else "N/A",
                "weight_bracelet": fmt_g(d.get("weight_bracelet_g")) if d.get("weight_bracelet_g") else None,
                "weight_head": fmt_g(d.get("weight_head_g")) if d.get("weight_head_g") else None,
            }

            case_data = {
                "material": c.get("material", "N/A"),
                "crystal": c.get("crystal", "N/A"),
                "wr": fmt_m(c.get("water_resistance_m")) if c.get("water_resistance_m") else "N/A",
                "bezel": c.get("bezel"),
                "crown": c.get("crown"),
                "caseback": c.get("caseback"),
                "dial_color": c.get("dial_color"),
            }

            movement_data = {
                "caliber": m.get("caliber"),
                "type": m.get("type"),
                "power_reserve": fmt_hours(m.get("power_reserve_hours")) if m.get("power_reserve_hours") else None,
                "frequency": fmt_vph(m.get("frequency_vph")) if m.get("frequency_vph") else None,
            }

            prod_start = ctx.get("production_start")
            prod_end = ctx.get("production_end")
            if prod_start:
                prod = str(prod_start) + (" - present" if not prod_end else f" - {prod_end}")
            else:
                prod = None

            context_data = {
                "msrp": fmt_usd(ctx.get("msrp_usd")) if ctx.get("msrp_usd") else None,
                "production": prod,
                "predecessor": ctx.get("predecessor"),
                "successor": ctx.get("successor"),
            }

            svg = generate_svg(w)
            wf = wrist_fit(d.get("lug_to_lug_mm"))

            # Similar L2L watches
            my_l2l = safe_float(d.get("lug_to_lug_mm"))
            similar = []
            if my_l2l:
                for other in self.watches:
                    if other["reference"] == w["reference"] and other["brand_slug"] == w["brand_slug"]:
                        continue
                    other_l2l = safe_float(other.get("dimensions", {}).get("lug_to_lug_mm"))
                    if other_l2l and abs(my_l2l - other_l2l) <= 1.0:
                        similar.append({
                            "brand": other["brand"],
                            "name": other.get("name", other["reference"]),
                            "reference": other["reference"],
                        })
                    if len(similar) >= 5:
                        break

            # Related: same collection
            related = []
            for other in self.watches:
                if other["reference"] == w["reference"] and other["brand_slug"] == w["brand_slug"]:
                    continue
                if other.get("collection_slug", "") == cs and other["brand_slug"] == bs:
                    od = other.get("dimensions", {})
                    related.append({
                        "brand": other["brand"],
                        "brand_slug": other["brand_slug"],
                        "collection_slug": other.get("collection_slug", ""),
                        "ref_slug": ref_slug(other["reference"]),
                        "name": other.get("name", other["reference"]),
                        "reference": other["reference"],
                        "dims": f"{fmt_mm(od.get('diameter_mm'))} / {fmt_mm(od.get('thickness_mm'))} thick",
                    })
                if len(related) >= 6:
                    break

            # Compare links
            wkey = (bs, cs, w["reference"])
            comp_entries = compare_lookup.get(wkey, [])
            compare_links = []
            for ce in comp_entries:
                o = ce["other"]
                od = o.get("dimensions", {})
                compare_links.append({
                    "slug": ce["slug"],
                    "other_name": f"{o['brand']} {o.get('name', o['reference'])}",
                    "other_dims": f"{fmt_mm(od.get('diameter_mm'))} / {fmt_mm(od.get('thickness_mm'))} thick",
                })

            aff = {
                "ebay": affiliate_ebay(w["brand"], w.get("name", ""), w["reference"]),
                "jomashop": affiliate_jomashop(w["brand"], w.get("name", "")),
                "chrono24": affiliate_chrono24(w["brand"], w["reference"]),
                "amazon": affiliate_amazon(w["brand"], w.get("name", "")),
            }

            # Schema.org Product
            schema = {
                "@context": "https://schema.org",
                "@type": "Product",
                "name": f"{w['brand']} {w.get('name', w['reference'])}",
                "brand": {"@type": "Brand", "name": w["brand"]},
                "description": f"{w['brand']} {w.get('name', w['reference'])} — {fmt_mm(d.get('diameter_mm'))} diameter, {fmt_mm(d.get('thickness_mm'))} thick, {fmt_mm(d.get('lug_to_lug_mm'))} lug-to-lug.",
                "sku": w["reference"],
                "category": "Watches",
            }
            if ctx.get("msrp_usd"):
                schema["offers"] = {
                    "@type": "Offer",
                    "price": ctx["msrp_usd"],
                    "priceCurrency": "USD",
                    "availability": "https://schema.org/InStock",
                }

            canonical = self.url(f"{bs}/{cs}/{rs}/index.html")
            html = self.env.get_template("reference.html").render(
                meta_title=f"{w['brand']} {w.get('name', w['reference'])} ({w['reference']}) Dimensions | DialSize",
                meta_desc=f"{w['brand']} {w.get('name', w['reference'])} dimensions: {fmt_mm(d.get('diameter_mm'))} diameter, {fmt_mm(d.get('lug_to_lug_mm'))} lug-to-lug, {fmt_mm(d.get('thickness_mm'))} thick. Complete specs and wrist fit guide.",
                canonical=canonical,
                w=w,
                dims=dims,
                case=case_data,
                movement=movement_data,
                context=context_data,
                svg_diagram=svg,
                wrist_fit_data=wf,
                similar_l2l=similar,
                related=related,
                compare_links=compare_links,
                affiliate=aff,
                schema_product=json.dumps(schema),
            )
            self.write(f"{bs}/{cs}/{rs}/index.html", html)

            # Search index entry
            self.search_index.append({
                "brand": w["brand"],
                "collection": w.get("collection", ""),
                "name": w.get("name", ""),
                "reference": w["reference"],
                "url": f"/{bs}/{cs}/{rs}/",
            })

    # -- Compare pages --
    def gen_compare_pages(self):
        print(f"Generating {len(self.comparisons)} compare pages...")
        for w1, w2, slug in self.comparisons:
            d1 = w1.get("dimensions", {})
            d2 = w2.get("dimensions", {})
            c1 = w1.get("case", {})
            c2 = w2.get("case", {})
            m1 = w1.get("movement", {})
            m2 = w2.get("movement", {})
            ctx1 = w1.get("context", {})
            ctx2 = w2.get("context", {})

            def spec_row(label, v1, v2, lower_wins=True, numeric=True):
                diff = False
                w1_wins = False
                w2_wins = False
                if numeric and v1 != "N/A" and v2 != "N/A":
                    try:
                        n1 = float(str(v1).replace(" mm", "").replace(" g", "").replace(" m", "")
                                    .replace(" hours", "").replace(",", "").replace(" vph", "")
                                    .replace("$", ""))
                        n2 = float(str(v2).replace(" mm", "").replace(" g", "").replace(" m", "")
                                    .replace(" hours", "").replace(",", "").replace(" vph", "")
                                    .replace("$", ""))
                        if abs(n1 - n2) > 0.01:
                            diff = True
                            if lower_wins:
                                w1_wins = n1 < n2
                                w2_wins = n2 < n1
                            else:
                                w1_wins = n1 > n2
                                w2_wins = n2 > n1
                    except ValueError:
                        pass
                return {"label": label, "v1": v1, "v2": v2, "diff": diff, "w1_wins": w1_wins, "w2_wins": w2_wins}

            rows = [
                spec_row("Diameter", fmt_mm(d1.get("diameter_mm")), fmt_mm(d2.get("diameter_mm")), lower_wins=True),
                spec_row("Lug-to-Lug", fmt_mm(d1.get("lug_to_lug_mm")), fmt_mm(d2.get("lug_to_lug_mm")), lower_wins=True),
                spec_row("Thickness", fmt_mm(d1.get("thickness_mm")), fmt_mm(d2.get("thickness_mm")), lower_wins=True),
                spec_row("Lug Width", fmt_mm(d1.get("lug_width_mm")) if d1.get("lug_width_mm") else "N/A",
                         fmt_mm(d2.get("lug_width_mm")) if d2.get("lug_width_mm") else "N/A", numeric=False),
                spec_row("Weight", fmt_g(d1.get("weight_bracelet_g")) if d1.get("weight_bracelet_g") else "N/A",
                         fmt_g(d2.get("weight_bracelet_g")) if d2.get("weight_bracelet_g") else "N/A", lower_wins=True),
                spec_row("Material", c1.get("material", "N/A"), c2.get("material", "N/A"), numeric=False),
                spec_row("Water Resistance", fmt_m(c1.get("water_resistance_m")) if c1.get("water_resistance_m") else "N/A",
                         fmt_m(c2.get("water_resistance_m")) if c2.get("water_resistance_m") else "N/A", lower_wins=False),
                spec_row("Movement", m1.get("type", "N/A"), m2.get("type", "N/A"), numeric=False),
                spec_row("Power Reserve", fmt_hours(m1.get("power_reserve_hours")) if m1.get("power_reserve_hours") else "N/A",
                         fmt_hours(m2.get("power_reserve_hours")) if m2.get("power_reserve_hours") else "N/A", lower_wins=False),
                spec_row("MSRP", fmt_usd(ctx1.get("msrp_usd")) if ctx1.get("msrp_usd") else "N/A",
                         fmt_usd(ctx2.get("msrp_usd")) if ctx2.get("msrp_usd") else "N/A", lower_wins=True),
            ]

            comp_svg = generate_compare_svg(w1, w2)
            verdict = compare_verdict(w1, w2)

            aff1 = {
                "ebay": affiliate_ebay(w1["brand"], w1.get("name", ""), w1["reference"]),
                "chrono24": affiliate_chrono24(w1["brand"], w1["reference"]),
            }
            aff2 = {
                "ebay": affiliate_ebay(w2["brand"], w2.get("name", ""), w2["reference"]),
                "chrono24": affiliate_chrono24(w2["brand"], w2["reference"]),
            }

            n1 = f"{w1['brand']} {w1.get('name', w1['reference'])}"
            n2 = f"{w2['brand']} {w2.get('name', w2['reference'])}"

            canonical = self.url(f"compare/{slug}/index.html")
            html = self.env.get_template("compare.html").render(
                meta_title=f"{n1} vs {n2} — Size Comparison | DialSize",
                meta_desc=f"Compare {n1} vs {n2} dimensions side by side. Diameter, thickness, lug-to-lug, weight and more.",
                canonical=canonical,
                w1=w1,
                w2=w2,
                spec_rows=rows,
                compare_svg=comp_svg,
                verdict=verdict,
                aff1=aff1,
                aff2=aff2,
            )
            self.write(f"compare/{slug}/index.html", html)

    # -- Compare index page --
    def gen_compare_index(self):
        print("Generating compare index page...")
        # Group comparisons by brand pair
        brand_groups = defaultdict(list)
        all_brands_in_comparisons = set()
        for w1, w2, slug in self.comparisons:
            d1 = w1.get("dimensions", {})
            d2 = w2.get("dimensions", {})
            b1 = w1["brand"]
            b2 = w2["brand"]
            all_brands_in_comparisons.add(b1)
            all_brands_in_comparisons.add(b2)
            if b1 == b2:
                group_key = b1
            else:
                group_key = " vs ".join(sorted([b1, b2]))
            brand_groups[group_key].append({
                "slug": slug,
                "w1_name": f"{b1} {w1.get('name', w1['reference'])}",
                "w2_name": f"{b2} {w2.get('name', w2['reference'])}",
                "w1_dia": f"{safe_float(d1.get('diameter_mm')):.1f}",
                "w2_dia": f"{safe_float(d2.get('diameter_mm')):.1f}",
            })

        # Sort groups: within-brand first (alphabetical), then cross-brand (alphabetical)
        within = sorted([(k, v) for k, v in brand_groups.items() if " vs " not in k])
        cross = sorted([(k, v) for k, v in brand_groups.items() if " vs " in k])
        groups = []
        for key, items in within + cross:
            groups.append({"title": key, "comparisons": items})

        canonical = self.url("compare/index.html")
        html = self.env.get_template("compare_index.html").render(
            meta_title="Watch Size Comparisons — Side-by-Side Dimensions | DialSize",
            meta_desc=f"Compare watch dimensions side by side. {len(self.comparisons)} comparisons across {len(all_brands_in_comparisons)} brands — diameter, lug-to-lug, thickness, and more.",
            canonical=canonical,
            total=len(self.comparisons),
            brand_count=len(all_brands_in_comparisons),
            groups=groups,
        )
        self.write("compare/index.html", html)

    # -- Lug width pages --
    def gen_lug_width_pages(self):
        print("Generating lug width pages...")
        pop_map = {
            18: "a common", 19: "a less common", 20: "the most popular",
            21: "a less common", 22: "a very popular", 24: "a common",
        }
        for width, lw_watches in sorted(self.lug_widths.items()):
            rows = []
            for w in lw_watches:
                d = w.get("dimensions", {})
                rows.append({
                    "brand": w["brand"],
                    "brand_slug": w["brand_slug"],
                    "collection_slug": w.get("collection_slug", ""),
                    "ref_slug": ref_slug(w["reference"]),
                    "name": w.get("name", w["reference"]),
                    "reference": w["reference"],
                    "diameter": fmt_mm(d.get("diameter_mm")),
                    "lug_to_lug": fmt_mm(d.get("lug_to_lug_mm")),
                    "thickness": fmt_mm(d.get("thickness_mm")),
                })

            popularity = pop_map.get(width, "a")

            canonical = self.url(f"lug-width/{width}mm/index.html")
            html = self.env.get_template("lug_width.html").render(
                meta_title=f"Watches with {width}mm Lug Width | DialSize",
                meta_desc=f"All {len(lw_watches)} watches with {width}mm lug width. Find compatible straps and see full specs.",
                canonical=canonical,
                width=width,
                watches=rows,
                popularity=popularity,
            )
            self.write(f"lug-width/{width}mm/index.html", html)

    # -- Guide pages --
    def gen_guide_pages(self):
        print("Generating guide pages...")
        for guide in GUIDES:
            filtered = [w for w in self.watches if guide["filter"](w)]
            sort_fn = guide.get("sort_key")
            if sort_fn:
                filtered.sort(key=sort_fn)
            else:
                filtered.sort(key=lambda w: safe_float(w.get("dimensions", {}).get("diameter_mm"), 99))

            rows = []
            for w in filtered:
                d = w.get("dimensions", {})
                rows.append({
                    "brand": w["brand"],
                    "brand_slug": w["brand_slug"],
                    "collection_slug": w.get("collection_slug", ""),
                    "ref_slug": ref_slug(w["reference"]),
                    "name": w.get("name", w["reference"]),
                    "reference": w["reference"],
                    "diameter": fmt_mm(d.get("diameter_mm")),
                    "lug_to_lug": fmt_mm(d.get("lug_to_lug_mm")),
                    "thickness": fmt_mm(d.get("thickness_mm")),
                    "lug_width": fmt_mm(d.get("lug_width_mm")) if d.get("lug_width_mm") else "N/A",
                })

            # FAQ
            faq_q1 = f"How many watches qualify for '{guide['title']}'?"
            faq_a1 = f"Our database currently lists {len(filtered)} watches that meet the criteria for this guide."
            faq_q2 = f"What is the most important dimension for choosing a watch?"
            faq_a2 = "Lug-to-lug distance is the most important dimension for wrist fit, followed by case thickness. Diameter alone does not tell the full story."

            canonical = self.url(f"guides/{guide['slug']}/index.html")
            html = self.env.get_template("guide.html").render(
                meta_title=guide.get("meta_title", f"{guide['title']} | DialSize"),
                meta_desc=guide.get("meta_desc", ""),
                canonical=canonical,
                title=guide["title"],
                intro=guide["intro"],
                content=guide["content"],
                watches=rows,
                faq_q1=faq_q1,
                faq_a1=faq_a1,
                faq_q2=faq_q2,
                faq_a2=faq_a2,
            )
            self.write(f"guides/{guide['slug']}/index.html", html)

    # -- Static pages --
    def gen_static_pages(self):
        print("Generating static pages...")

        # Privacy
        privacy_content = """<p>Last updated: October 2026</p>
<h2>Information We Collect</h2>
<p>DialSize.com does not require an account and does not ask you for personal information. We use two Google services to understand how the site is used and to fund it through advertising:</p>
<ul>
<li><strong>Google Analytics:</strong> Helps us understand how visitors use the site, such as which pages are viewed, time on site, device type, and general geographic region. We do not use Google Analytics to collect information that directly identifies you.</li>
<li><strong>Google AdSense:</strong> Displays advertisements on the site. Google and its partners may use cookies to show ads based on your visits to this and other websites.</li>
</ul>
<p>DialSize.com does not set its own tracking cookies. Analytics and advertising cookies are set by Google.</p>
<h2>Cookie Consent</h2>
<p><strong>Visitors in the European Economic Area, United Kingdom, and Switzerland:</strong> Before any analytics or advertising cookies are set, you will see a consent message provided by Google. Analytics and personalized advertising are only enabled if you choose to allow them. If you decline, Google may still show non-personalized ads, which use only limited data such as general location and the page being viewed.</p>
<p><strong>Visitors in all other regions:</strong> Analytics and personalized advertising are enabled by default. You can opt out at any time using the options below.</p>
<h2>Managing Your Preferences</h2>
<ul>
<li>Control personalized advertising from Google at <a href="https://adssettings.google.com/" rel="nofollow">Google Ad Settings</a>.</li>
<li>Learn how Google uses data from sites that use its services at <a href="https://policies.google.com/technologies/partner-sites" rel="nofollow">How Google uses information from sites that use its services</a>.</li>
<li>Opt out of Google Analytics on all websites with the <a href="https://tools.google.com/dlpage/gaoptout" rel="nofollow">Google Analytics Opt-out Browser Add-on</a>.</li>
<li>Block or delete cookies in your browser settings. If you are in the European Economic Area, United Kingdom, or Switzerland, clearing cookies for this site will show Google's consent message again on your next visit so you can change your choice.</li>
</ul>
<h2>Affiliate Links</h2>
<p>Some links on DialSize.com are affiliate links. When you click these links and make a purchase, we may earn a commission at no extra cost to you. This helps us maintain and improve the site. See our <a href="/affiliate-disclosure/">Affiliate Disclosure</a> for details.</p>
<h2>Your Rights</h2>
<p>Depending on where you live, including under the GDPR and UK GDPR, you may have the right to access, correct, or delete your personal data, and to object to or restrict its processing. To exercise these rights, contact us using the details below.</p>
<h2>Data Retention</h2>
<p>Google Analytics data is retained for 14 months. We do not store any personal information beyond what is collected by Google Analytics and Google AdSense.</p>
<h2>Contact</h2>
<p>For privacy-related questions, contact us at <a href="mailto:info@dialsize.com">info@dialsize.com</a>.</p>"""

        canonical = self.url("privacy/index.html")
        html = self.env.get_template("static_page.html").render(
            meta_title="Privacy Policy | DialSize",
            meta_desc="DialSize.com privacy policy. Learn how we handle your data, cookies, analytics, and advertising.",
            canonical=canonical,
            page_title="Privacy Policy",
            page_content=privacy_content,
        )
        self.write("privacy/index.html", html)

        # About
        about_content = """<h2>What is DialSize?</h2>
<p>DialSize is a comprehensive watch dimensions database built for watch enthusiasts, buyers, and researchers. We catalog the exact measurements of hundreds of watches so you can compare sizes, check wrist fit, and make informed purchasing decisions — all without visiting a boutique.</p>
<h2>Why Dimensions Matter</h2>
<p>Watch brands advertise diameter, but that number alone does not tell you how a watch wears. Lug-to-lug distance determines whether a watch overhangs your wrist. Thickness determines how it sits under a shirt cuff. Lug width determines strap compatibility. We track all of these.</p>
<h2>Our Data</h2>
<p>All dimensions are sourced from manufacturer specifications, verified against multiple independent sources, and regularly updated. Where manufacturer data is unavailable, we note the source. Each watch entry includes the date it was last verified.</p>
<h2>How to Use DialSize</h2>
<ul>
<li><strong>Search:</strong> Use the search bar to find any watch by brand, model, or reference number.</li>
<li><strong>Compare:</strong> Our comparison pages put two watches side by side with differences highlighted.</li>
<li><strong>Guides:</strong> Browse our curated guides for specific needs — small wrists, thin watches, particular lug widths.</li>
<li><strong>Wrist Fit:</strong> Each watch page includes a wrist fit estimate based on lug-to-lug distance.</li>
</ul>
<h2>Contact</h2>
<p>Questions, corrections, or data submissions: <a href="mailto:info@dialsize.com">info@dialsize.com</a></p>"""

        canonical = self.url("about/index.html")
        html = self.env.get_template("static_page.html").render(
            meta_title="About DialSize — Watch Dimensions Database",
            meta_desc="DialSize is a comprehensive watch dimensions database. Compare watch sizes, check wrist fit, and find your perfect watch.",
            canonical=canonical,
            page_title="About DialSize",
            page_content=about_content,
        )
        self.write("about/index.html", html)

        # Affiliate disclosure
        affiliate_content = """<h2>FTC Disclosure</h2>
<p>DialSize.com is a participant in affiliate programs including, but not limited to, the eBay Partner Network. This means that when you click certain links on our site and make a purchase, we may earn a commission at no additional cost to you.</p>
<h2>How Affiliate Links Work</h2>
<p>On our watch reference pages and comparison pages, you will find "Where to Buy" links to retailers such as eBay, Chrono24, Jomashop, and Amazon. These links contain tracking parameters that identify DialSize as the referral source. If you make a purchase through these links, the retailer pays us a small commission.</p>
<h2>Our Commitment</h2>
<ul>
<li>Affiliate relationships do not influence our data, measurements, or editorial content.</li>
<li>All dimensions and specifications are sourced from manufacturers and verified independently.</li>
<li>We never recommend a watch because of its affiliate commission.</li>
<li>All affiliate links are clearly marked with <code>rel="sponsored"</code> attributes.</li>
</ul>
<h2>Questions?</h2>
<p>If you have questions about our affiliate relationships, contact us at <a href="mailto:info@dialsize.com">info@dialsize.com</a>.</p>"""

        canonical = self.url("affiliate-disclosure/index.html")
        html = self.env.get_template("static_page.html").render(
            meta_title="Affiliate Disclosure | DialSize",
            meta_desc="DialSize.com affiliate disclosure. We earn commissions from qualifying purchases through our links at no cost to you.",
            canonical=canonical,
            page_title="Affiliate Disclosure",
            page_content=affiliate_content,
        )
        self.write("affiliate-disclosure/index.html", html)

    # -- 404 --
    def gen_404(self):
        print("Generating 404 page...")
        html = self.env.get_template("error.html").render(
            meta_title="Page Not Found | DialSize",
            meta_desc="The page you requested was not found.",
            canonical=SITE_URL + "/404.html",
        )
        self.write("404.html", html)

    # -- Sitemap --
    def gen_sitemap(self):
        print("Generating sitemap.xml...")
        lines = ['<?xml version="1.0" encoding="UTF-8"?>']
        lines.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
        today = datetime.now().strftime("%Y-%m-%d")
        for u in sorted(set(self.all_urls)):
            priority = "1.0" if u == SITE_URL + "/" else "0.8" if u.count("/") <= 4 else "0.6"
            lines.append(f"  <url><loc>{u}</loc><lastmod>{today}</lastmod><priority>{priority}</priority></url>")
        lines.append("</urlset>")
        self.write("sitemap.xml", "\n".join(lines))

    # -- Robots.txt --
    def gen_robots(self):
        print("Generating robots.txt...")
        content = f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n"
        self.write("robots.txt", content)

    # -- Search index --
    def gen_search_index(self):
        print("Generating search-index.json...")
        self.write("search-index.json", json.dumps(self.search_index, separators=(",", ":")))

    # -- CNAME --
    def gen_cname(self):
        print("Generating CNAME...")
        self.write("CNAME", "dialsize.com")


class _DictLoader(BaseLoader):
    """Jinja2 loader backed by a dict of template strings."""
    def __init__(self, mapping):
        self.mapping = mapping

    def get_source(self, environment, template):
        if template not in self.mapping:
            raise TemplateNotFound(template)
        source = self.mapping[template]
        return source, template, lambda: True


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    gen = SiteGenerator()
    gen.run()

"""Regenerate FloodSense design-output PNGs from the shared high-fidelity tokens.

This repository has no web frontend source tree yet; the PNGs are the current
design references. The script keeps the screen inventory intact, applies the
palette to existing high-fidelity screens, and redraws the two reusable design
boards from the same token file.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "frontend-design-output"
TOKENS = OUTPUT / "design-tokens.json"


def rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))


def hex_value(value) -> str:
    if isinstance(value, str):
        return value.lower()
    return "#%02x%02x%02x" % value


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        Path("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


def rounded(draw: ImageDraw.ImageDraw, box, fill, outline=None, radius=12, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def text(draw, xy, value, size=16, fill=None, bold=False, anchor=None):
    draw.text(xy, value, font=font(size, bold), fill=fill, anchor=anchor)


def swatch(draw, x, y, w, h, name, color_value, label, colors):
    rounded(draw, (x, y, x + w, y + h), colors["surface"], colors["divider"], radius=2)
    draw.rectangle((x, y, x + w, y + 76), fill=rgb(color_value) if isinstance(color_value, str) else color_value)
    text(draw, (x + w / 2, y + 91), name, 13, colors["bodyText"], anchor="mm")
    text(draw, (x + w / 2, y + 111), hex_value(color_value), 12, colors["secondaryText"], anchor="mm")
    text(draw, (x + w / 2, y + 131), label, 11, colors["secondaryText"], anchor="mm")


def draw_design_system(colors):
    image = Image.new("RGB", (1600, 1200), colors["pageBackground"])
    draw = ImageDraw.Draw(image)
    margin = 56
    text(draw, (margin, 42), "FloodSense", 18, colors["primary"], bold=True)
    text(draw, (margin, 82), "Design Guide - COLORS", 34, colors["bodyText"], bold=True)
    text(draw, (margin, 124), "Color palettes", 18, colors["secondaryText"])

    palette = [
        ("Primary / Brand", colors["primary"], "Primary action"),
        ("Nav / Link Hover", colors["linkHover"], "Hover / link"),
        ("Active Background", colors["activeBackground"], "Selected state"),
        ("Page Background", colors["pageBackground"], "App canvas"),
        ("Card / Surface", colors["surface"], "Cards and modals"),
        ("Border / Divider", colors["divider"], "Field and table lines"),
        ("Body Text", colors["bodyText"], "Primary copy"),
        ("Secondary Text", colors["secondaryText"], "Supporting copy"),
    ]
    x0, y0, gap, card_w, card_h = 62, 178, 22, 330, 150
    for i, (name, value, label) in enumerate(palette):
        row, col = divmod(i, 4)
        swatch(draw, x0 + col * (card_w + gap), y0 + row * (card_h + 22), card_w, card_h, name, value, label, colors)

    text(draw, (margin, 548), "Susceptibility classes", 18, colors["bodyText"])
    classes = [
        ("Low", colors["low"], "Normal / safe"),
        ("Moderate", colors["moderate"], "Advisory"),
        ("High", colors["high"], "High susceptibility"),
        ("Very High", colors["veryHigh"], "Critical state"),
        ("Uncertain", colors["uncertain"], "Insufficient data"),
    ]
    card_w, card_h, gap = 272, 150, 18
    for i, (name, value, label) in enumerate(classes):
        swatch(draw, 62 + i * (card_w + gap), 590, card_w, card_h, name, value, label, colors)

    # Compact component rules, visible on the same source-of-truth board.
    rounded(draw, (62, 824, 1538, 1134), colors["surface"], colors["divider"], radius=14)
    text(draw, (88, 852), "Reusable component rules", 22, colors["bodyText"], bold=True)
    rules = [
        ("Buttons", "Primary blue actions; outlined secondary actions; yellow review actions."),
        ("Status", "Always pair label + icon + color. Never communicate a safety class by color alone."),
        ("Surfaces", "White cards on #f7f8f5 with #e5e7eb dividers and a restrained shadow."),
        ("Forms", "16 px controls, generous touch targets, visible error and focus states."),
    ]
    for i, (label, value) in enumerate(rules):
        yy = 905 + i * 48
        text(draw, (92, yy), label, 14, colors["primary"], bold=True)
        text(draw, (250, yy), value, 14, colors["bodyText"])
    image.save(OUTPUT / "design-system.png")


def chip(draw, x, y, label, fill, ink, dot=None):
    width = int(draw.textlength(label, font=font(13, True))) + 34
    rounded(draw, (x, y, x + width, y + 30), fill, radius=15)
    if dot:
        draw.ellipse((x + 12, y + 10, x + 20, y + 18), fill=ink)
        text(draw, (x + 27, y + 15), label, 13, ink, bold=True, anchor="lm")
    else:
        text(draw, (x + width / 2, y + 15), label, 13, ink, bold=True, anchor="mm")
    return width


def component_card(draw, box, title, colors):
    rounded(draw, box, colors["surface"], colors["divider"], radius=14)
    text(draw, (box[0] + 22, box[1] + 26), title, 20, colors["bodyText"], bold=True)


def draw_component_library(colors):
    image = Image.new("RGB", (1600, 1200), colors["pageBackground"])
    draw = ImageDraw.Draw(image)
    text(draw, (56, 42), "FloodSense", 18, colors["primary"], bold=True)
    text(draw, (56, 82), "Reusable components", 34, colors["bodyText"], bold=True)
    text(draw, (56, 124), "Building blocks every resident and admin screen is assembled from", 18, colors["secondaryText"])
    text(draw, (1320, 42), "Resident + admin", 14, colors["secondaryText"])

    cards = [(28, 184, 508, 430), (546, 184, 1036, 430), (1044, 184, 1572, 430),
             (28, 452, 508, 698), (546, 452, 1036, 698), (1044, 452, 1572, 698),
             (28, 720, 508, 966), (546, 720, 1036, 966), (1044, 720, 1572, 966)]
    titles = ["Buttons", "Status pills & susceptibility chips", "Form elements", "Alerts", "Map controls & legend", "Cards & metrics", "Loading / empty / offline", "Tables & filters", "Confirmation & provenance"]
    for box, title in zip(cards, titles):
        component_card(draw, box, title, colors)

    # Buttons
    x, y = 50, 244
    button_rows = [
        [("+  New rule", colors["primary"], colors["surface"], None), ("Publish version", colors["moderate"], colors["bodyText"], None)],
        [("Save draft", colors["surface"], colors["secondaryText"], colors["divider"]), ("Preview colors", colors["surface"], colors["primary"], colors["primary"])],
    ]
    for row_index, row in enumerate(button_rows):
        x = 50
        y = 244 + row_index * 54
        for label, fill, ink, outline in row:
            w = int(draw.textlength(label, font=font(14, True))) + 34
            rounded(draw, (x, y, x + w, y + 42), fill, outline, radius=8)
            text(draw, (x + w / 2, y + 21), label, 14, ink, bold=True, anchor="mm")
            x += w + 12
    text(draw, (50, 362), "Primary, review, outlined, and link-style actions share one rhythm.", 12, colors["secondaryText"])

    # Status and severity
    x, y = 568, 244
    for label, fill, ink in [("Draft", "#eef1f4", colors["secondaryText"]), ("Under review", "#fff4cc", "#8a6500"), ("Approved", "#e8f0ff", colors["primary"]), ("Published", colors["activeBackground"], colors["low"]), ("Rejected", "#f8dedd", colors["veryHigh"])]:
        x += chip(draw, x, y, label, fill if isinstance(fill, tuple) else rgb(fill), ink) + 8
    x, y = 568, 300
    for label, key in [("Low", "low"), ("Moderate", "moderate"), ("High", "high"), ("Very high", "veryHigh"), ("Uncertain", "uncertain")]:
        fill = {"low":"#e8f5ec", "moderate":"#fff4cc", "high":"#fde9d9", "veryHigh":"#f8dedd", "uncertain":"#eef1f4"}[key]
        x += chip(draw, x, y, label, fill if isinstance(fill, tuple) else rgb(fill), colors[key], dot=True) + 8

    # Form elements
    text(draw, (1066, 244), "Home barangay", 13, colors["bodyText"], bold=True)
    rounded(draw, (1066, 266, 1542, 308), colors["surface"], colors["divider"], radius=7)
    text(draw, (1082, 287), "Select from approved list", 14, colors["secondaryText"], anchor="lm")
    text(draw, (1066, 340), "Email address", 13, colors["bodyText"], bold=True)
    rounded(draw, (1066, 362, 1542, 404), colors["surface"], colors["primary"], radius=7)
    text(draw, (1082, 383), "mara@example.com", 14, colors["bodyText"], anchor="lm")
    rounded(draw, (1066, 420, 1542, 464), "#f8dedd", radius=7)
    text(draw, (1082, 442), "Please choose a supported barangay.", 13, colors["veryHigh"], anchor="lm")

    # Alerts
    for i, (label, copy, key, fill) in enumerate([
        ("Info", "Map version 12 is live", "primary", "#eef7fd"),
        ("Warning", "3 zones have invalid geometry", "moderate", "#fff8e4"),
        ("Success", "Rule set v8 passed validation", "low", "#e8f5ec"),
        ("Error", "Publish blocked", "veryHigh", "#f8dedd"),
    ]):
        yy = 500 + i * 42
        rounded(draw, (50, yy, 486, yy + 32), rgb(fill), radius=6)
        draw.rectangle((50, yy, 54, yy + 32), fill=colors[key])
        text(draw, (68, yy + 16), f"{label}  ·  {copy}", 13, colors[key], bold=True, anchor="lm")

    # Map controls / legend
    rounded(draw, (568, 500, 1014, 642), "#edf8fd", colors["divider"], radius=10)
    for i, label in enumerate(["+", "−", "⌖"]):
        rounded(draw, (586 + i * 44, 520, 620 + i * 44, 554), colors["surface"], colors["divider"], radius=7)
        text(draw, (603 + i * 44, 537), label, 18, colors["primary"], bold=True, anchor="mm")
    rounded(draw, (586, 574, 744, 630), colors["surface"], colors["divider"], radius=8)
    text(draw, (604, 592), "● Low", 12, colors["low"])
    text(draw, (604, 612), "● High", 12, colors["high"])

    # Cards / metrics
    for i, (label, value) in enumerate([("ZONES", "48"), ("CENTERS", "12")]):
        bx = 1066 + i * 230
        rounded(draw, (bx, 500, bx + 210, 618), colors["surface"], colors["divider"], radius=10)
        text(draw, (bx + 16, 522), label, 12, colors["secondaryText"], bold=True)
        text(draw, (bx + 16, 556), value, 30, colors["primary"], bold=True)

    # Loading/empty, tables, provenance
    for i, width in enumerate([400, 300]):
        rounded(draw, (50, 770 + i * 24, 50 + width, 780 + i * 24), "#d9e8ef", radius=5)
    rounded(draw, (50, 830, 486, 920), colors["surface"], colors["divider"], radius=8)
    text(draw, (268, 866), "No approved results for this scenario.", 14, colors["bodyText"], anchor="mm")
    text(draw, (268, 889), "Try another duration.", 12, colors["secondaryText"], anchor="mm")
    rounded(draw, (568, 770, 740, 812), colors["surface"], colors["divider"], radius=7)
    text(draw, (586, 791), "Search", 13, colors["secondaryText"], anchor="lm")
    for i, label in enumerate(["FS-ZONE-0018     Review", "FS-ZONE-0001     Published"]):
        text(draw, (568, 850 + i * 34), label, 13, colors["bodyText"])
    rounded(draw, (1066, 770, 1542, 920), "#fafdff", colors["divider"], radius=10)
    text(draw, (1084, 796), "Publish map v1.3?", 16, colors["bodyText"], bold=True)
    text(draw, (1084, 822), "Every public result shows source, version, and date.", 12, colors["secondaryText"])
    rounded(draw, (1084, 854, 1170, 894), colors["surface"], colors["primary"], radius=7)
    text(draw, (1127, 874), "Cancel", 13, colors["primary"], bold=True, anchor="mm")
    rounded(draw, (1182, 854, 1270, 894), colors["primary"], radius=7)
    text(draw, (1226, 874), "Publish", 13, colors["surface"], bold=True, anchor="mm")

    text(draw, (56, 1128), "FloodSense · high-fidelity reusable component reference", 13, colors["secondaryText"])
    image.save(OUTPUT / "component-library.png")


def restyle_existing_pngs(colors):
    mapping = {
        "#0b3c5d": colors["primary"], "#075985": colors["primary"], "#0891b2": colors["linkHover"],
        "#f6f9fc": colors["pageBackground"], "#172033": colors["bodyText"], "#cbd5e1": colors["divider"],
        "#64748b": colors["secondaryText"], "#15803d": colors["low"], "#d97706": colors["moderate"],
        "#ea580c": colors["high"], "#dc2626": colors["veryHigh"],
        "#eaf7ee": "#e8f5ec", "#fff4de": "#fff4cc", "#fdecec": "#f8dedd",
        "#e8f0ff": "#eef7fd", "#e6ecf1": "#e5e7eb",
    }
    exact = {rgb(k): (v if isinstance(v, tuple) else rgb(v)) for k, v in mapping.items()}
    for path in OUTPUT.glob("*.png"):
        if path.name in {"design-system.png", "component-library.png", "floodsense-contour-reference.png"}:
            continue
        with Image.open(path) as source:
            image = source.convert("RGB")
        pixels = image.load()
        for y in range(image.height):
            for x in range(image.width):
                color = pixels[x, y]
                if color in exact:
                    pixels[x, y] = exact[color]
        temporary = path.with_name(path.stem + ".restyled.png")
        image.save(temporary)
        os.replace(temporary, path)


def main():
    tokens = json.loads(TOKENS.read_text(encoding="utf-8"))
    colors = {key: rgb(value) for key, value in tokens["palette"].items()}
    restyle_existing_pngs(colors)
    draw_design_system(colors)
    draw_component_library(colors)


if __name__ == "__main__":
    main()

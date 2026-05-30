import os
import sys
from PIL import Image
from khatt.geometry.skeleton  import render_skeleton
from khatt.diffusion.stylizer import stylize_skeleton
from khatt.validation.gate    import validate_output
STYLES = {
    "thuluth": {
        "font":      "assets/fonts/Amiri-Regular.ttf",
        "font_size": 140,
        "dot_color": (15, 8, 3),
        "prompt": (
            "Arabic Thuluth calligraphy, each letter clearly legible, "
            "deep black ink on aged parchment, classical Islamic manuscript, "
            "reed pen strokes, museum quality, high contrast"
        ),
    },
    "naskh": {
        "font":      "assets/fonts/Amiri-Regular.ttf",
        "font_size": 140,
        "dot_color": (15, 8, 3),
        "prompt": (
            "Arabic Naskh calligraphy, clean precise letterforms, "
            "black ink on white paper, classical manuscript, sharp and legible"
        ),
    },
    "nastaliq": {
        "font":      "assets/fonts/NotoNastaliqUrdu-Regular.ttf",
        "font_size": 120,
        "dot_color": (15, 8, 3),
        "prompt": (
            "Persian Nastaliq calligraphy, authentic diagonal script, "
            "letters flowing upward to the right, deep black ink on "
            "aged cream paper, Safavid dynasty manuscript style, "
            "reed pen with natural ink bleed, each letter clearly "
            "formed, classical Persian poetry manuscript, masterpiece"
        ),
    },
    "ruqah": {
        "font":      "assets/fonts/ArefRuqaa-Regular.ttf",
        "font_size": 140,
        "dot_color": (15, 8, 3),
        "prompt": (
            "Arabic Ruqah handwriting script, compressed simplified "
            "letterforms, deep black ink on white paper, Ottoman "
            "administrative document style, clean confident strokes, "
            "professional calligrapher, high contrast, sharp edges, "
            "each letter distinct and legible"
        ),
    },
    "kufic": {
        "font":      "assets/fonts/ReemKufi-Regular.ttf",
        "font_size": 140,
        "dot_color": (212, 175, 55),
        "prompt": (
            "Arabic Kufic calligraphy, angular geometric letterforms, "
            "gold ink on dark stone, early Islamic architecture inscription, "
            "bold geometric strokes, include all letter dots, monumental style"
        ),
    },
    "diwani": {
        "font":      "assets/fonts/Amiri-Regular.ttf",
        "font_size": 140,
        "dot_color": (212, 175, 55),
        "prompt": (
            "Arabic Diwani calligraphy, highly ornate flowing script, "
            "gold ink on cream parchment, Ottoman imperial court style, "
            "elaborate letterforms, luxury manuscript"
        ),
    },
}

def enforce_aspect_ratio(path, max_ratio=2.4):
    img = Image.open(path).convert("RGB")
    w, h = img.size
    ratio = w / h
    if ratio > max_ratio:
        new_h = int(w / max_ratio)
        out   = Image.new("RGB", (w, new_h), (255, 255, 255))
        out.paste(img, (0, (new_h - h) // 2))
        out.save(path)
        print(f"Aspect ratio fixed : {w}x{h} → {w}x{new_h}")
    elif ratio < (1 / max_ratio):
        new_w = int(h / max_ratio)
        out   = Image.new("RGB", (new_w, h), (255, 255, 255))
        out.paste(img, ((new_w - w) // 2, 0))
        out.save(path)
        print(f"Aspect ratio fixed : {w}x{h} → {new_w}x{h}")
    else:
        print(f"Aspect ratio OK    : {w}x{h} ({ratio:.2f}:1)")

def run(text, style="thuluth"):
    if style not in STYLES:
        print(f"Unknown style '{style}'. Available: {list(STYLES.keys())}")
        sys.exit(1)

    cfg           = STYLES[style]
    skeleton_path = "outputs\\skeleton.png"
    stylized_path = "outputs\\stylized.png"
    font_path = "assets/fonts/Amiri-Regular.ttf"

    print("=" * 55)
    print(f"  Khatt Engine")
    print(f"  Text  : {text}")
    print(f"  Style : {style}")
    print(f"  Font  : {cfg['font']}")
    print("=" * 55)

    print("\n[Layer 1+2] Generating skeleton...")
    render_skeleton(text, cfg["font"], skeleton_path, font_size=cfg["font_size"])

    print("\n[Check]    Enforcing aspect ratio...")
    enforce_aspect_ratio(skeleton_path)

    print("\n[Layer 5]   Validating skeleton...")
    passed, score, _ = validate_output(skeleton_path, text)

    if not passed:
        print(f"\nSkeleton validation failed (score={score:.2f}).")
        sys.exit(1)

    print(f"\nSkeleton valid (score={score:.2f}). Proceeding to stylization.")

    print(f"\n[Layer 3+4] Stylizing ({style})...")
    success = stylize_skeleton(
        skeleton_path, stylized_path,
        cfg["prompt"],
        control_strength=0.95,
        dot_color=cfg["dot_color"]
    )

    if success:
        print(f"\nPipeline complete.")
        print(f"  start {stylized_path}")
    else:
        print("\nStylization failed. Check your API key.")
        sys.exit(1)
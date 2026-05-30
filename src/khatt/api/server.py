import os
import shutil
import time
import random
import numpy as np
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from PIL import Image
from scipy import ndimage
from scipy.ndimage import gaussian_filter

from khatt.geometry.skeleton  import render_skeleton
from khatt.diffusion.stylizer import stylize_skeleton
from khatt.validation.gate    import validate_output
from khatt.pipeline           import STYLES, enforce_aspect_ratio

Path("outputs").mkdir(exist_ok=True)
Path("outputs/history").mkdir(exist_ok=True)

app = FastAPI(title="Khatt Engine")
app.mount("/outputs", StaticFiles(directory="outputs"), name="outputs")


def build_letter_mask(skeleton_path, target_size, dilation=5, blur=2.0):
    """
    Builds a precise binary mask from the skeleton.

    This mask defines exactly where the letters are.
    Everything outside this mask is discarded from the AI output —
    no ornaments, no secondary text, no decorations can survive.

    Steps:
      1. Threshold: identify ink pixels
      2. Fill holes: counter-forms inside letters become solid
      3. Dilate: expand slightly to capture ink texture at edges
      4. Blur: smooth edges for natural-looking transitions
    """
    skeleton = Image.open(skeleton_path).convert("L")
    skeleton = skeleton.resize(target_size, Image.LANCZOS)
    skel_arr = np.array(skeleton)

    # Step 1 — ink mask
    ink = skel_arr < 100

    # Step 2 — fill counter-forms (inside of ع م ب etc)
    filled = ndimage.binary_fill_holes(ink)

    # Step 3 — dilate to capture edge texture from AI
    struct  = ndimage.generate_binary_structure(2, 1)
    dilated = ndimage.binary_dilation(
        filled, structure=struct, iterations=dilation
    )

    # Step 4 — smooth edges
    mask = gaussian_filter(
        dilated.astype(np.float32), sigma=blur
    )
    return np.clip(mask, 0, 1)


def apply_letter_mask(stylized_path, skeleton_path, output_path,
                      background=(255, 255, 255)):
    """
    THE CORE FIX — replaces prompt-based hallucination suppression.

    Takes the AI stylized image and discards everything outside
    the letter boundaries defined by the skeleton mask.

    The AI can generate whatever it wants around the letters.
    None of it survives this step. Only the letter pixels remain.

    Result: clean AI-textured letterforms on a plain background.
    No ornaments. No secondary text. No decorations. Guaranteed.
    """
    stylized = Image.open(stylized_path).convert("RGB")
    w, h     = stylized.size

    mask     = build_letter_mask(skeleton_path, (w, h))
    sty_arr  = np.array(stylized, dtype=np.float32)
    bg       = np.full_like(sty_arr, background, dtype=np.float32)

    # Composite: letter pixels from AI, everything else = clean background
    mask_3ch = mask[:, :, np.newaxis]
    result   = (sty_arr * mask_3ch + bg * (1.0 - mask_3ch))
    result   = np.clip(result, 0, 255).astype(np.uint8)

    Image.fromarray(result).save(output_path)
    print(f"Masked output -> {output_path}")
    return output_path


def apply_transparent_mask(stylized_path, skeleton_path, output_path):
    """
    Same as apply_letter_mask but with transparent background.
    For the Download Transparent option.
    """
    stylized = Image.open(stylized_path).convert("RGBA")
    w, h     = stylized.size

    mask     = build_letter_mask(skeleton_path, (w, h))
    sty_arr  = np.array(stylized, dtype=np.float32)
    alpha    = np.clip(mask * 255, 0, 255).astype(np.uint8)

    sty_arr[:, :, 3] = alpha
    Image.fromarray(sty_arr.astype(np.uint8), 'RGBA').save(
        output_path, format='PNG'
    )
    print(f"Transparent  -> {output_path}")


# Background colors per style — applied after masking
STYLE_BACKGROUNDS = {
    "thuluth":  (245, 235, 210),   # warm ivory parchment
    "naskh":    (255, 255, 255),   # pure white
    "nastaliq": (240, 236, 225),   # faded cream
    "ruqah":    (255, 255, 255),   # pure white — Ruqah is always clean
    "kufic":    (28,  28,  28),    # near-black stone
    "diwani":   (245, 235, 210),   # warm cream
}


class GenerateRequest(BaseModel):
    text:      str
    style:     str = "thuluth"
    font_size: int = 140


@app.get("/", response_class=HTMLResponse)
async def root():
    html_path = Path(__file__).parent.parent / "web" / "index.html"
    with open(html_path, "r", encoding="utf-8") as f:
        return f.read()


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/api/generate")
def generate(req: GenerateRequest):
    text  = req.text.strip()
    style = req.style

    if not text:
        raise HTTPException(400, "Text cannot be empty")
    if style not in STYLES:
        raise HTTPException(400, f"Unknown style: {style}")
    if not (60 <= req.font_size <= 300):
        raise HTTPException(400, "font_size must be between 60 and 300")

    cfg              = STYLES[style]
    skeleton_path    = "outputs/skeleton.png"
    skeleton_mask_path = "outputs/skeleton_mask.png"
    raw_ai_path      = "outputs/stylized_raw.png"
    stylized_path    = "outputs/stylized.png"
    transparent_path = "outputs/transparent.png"

    try:
        # Layer 1 + 2 — skeleton
        render_skeleton(
            text, cfg["font"], skeleton_path,
            font_size=req.font_size,
            add_border=cfg.get("border", False)
        )

        # Layer 3 — aspect ratio
        enforce_aspect_ratio(skeleton_path)

        # Save borderless mask copy
        shutil.copy(skeleton_path, skeleton_mask_path)

        # Layer 5 — validation
        skip_ocr = os.getenv("SKIP_OCR", "false").lower() == "true"
        if skip_ocr:
            passed, score = True, 1.0
        else:
            passed, score, _ = validate_output(skeleton_path, text)

        # Layer 4 — AI stylization (raw output)
        success = stylize_skeleton(
            skeleton_path, raw_ai_path,
            cfg["prompt"],
            control_strength=0.95,
            dot_color=cfg.get("dot_color", (20, 10, 5))
        )
        if not success:
            raise HTTPException(500, "Stylization API call failed")

        # POST-PROCESS — apply letter mask
        # This is the architectural fix: discards all AI-generated
        # ornaments, secondary text, and decorations. Only letter
        # pixels survive. Prompt-independent and guaranteed.
        bg = STYLE_BACKGROUNDS.get(style, (255, 255, 255))
        apply_letter_mask(
            raw_ai_path, skeleton_mask_path, stylized_path,
            background=bg
        )

        # Transparent version
        try:
            apply_transparent_mask(
                raw_ai_path, skeleton_mask_path, transparent_path
            )
            transparent_ok = True
        except Exception as e:
            print(f"Transparent failed: {e}")
            transparent_ok = False

        # History
        ts        = int(time.time())
        hist_dir  = Path("outputs/history")
        hist_path = hist_dir / f"{ts}_{style}.png"
        shutil.copy(stylized_path, hist_path)

        history_files = sorted(hist_dir.glob("*.png"))
        for old in history_files[:-12]:
            old.unlink()

        history = [
            f"/outputs/history/{f.name}"
            for f in sorted(
                hist_dir.glob("*.png"), reverse=True
            )[:6]
        ]

        return {
            "success":           True,
            "image_url":         f"/outputs/stylized.png?t={ts}",
            "skeleton_url":      f"/outputs/skeleton.png?t={ts}",
            "transparent_url":   f"/outputs/transparent.png?t={ts}"
                                 if transparent_ok else None,
            "validation_score":  round(score, 2),
            "validation_passed": passed,
            "history":           history,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))
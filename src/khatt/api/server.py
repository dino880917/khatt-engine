import os
import shutil
import time
import numpy as np
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
from PIL import Image
from scipy import ndimage
from scipy.ndimage import gaussian_filter

from khatt.geometry.skeleton  import render_skeleton, render_svg
from khatt.diffusion.stylizer import stylize_skeleton
from khatt.validation.gate    import validate_output
from khatt.pipeline           import STYLES, enforce_aspect_ratio
from khatt.transliteration.names import lookup, search as name_search, transliterate_western

Path("outputs").mkdir(exist_ok=True)
Path("outputs/history").mkdir(exist_ok=True)

app = FastAPI(title="Khatt Engine")
app.mount("/outputs", StaticFiles(directory="outputs"), name="outputs")


def create_transparent_png(stylized_path, skeleton_mask_path, output_path):
    stylized = Image.open(stylized_path).convert("RGBA")
    skeleton = Image.open(skeleton_mask_path).convert("L")

    if skeleton.size != stylized.size:
        skeleton = skeleton.resize(stylized.size, Image.LANCZOS)

    skel_arr = np.array(skeleton, dtype=np.uint8)
    ink_mask = skel_arr < 100
    filled   = ndimage.binary_fill_holes(ink_mask)
    struct   = ndimage.generate_binary_structure(2, 1)
    dilated  = ndimage.binary_dilation(filled, structure=struct, iterations=3)
    alpha_f  = gaussian_filter(dilated.astype(np.float32) * 255, sigma=1.5)
    alpha    = np.clip(alpha_f, 0, 255).astype(np.uint8)

    style_arr          = np.array(stylized)
    style_arr[:, :, 3] = alpha
    Image.fromarray(style_arr, 'RGBA').save(output_path, format='PNG')
    print(f"Transparent PNG -> {output_path}")


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


@app.get("/api/name/lookup")
def name_lookup(q: str):
    if not q or len(q.strip()) < 2:
        raise HTTPException(400, "Name too short")
    name   = q.strip()
    result = lookup(name)
    if result["found"]:
        result["method"] = "database"
        return result
    return transliterate_western(name)


@app.get("/api/name/search")
def name_search_endpoint(q: str):
    if not q or len(q.strip()) < 1:
        return {"results": []}
    return {"results": name_search(q.strip())}


@app.get("/api/svg")
def download_svg(text: str, style: str = "thuluth", font_size: int = 140):
    """
    Generate and download a clean SVG vector file.
    Uses FreeType Bézier outlines — no rasterization, no quality loss.
    """
    if not text:
        raise HTTPException(400, "Text cannot be empty")
    if style not in STYLES:
        raise HTTPException(400, f"Unknown style: {style}")

    cfg      = STYLES[style]
    svg_path = "outputs/calligraphy.svg"

    try:
        render_svg(
            text, cfg["font"], svg_path,
            font_size=font_size,
        )
        return FileResponse(
            svg_path,
            media_type="image/svg+xml",
            filename="khatt_calligraphy.svg"
        )
    except Exception as e:
        raise HTTPException(500, str(e))


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

    cfg                = STYLES[style]
    skeleton_path      = "outputs/skeleton.png"
    skeleton_mask_path = "outputs/skeleton_mask.png"
    stylized_path      = "outputs/stylized.png"
    transparent_path   = "outputs/transparent.png"

    try:
        render_skeleton(
            text, cfg["font"], skeleton_path,
            font_size=req.font_size,
            add_border=cfg.get("border", False)
        )

        enforce_aspect_ratio(skeleton_path)
        shutil.copy(skeleton_path, skeleton_mask_path)

        skip_ocr = os.getenv("SKIP_OCR", "false").lower() == "true"
        if skip_ocr:
            passed, score = True, 1.0
        else:
            passed, score, _ = validate_output(skeleton_path, text)

        success = stylize_skeleton(
            skeleton_path, stylized_path,
            cfg["prompt"],
            control_strength=0.95,
            dot_color=cfg.get("dot_color", (20, 10, 5))
        )
        if not success:
            raise HTTPException(500, "Stylization API call failed")

        try:
            create_transparent_png(
                stylized_path, skeleton_mask_path, transparent_path
            )
            transparent_ok = True
        except Exception as e:
            print(f"Transparent PNG failed: {e}")
            transparent_ok = False

        ts       = int(time.time())
        hist_dir = Path("outputs/history")
        shutil.copy(stylized_path, hist_dir / f"{ts}_{style}.png")

        history_files = sorted(hist_dir.glob("*.png"))
        for old in history_files[:-12]:
            old.unlink()

        history = [
            f"/outputs/history/{f.name}"
            for f in sorted(hist_dir.glob("*.png"), reverse=True)[:6]
        ]

        return {
            "success":           True,
            "image_url":         f"/outputs/stylized.png?t={ts}",
            "skeleton_url":      f"/outputs/skeleton.png?t={ts}",
            "transparent_url":   f"/outputs/transparent.png?t={ts}"
                                 if transparent_ok else None,
            "svg_url":           f"/api/svg?text={text}&style={style}"
                                 f"&font_size={req.font_size}",
            "validation_score":  round(score, 2),
            "validation_passed": passed,
            "history":           history,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))
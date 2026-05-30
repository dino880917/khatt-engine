import os
import shutil
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from PIL import Image

from khatt.geometry.skeleton  import render_skeleton
from khatt.diffusion.stylizer import stylize_skeleton
from khatt.validation.gate    import validate_output
from khatt.pipeline           import STYLES, enforce_aspect_ratio

# ── Create required directories on startup ──────────────────────────
Path("outputs").mkdir(exist_ok=True)
Path("outputs/history").mkdir(exist_ok=True)

app = FastAPI(title="Khatt Engine")
app.mount("/outputs", StaticFiles(directory="outputs"), name="outputs")


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

    cfg           = STYLES[style]
    skeleton_path = "outputs/skeleton.png"
    stylized_path = "outputs/stylized.png"

    try:
        # Layer 1 + 2 — skeleton
        render_skeleton(
            text, cfg["font"], skeleton_path,
            font_size=req.font_size
        )

        # Layer 3 — aspect ratio
        enforce_aspect_ratio(skeleton_path)

        # Layer 5 — validation
        passed, score, _ = validate_output(skeleton_path, text)

        # Layer 4 — stylize
        success = stylize_skeleton(
            skeleton_path, stylized_path,
            cfg["prompt"],
            control_strength=0.95,
            dot_color=cfg.get("dot_color", (20, 10, 5))
        )
        if not success:
            raise HTTPException(500, "Stylization API call failed")

        # Save to history
        ts        = int(time.time())
        hist_path = Path("outputs/history") / f"{ts}_{style}.png"
        shutil.copy(stylized_path, hist_path)

        # Keep only last 12 history items
        history_files = sorted(Path("outputs/history").glob("*.png"))
        for old in history_files[:-12]:
            old.unlink()

        # Build history list
        history = [
            f"/outputs/history/{f.name}"
            for f in sorted(
                Path("outputs/history").glob("*.png"),
                reverse=True
            )[:6]
        ]

        return {
            "success":           True,
            "image_url":         f"/outputs/stylized.png?t={ts}",
            "skeleton_url":      f"/outputs/skeleton.png?t={ts}",
            "validation_score":  round(score, 2),
            "validation_passed": passed,
            "history":           history,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))
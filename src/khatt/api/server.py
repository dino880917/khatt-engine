import os
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

app = FastAPI(title="Khatt Engine")
app.mount("/outputs", StaticFiles(directory="outputs"), name="outputs")

class GenerateRequest(BaseModel):
    text:      str
    style:     str = "thuluth"
    font_size: int = 140

@app.get("/", response_class=HTMLResponse)
async def root():
    html_path = os.path.join(
        os.path.dirname(__file__), "..", "web", "index.html"
    )
    with open(html_path, "r", encoding="utf-8") as f:
        return f.read()

@app.post("/api/generate")
def generate(req: GenerateRequest):
    text  = req.text.strip()
    style = req.style

    if not text:
        raise HTTPException(400, "Text cannot be empty")
    if style not in STYLES:
        raise HTTPException(400, f"Unknown style: {style}")

    cfg           = STYLES[style]
    skeleton_path = "outputs/skeleton.png"
    stylized_path = "outputs/stylized.png"

    try:
        render_skeleton(text, cfg["font"], skeleton_path,
                        font_size=req.font_size)
        enforce_aspect_ratio(skeleton_path)
        passed, score, _ = validate_output(skeleton_path, text)
        success = stylize_skeleton(
            skeleton_path, stylized_path,
            cfg["prompt"],
            control_strength=0.95,
            dot_color=cfg.get("dot_color", (20, 10, 5))
        )
        if not success:
            raise HTTPException(500, "Stylization API call failed")

        import time
        import shutil

        # Save timestamped copy so history works
        ts       = int(time.time())
        hist_dir = Path("outputs/history")
        hist_dir.mkdir(exist_ok=True)
        hist_path = hist_dir / f"{ts}_{style}.png"
        shutil.copy(stylized_path, hist_path)

        # Keep only last 12 history items
        history_files = sorted(hist_dir.glob("*.png"))
        for old in history_files[:-12]:
            old.unlink()

        # Build history list for response
        history = []
        for f in sorted(hist_dir.glob("*.png"), reverse=True)[:6]:
            history.append(f"/outputs/history/{f.name}")

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
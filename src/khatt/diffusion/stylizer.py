import os
import random
import requests
import numpy as np
from PIL import Image
from dotenv import load_dotenv

load_dotenv()

def extract_dots(skeleton_path, min_size=2, max_size=400):
    from scipy import ndimage
    img      = Image.open(skeleton_path).convert("L")
    arr      = np.array(img)
    dark     = arr < 128
    labeled, num = ndimage.label(dark)
    dot_mask = np.zeros_like(dark, dtype=bool)
    for i in range(1, num + 1):
        region = labeled == i
        size   = region.sum()
        if min_size <= size <= max_size:
            dot_mask |= region
    return dot_mask, img.size

def composite_dots(stylized_path, skeleton_path, output_path,
                   dot_color=(20, 10, 5)):
    try:
        from scipy import ndimage
    except ImportError:
        print("scipy not installed — skipping dot composite.")
        return

    dot_mask, skel_size = extract_dots(skeleton_path)
    stylized = Image.open(stylized_path).convert("RGB")
    sty_w, sty_h = stylized.size

    dot_img     = Image.fromarray(dot_mask.astype(np.uint8) * 255, mode="L")
    dot_resized = dot_img.resize((sty_w, sty_h), Image.NEAREST)
    dot_arr     = np.array(dot_resized) > 128

    sty_arr             = np.array(stylized)
    sty_arr[dot_arr]    = dot_color
    Image.fromarray(sty_arr).save(output_path)
    print(f"Dots composited -> {output_path}")

def stylize_skeleton(skeleton_path, output_path, style_prompt,
                     control_strength=0.95, composite=False,
                     dot_color=(20, 10, 5)):

    api_key = os.getenv("STABILITY_API_KEY")
    if not api_key:
        raise ValueError("STABILITY_API_KEY not found.")

    seed = random.randint(1, 2147483647)
    print(f"Sending skeleton to Stability AI...")
    print(f"Control strength : {control_strength}")
    print(f"Seed             : {seed}")

    with open(skeleton_path, "rb") as f:
        image_data = f.read()

    response = requests.post(
        "https://api.stability.ai/v2beta/stable-image/control/sketch",
        headers={
            "authorization": f"Bearer {api_key}",
            "accept":        "image/*",
        },
        files={
            "image": ("skeleton.png", image_data, "image/png"),
        },
        data={
            "prompt": style_prompt,
            "negative_prompt": (
                "multiple lines of text, text lines below the word, "
                "manuscript page, full page calligraphy, text filling page, "
                "secondary calligraphic lines, background writing, "
                "margin text, border calligraphy, page layout, "
                "book page, manuscript layout, additional words, "
                "decorative text fills, extra Arabic text, "
                "calligraphic context, supporting verses, "
                "blurry, distorted, illegible, deformed letters, "
                "missing dots, wrong letterforms, latin text, unreadable"
            ),
            "control_strength": str(control_strength),
            "output_format":    "png",
            "seed":             str(seed),
        },
        timeout=120,
    )

    if response.status_code == 200:
        raw_path = output_path.replace(".png", "_raw.png")
        with open(raw_path, "wb") as f:
            f.write(response.content)
        print(f"AI output saved -> {raw_path}")

        if composite:
            print("Compositing skeleton dots onto AI output...")
            composite_dots(raw_path, skeleton_path, output_path,
                           dot_color=dot_color)
        else:
            import shutil
            shutil.copy(raw_path, output_path)

        return True
    else:
        print(f"API Error {response.status_code}: {response.text}")
        return False
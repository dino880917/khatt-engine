import os
import requests
import numpy as np
from PIL import Image
from dotenv import load_dotenv

load_dotenv()

def extract_dots(skeleton_path, min_size=2, max_size=400):
    """
    Extracts small dark regions from the skeleton — these are the dots.
    Arabic dots are small isolated ink regions above or below the baseline.
    Returns a mask of dot pixels.
    """
    from PIL import ImageFilter
    img   = Image.open(skeleton_path).convert("L")
    arr   = np.array(img)
    dark  = arr < 128  # True where ink exists

    from scipy import ndimage
    labeled, num = ndimage.label(dark)
    dot_mask = np.zeros_like(dark, dtype=bool)

    for i in range(1, num + 1):
        region = labeled == i
        size   = region.sum()
        if min_size <= size <= max_size:
            dot_mask |= region

    return dot_mask, img.size

def composite_dots(stylized_path, skeleton_path, output_path,
                   dot_color=(20, 10, 5), ink_color=None):
    """
    Takes the stylized image and composites skeleton dots on top.
    Guarantees linguistically correct dot placement regardless of AI output.
    """
    try:
        from scipy import ndimage
    except ImportError:
        print("scipy not installed — skipping dot composite.")
        return

    dot_mask, skel_size = extract_dots(skeleton_path)

    stylized = Image.open(stylized_path).convert("RGB")
    sty_w, sty_h = stylized.size

    # Scale dot mask to match stylized image dimensions
    scale_x = sty_w / skel_size[0]
    scale_y = sty_h / skel_size[1]

    dot_img  = Image.fromarray(dot_mask.astype(np.uint8) * 255, mode="L")
    dot_resized = dot_img.resize((sty_w, sty_h), Image.NEAREST)
    dot_arr  = np.array(dot_resized) > 128

    sty_arr  = np.array(stylized)
    # Paint dots with a dark ink color
    if ink_color is not None:
        # Sample the average ink color from the letter bodies
        # and use a slightly darker version for the dots
        sty_arr[dot_arr] = ink_color
    else:
        sty_arr[dot_arr] = dot_color
    

    result = Image.fromarray(sty_arr)
    result.save(output_path)
    print(f"Dots composited -> {output_path}")

def stylize_skeleton(skeleton_path, output_path, style_prompt,
                     control_strength=0.95, composite=False,
                     dot_color=(20, 10, 5)):

    api_key = os.getenv("STABILITY_API_KEY")
    if not api_key:
        raise ValueError("STABILITY_API_KEY not found.")

    print(f"Sending skeleton to Stability AI...")
    print(f"Control strength : {control_strength}")

    with open(skeleton_path, "rb") as f:
        image_data = f.read()

    response = requests.post(
        "https://api.stability.ai/v2beta/stable-image/control/sketch",
         timeout=120,
        headers={
            "authorization": f"Bearer {api_key}",
            "accept": "image/*",
        },
        files={"image": ("skeleton.png", image_data, "image/png")},
        data={
            "prompt": style_prompt,
            "negative_prompt": (
                "extra calligraphic text, background Arabic writing, "
                "secondary text lines, additional words, border calligraphy, "
                "filler calligraphy, ornamental text fills, margin writing, "
                "extra flourishes outside the main letters, duplicate strokes, "
                "decorative text backgrounds, stamps, seals, medallions, "
                "calligraphic borders with text, additional ornamental elements, "
                "blurry, distorted, illegible, deformed letters, "
                "missing dots, wrong letterforms, latin text, unreadable"
            ),
            "control_strength": str(control_strength),
            "output_format":    "png",
        },
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
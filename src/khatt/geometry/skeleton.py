import freetype
import uharfbuzz as hb
import numpy as np
import re
from PIL import Image
from scipy import ndimage

HARAKAT_RANGE = set(range(0x064B, 0x0660)) | {0x0670, 0x0671}
HARAKAT_GRAY  = 210


def add_frame(canvas, frame_pad=18, outer_thick=3, gap=8, inner_thick=1):
    result = canvas.copy()
    h, w   = result.shape
    p      = frame_pad

    def hline(y, x0, x1, t):
        result[max(0,y):min(h,y+t), max(0,x0):min(w,x1)] = 0

    def vline(x, y0, y1, t):
        result[max(0,y0):min(h,y1), max(0,x):min(w,x+t)] = 0

    hline(p,               p, w-p, outer_thick)
    hline(h-p-outer_thick, p, w-p, outer_thick)
    vline(p,               p, h-p, outer_thick)
    vline(w-p-outer_thick, p, h-p, outer_thick)

    i = p + gap + outer_thick
    hline(i,               i, w-i, inner_thick)
    hline(h-i-inner_thick, i, w-i, inner_thick)
    vline(i,               i, h-i, inner_thick)
    vline(w-i-inner_thick, i, h-i, inner_thick)

    diamond_r = 5
    corners = [
        (p + gap//2 + outer_thick + 2, p + gap//2 + outer_thick + 2),
        (p + gap//2 + outer_thick + 2, w - p - gap//2 - outer_thick - 2),
        (h - p - gap//2 - outer_thick - 2, p + gap//2 + outer_thick + 2),
        (h - p - gap//2 - outer_thick - 2, w - p - gap//2 - outer_thick - 2),
    ]
    for cy, cx in corners:
        for dy in range(-diamond_r, diamond_r + 1):
            for dx in range(-diamond_r, diamond_r + 1):
                if abs(dy) + abs(dx) <= diamond_r:
                    ny, nx = cy + dy, cx + dx
                    if 0 <= ny < h and 0 <= nx < w:
                        result[ny, nx] = 0

    return result



def render_svg(text, font_path, output_path, font_size=140,
               fill_color="#1a0a00"):
    """
    Render Arabic text as a clean SVG vector file.

    Strategy: render the skeleton PNG first (already proven correct
    for all fonts and styles), then trace it to vector paths using
    vtracer. This sidesteps all FreeType coordinate system issues.

    The skeleton PNG handles all font-specific positioning correctly.
    vtracer converts the bitmap contours to clean Bézier paths.
    Result: perfect vector output for any font, any style.
    """
    import tempfile
    import vtracer

    # Step 1 — render clean skeleton PNG at high resolution
    # Use a temporary file so we don't overwrite the main skeleton
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
        tmp_png = tmp.name

    try:
        # Render at larger size for better vector quality
        render_skeleton(
            text, font_path, tmp_png,
            font_size=font_size,
            dot_boost=1.0,     # no dot boost for vector — we want clean paths
            add_border=False   # no border for SVG output
        )

        # Step 2 — trace PNG to SVG
        vtracer.convert_image_to_svg_py(
            tmp_png,
            output_path,
            colormode    = 'binary',
            hierarchical = 'stacked',
            mode         = 'spline',
            filter_speckle    = 4,
            color_precision   = 6,
            layer_difference  = 16,
            corner_threshold  = 60,
            length_threshold  = 4.0,
            max_iterations    = 10,
            splice_threshold  = 45,
            path_precision    = 8
        )

        # Step 3 — inject fill color and metadata into SVG
        with open(output_path, 'r', encoding='utf-8') as f:
            svg_content = f.read()

        # Replace default black with our fill color
        svg_content = svg_content.replace(
            'fill="#000000"', f'fill="{fill_color}"'
        )

        # Inject title and description
        svg_content = svg_content.replace(
            '<svg ',
            '<svg xmlns:khatt="https://khatt-engine.onrender.com" '
        )

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(svg_content)

        print(f"SVG saved -> {output_path}")

    finally:
        import os
        if os.path.exists(tmp_png):
            os.unlink(tmp_png)
        # Also clean up the mask file created by render_skeleton
        mask = tmp_png.replace('.png', '_mask.png')
        if os.path.exists(mask):
            os.unlink(mask)

def render_skeleton(text, font_path, output_path,
                    font_size=140, dot_boost=1.15, add_border=True):
    """
    Renders Arabic text as a clean skeleton PNG for AI stylization.
    """
    blob    = hb.Blob.from_file_path(font_path)
    hb_face = hb.Face(blob)
    hb_font = hb.Font(hb_face)
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(hb_font, buf)
    infos     = buf.glyph_infos
    positions = buf.glyph_positions

    harakat_clusters = {
        i for i, ch in enumerate(text)
        if ord(ch) in HARAKAT_RANGE
    }
    if harakat_clusters:
        print(f"  Harakat at {len(harakat_clusters)} positions — "
              f"rendering in gray ({HARAKAT_GRAY}/255)")

    ft_face = freetype.Face(font_path)
    ft_face.set_char_size(font_size * 64)
    scale = font_size / ft_face.units_per_EM

    glyphs_data = []
    cursor_x    = 0.0
    baseline_y  = 500
    letter_pts  = []

    for info, pos in zip(infos, positions):
        adv_px       = pos.x_advance * scale
        off_x        = pos.x_offset  * scale
        off_y        = pos.y_offset  * scale
        is_diacritic = info.cluster in harakat_clusters

        ft_face.load_glyph(info.codepoint, freetype.FT_LOAD_RENDER)
        bm = ft_face.glyph.bitmap
        bl = ft_face.glyph.bitmap_left
        bt = ft_face.glyph.bitmap_top

        if bm.width > 0 and bm.rows > 0 and not is_diacritic:
            ox = cursor_x + bl + off_x
            oy = baseline_y - bt - off_y
            letter_pts.append((ox, oy, ox + bm.width, oy + bm.rows))

        glyphs_data.append((
            info.codepoint, adv_px, off_x, off_y, is_diacritic
        ))
        cursor_x += adv_px

    if not letter_pts:
        print("No letter glyphs found.")
        return

    ink_x1  = min(p[0] for p in letter_pts)
    ink_y1  = min(p[1] for p in letter_pts)
    ink_x2  = max(p[2] for p in letter_pts)
    ink_y2  = max(p[3] for p in letter_pts)
    body_y2 = min(baseline_y + font_size * 0.3, ink_y2)

    padding  = 55
    canvas_w = int(ink_x2 - ink_x1) + padding * 2
    canvas_h = int(body_y2 - ink_y1) + padding * 2
    min_h    = int(canvas_w * 0.65)
    if canvas_h < min_h:
        extra      = (min_h - canvas_h) // 2
        canvas_h   = min_h
        baseline_y += extra

    shift_x = -ink_x1 + padding
    shift_y = (-ink_y1 + padding +
               (canvas_h - int(body_y2 - ink_y1) - padding * 2) // 2)

    canvas = np.full((canvas_h, canvas_w), 255, dtype=np.uint8)

    cursor_x = 0.0
    for glyph_id, adv_px, off_x, off_y, is_diacritic in glyphs_data:
        ft_face.load_glyph(glyph_id, freetype.FT_LOAD_RENDER)
        bm = ft_face.glyph.bitmap
        bl = ft_face.glyph.bitmap_left
        bt = ft_face.glyph.bitmap_top

        if bm.width == 0 or bm.rows == 0:
            cursor_x += adv_px
            continue

        ox = int(cursor_x + bl + off_x + shift_x)
        oy = int(baseline_y - bt - off_y + shift_y)

        pitch     = abs(bm.pitch)
        raw       = np.frombuffer(
            bytes(bm.buffer[:bm.rows * pitch]), dtype=np.uint8
        )
        glyph_arr = raw.reshape(bm.rows, pitch)[:, :bm.width]

        x1 = max(0, ox);            y1 = max(0, oy)
        x2 = min(canvas_w, ox + bm.width)
        y2 = min(canvas_h, oy + bm.rows)

        if x1 >= x2 or y1 >= y2:
            cursor_x += adv_px
            continue

        glyph_crop = glyph_arr[y1-oy:y2-oy, x1-ox:x2-ox]

        if is_diacritic:
            alpha_f  = glyph_crop.astype(np.float32) / 255.0
            blended  = (255*(1-alpha_f) +
                        HARAKAT_GRAY*alpha_f).astype(np.uint8)
            canvas[y1:y2, x1:x2] = np.minimum(
                canvas[y1:y2, x1:x2], blended
            )
        else:
            canvas[y1:y2, x1:x2] = np.minimum(
                canvas[y1:y2, x1:x2], 255 - glyph_crop
            )

        cursor_x += adv_px

    if dot_boost > 1.0:
        canvas = _boost_dots(canvas, dot_boost)

    canvas_for_mask = canvas.copy()

    if add_border:
        canvas = add_frame(canvas)

    target_w = 1024
    ratio    = target_w / canvas.shape[1]
    target_h = int(canvas.shape[0] * ratio)

    img = Image.fromarray(canvas, mode='L').convert('RGB')
    img = img.resize((target_w, target_h), Image.LANCZOS)
    img.save(output_path)
    print(f"Saved -> {output_path} ({img.width}x{img.height})")

    mask_path = output_path.replace('.png', '_mask.png')
    mask_img  = Image.fromarray(canvas_for_mask, mode='L').convert('RGB')
    mask_img  = mask_img.resize((target_w, target_h), Image.LANCZOS)
    mask_img.save(mask_path)


def _boost_dots(canvas, boost_factor):
    dark         = canvas < 128
    labeled, num = ndimage.label(dark)
    boosted      = canvas.copy()

    for i in range(1, num + 1):
        region = labeled == i
        size   = region.sum()
        if 3 <= size <= 80:
            rows = np.where(region.any(axis=1))[0]
            cols = np.where(region.any(axis=0))[0]
            if len(rows) == 0 or len(cols) == 0:
                continue
            cy    = int((rows[0] + rows[-1]) / 2)
            cx    = int((cols[0] + cols[-1]) / 2)
            orig_r = max(rows[-1]-rows[0], cols[-1]-cols[0]) / 2
            new_r  = max(3, int(orig_r * boost_factor))
            h, w   = canvas.shape
            y_idx, x_idx = np.ogrid[:h, :w]
            circle = (y_idx - cy)**2 + (x_idx - cx)**2 <= new_r**2
            boosted[circle] = 0

    return boosted
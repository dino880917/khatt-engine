import freetype
import uharfbuzz as hb
import numpy as np
from PIL import Image
from scipy import ndimage

def render_skeleton(text, font_path, output_path, font_size=140, dot_boost=1.15):
    """
    Renders Arabic text as a clean skeleton image.
    dot_boost: multiplier for dot size so AI does not ignore them.
               1.0 = original size, 2.8 = nearly 3x larger dots.
    """

    # 1 — Shape with HarfBuzz
    blob    = hb.Blob.from_file_path(font_path)
    hb_face = hb.Face(blob)
    hb_font = hb.Font(hb_face)
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(hb_font, buf)
    infos     = buf.glyph_infos
    positions = buf.glyph_positions

    # 2 — Load FreeType
    ft_face = freetype.Face(font_path)
    ft_face.set_char_size(font_size * 64)
    scale = font_size / ft_face.units_per_EM
    print(f"Scale  : {scale:.4f} px per design unit")

    # 3 — First pass: measure real ink bounds
    glyphs_data = []
    cursor_x    = 0.0
    baseline_y  = 500
    pts = []

    for info, pos in zip(infos, positions):
        adv_px = pos.x_advance * scale
        off_x  = pos.x_offset  * scale
        off_y  = pos.y_offset  * scale

        ft_face.load_glyph(info.codepoint, freetype.FT_LOAD_RENDER)
        bm = ft_face.glyph.bitmap
        bl = ft_face.glyph.bitmap_left
        bt = ft_face.glyph.bitmap_top

        if bm.width > 0 and bm.rows > 0:
            ox = cursor_x + bl + off_x
            oy = baseline_y - bt - off_y
            pts.append((ox, oy, ox + bm.width, oy + bm.rows))

        glyphs_data.append((info.codepoint, adv_px, off_x, off_y))
        cursor_x += adv_px

    if not pts:
        print("No glyphs rendered.")
        return

    ink_x1 = min(p[0] for p in pts)
    ink_y1 = min(p[1] for p in pts)
    ink_x2 = max(p[2] for p in pts)
    ink_y2 = max(p[3] for p in pts)

    body_y2  = min(baseline_y + font_size * 0.3, ink_y2)
    padding  = 60
    canvas_w = int(ink_x2 - ink_x1) + padding * 2
    canvas_h = int(body_y2 - ink_y1) + padding * 2
    shift_x  = -ink_x1 + padding
    shift_y  = -ink_y1 + padding

    print(f"Canvas : {canvas_w} x {canvas_h} px")

    # 4 — White canvas
    canvas = np.full((canvas_h, canvas_w), 255, dtype=np.uint8)

    # 5 — Draw glyphs
    cursor_x = 0.0
    for glyph_id, adv_px, off_x, off_y in glyphs_data:
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
        raw       = np.frombuffer(bytes(bm.buffer[:bm.rows * pitch]), dtype=np.uint8)
        glyph_arr = raw.reshape(bm.rows, pitch)[:, :bm.width]

        x1 = max(0, ox);          y1 = max(0, oy)
        x2 = min(canvas_w, ox + bm.width)
        y2 = min(canvas_h, oy + bm.rows)

        if x1 >= x2 or y1 >= y2:
            cursor_x += adv_px
            continue

        glyph_crop = glyph_arr[y1-oy : y2-oy, x1-ox : x2-ox]
        canvas[y1:y2, x1:x2] = np.minimum(
            canvas[y1:y2, x1:x2],
            255 - glyph_crop
        )
        cursor_x += adv_px

    # 6 — Boost dot sizes so AI cannot ignore them
    if dot_boost > 1.0:
        canvas = _boost_dots(canvas, dot_boost)

    # 7 — Scale up to 1024px wide
    img      = Image.fromarray(canvas, mode='L').convert('RGB')
    target_w = 1024
    ratio    = target_w / img.width
    target_h = int(img.height * ratio)
    img      = img.resize((target_w, target_h), Image.LANCZOS)

    img.save(output_path)
    print(f"Saved  -> {output_path}  ({img.width}x{img.height})")


def _boost_dots(canvas, boost_factor):
    """
    Finds small isolated ink regions (dots) and expands them.
    Large letter bodies are left unchanged.
    The AI must then render them as part of the composition.
    """
    dark    = canvas < 128
    labeled, num = ndimage.label(dark)

    boosted = canvas.copy()

    for i in range(1, num + 1):
        region = labeled == i
        size   = region.sum()

        # Dots are small isolated regions — letter bodies are large
        # Threshold: anything under 600px is a dot or diacritic
        if 3 <= size <= 80:
            # Find bounding box of this dot
            rows = np.where(region.any(axis=1))[0]
            cols = np.where(region.any(axis=0))[0]
            if len(rows) == 0 or len(cols) == 0:
                continue

            cy = int((rows[0] + rows[-1]) / 2)
            cx = int((cols[0] + cols[-1]) / 2)

            # Calculate new radius based on boost factor
            orig_r = max(rows[-1] - rows[0], cols[-1] - cols[0]) / 2
            new_r  = max(3, int(orig_r * boost_factor))

            # Draw filled circle at same center
            h, w = canvas.shape
            y_idx, x_idx = np.ogrid[:h, :w]
            circle = (y_idx - cy) ** 2 + (x_idx - cx) ** 2 <= new_r ** 2
            boosted[circle] = 0

    return boosted


if __name__ == "__main__":
    render_skeleton(
        text        = "بسم الله",
        font_path   = "assets/fonts/Amiri-Regular.ttf",
        output_path = "outputs/skeleton_test.png",
        font_size   = 140,
        dot_boost   = 1.15,
    )
import freetype
import uharfbuzz as hb
import numpy as np
from PIL import Image
from scipy import ndimage

# Arabic harakat Unicode ranges
HARAKAT_RANGE = set(range(0x064B, 0x0660)) | {0x0670, 0x0671}
HARAKAT_GRAY  = 210   # gray level: 0=black, 255=white, 160=medium gray


def add_frame(canvas, frame_pad=18, outer_thick=3, gap=8, inner_thick=1):
    """
    Geometric double-border frame with diamond corner ornaments.
    Occupies empty space so the AI does not fill it with calligraphy.
    """
    result = canvas.copy()
    h, w   = result.shape
    p      = frame_pad

    def hline(y, x0, x1, t):
        result[max(0,y):min(h,y+t), max(0,x0):min(w,x1)] = 0

    def vline(x, y0, y1, t):
        result[max(0,y0):min(h,y1), max(0,x):min(w,x+t)] = 0

    # Outer rectangle
    hline(p,                 p, w-p, outer_thick)
    hline(h-p-outer_thick,   p, w-p, outer_thick)
    vline(p,                 p, h-p, outer_thick)
    vline(w-p-outer_thick,   p, h-p, outer_thick)

    # Inner rectangle
    i = p + gap + outer_thick
    hline(i,                 i, w-i, inner_thick)
    hline(h-i-inner_thick,   i, w-i, inner_thick)
    vline(i,                 i, h-i, inner_thick)
    vline(w-i-inner_thick,   i, h-i, inner_thick)

    # Diamond corner ornaments
    diamond_r = 5
    corners = [
        (p + gap//2 + outer_thick + 2,         p + gap//2 + outer_thick + 2),
        (p + gap//2 + outer_thick + 2,         w - p - gap//2 - outer_thick - 2),
        (h - p - gap//2 - outer_thick - 2,     p + gap//2 + outer_thick + 2),
        (h - p - gap//2 - outer_thick - 2,     w - p - gap//2 - outer_thick - 2),
    ]
    for cy, cx in corners:
        for dy in range(-diamond_r, diamond_r + 1):
            for dx in range(-diamond_r, diamond_r + 1):
                if abs(dy) + abs(dx) <= diamond_r:
                    ny, nx = cy + dy, cx + dx
                    if 0 <= ny < h and 0 <= nx < w:
                        result[ny, nx] = 0

    return result


def render_skeleton(text, font_path, output_path,
                    font_size=140, dot_boost=1.15, add_border=True):
    """
    Renders Arabic text as a clean skeleton for AI stylization.

    Harakat handling:
      HarfBuzz receives the full text including harakat — they are
      needed for correct shaping and letter connections. But harakat
      glyphs are rendered in gray (not black) so the AI treats them as
      secondary marks rather than primary ink, preventing ornamental
      hallucination triggered by shadda, fatha, etc.

    Empty space handling:
      Canvas is tightened around the ink bounding box and a minimum
      height is enforced to prevent flat wide compositions. The
      geometric frame occupies the remaining space with a neutral
      signal that tells the AI the composition is complete.
    """

    # 1 — Shape with HarfBuzz (full text including harakat)
    blob    = hb.Blob.from_file_path(font_path)
    hb_face = hb.Face(blob)
    hb_font = hb.Font(hb_face)
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(hb_font, buf)
    infos     = buf.glyph_infos
    positions = buf.glyph_positions

    # Identify which input character positions are harakat
    harakat_clusters = {
        i for i, ch in enumerate(text)
        if ord(ch) in HARAKAT_RANGE
    }
    if harakat_clusters:
        print(f"  Harakat at {len(harakat_clusters)} positions — "
              f"rendering in gray ({HARAKAT_GRAY}/255)")

    # 2 — Load FreeType
    ft_face = freetype.Face(font_path)
    ft_face.set_char_size(font_size * 64)
    scale = font_size / ft_face.units_per_EM
    print(f"Scale  : {scale:.4f} px per design unit")

    # 3 — First pass: measure LETTER BODY bounds only (not harakat)
    glyphs_data = []
    cursor_x    = 0.0
    baseline_y  = 500
    letter_pts  = []

    for info, pos in zip(infos, positions):
        adv_px      = pos.x_advance * scale
        off_x       = pos.x_offset  * scale
        off_y       = pos.y_offset  * scale
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

    ink_x1 = min(p[0] for p in letter_pts)
    ink_y1 = min(p[1] for p in letter_pts)
    ink_x2 = max(p[2] for p in letter_pts)
    ink_y2 = max(p[3] for p in letter_pts)

    body_y2  = min(baseline_y + font_size * 0.3, ink_y2)

    # Tighter padding — word fills more of the frame
    padding  = 55
    canvas_w = int(ink_x2 - ink_x1) + padding * 2
    canvas_h = int(body_y2 - ink_y1) + padding * 2

    # Enforce minimum height to avoid flat wide compositions
    # that invite the AI to fill vertical empty space
    min_h    = int(canvas_w * 0.65)
    if canvas_h < min_h:
        extra    = (min_h - canvas_h) // 2
        canvas_h = min_h
        baseline_y += extra   # shift letters down to stay centered

    shift_x  = -ink_x1 + padding
    shift_y  = -ink_y1 + padding + (canvas_h - int(body_y2 - ink_y1) - padding * 2) // 2

    print(f"Canvas : {canvas_w} x {canvas_h} px")

    # 4 — White canvas
    canvas = np.full((canvas_h, canvas_w), 255, dtype=np.uint8)

    # 5 — Render glyphs
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

        x1 = max(0, ox);           y1 = max(0, oy)
        x2 = min(canvas_w, ox + bm.width)
        y2 = min(canvas_h, oy + bm.rows)

        if x1 >= x2 or y1 >= y2:
            cursor_x += adv_px
            continue

        glyph_crop = glyph_arr[y1-oy : y2-oy, x1-ox : x2-ox]

        if is_diacritic:
            # Render harakat in gray — visually secondary to letter bodies
            # blend: result = 255*(1-alpha) + HARAKAT_GRAY*alpha
            alpha_f  = glyph_crop.astype(np.float32) / 255.0
            blended  = (255*(1-alpha_f) + HARAKAT_GRAY*alpha_f).astype(np.uint8)
            canvas[y1:y2, x1:x2] = np.minimum(
                canvas[y1:y2, x1:x2], blended
            )
        else:
            # Render letter bodies in black
            canvas[y1:y2, x1:x2] = np.minimum(
                canvas[y1:y2, x1:x2],
                255 - glyph_crop
            )

        cursor_x += adv_px

    # 6 — Boost letter dots (harakat already handled above)
    if dot_boost > 1.0:
        canvas = _boost_dots(canvas, dot_boost)

    # 7 — Geometric frame
    if add_border:
        canvas = add_frame(canvas)

    # 8 — Scale to 1024px wide
    img      = Image.fromarray(canvas, mode='L').convert('RGB')
    target_w = 1024
    ratio    = target_w / img.width
    target_h = int(img.height * ratio)
    img      = img.resize((target_w, target_h), Image.LANCZOS)

    img.save(output_path)
    print(f"Saved  -> {output_path}  ({img.width}x{img.height})")


def _boost_dots(canvas, boost_factor):
    """
    Enlarges small isolated ink regions (letter dots).
    Only affects regions under 80px — letter bodies are much larger.
    Harakat are already gray so _boost_dots ignores them naturally
    (gray pixels are > 128 and are not treated as ink).
    """
    dark         = canvas < 128    # only pure black ink
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


if __name__ == "__main__":
    # Test with a heavily voweled word to verify gray harakat rendering
    render_skeleton(
        text        = "عَزَّام",
        font_path   = "assets/fonts/Amiri-Regular.ttf",
        output_path = "outputs/skeleton_test.png",
        font_size   = 140,
        dot_boost   = 1.15,
        add_border  = True,
    )
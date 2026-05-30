import freetype
import uharfbuzz as hb
import numpy as np
import re
from PIL import Image
from scipy import ndimage


def strip_harakat(text):
    """
    Remove Arabic diacritical marks (harakat) from text before rendering.

    Why: HarfBuzz already used harakat for shaping — they determined
    contextual forms and connections. Once shaping is done they have
    served their purpose. Keeping them in the skeleton creates small
    isolated marks that the AI misreads as ornamental stamps, medallions,
    and decorative seals — triggering hallucinated compositions.

    Removes: fatha, damma, kasra, tanwin variants, shadda, sukun,
             superscript alef, wasla, and all other harakat.
    Does NOT remove: base letter codepoints or letter dots.
    """
    return re.sub(r'[\u064B-\u065F\u0670\u0671]', '', text)


def add_frame(canvas, frame_pad=22, outer_thick=3, gap=9, inner_thick=1):
    """
    Add a clean geometric frame around the calligraphic text.

    Why: A large white canvas with a small word in the center invites
    the AI to fill the empty space with calligraphic context — secondary
    text, decorative borders, bismillah lines. The frame occupies that
    space with a neutral geometric signal that tells the AI:
    'the composition boundary is here, do not add content outside it.'

    The frame is purely geometric (not calligraphic) so it does not
    give the AI more calligraphic patterns to extend or complete.
    """
    result = canvas.copy()
    h, w   = result.shape
    p      = frame_pad

    def hline(y, x0, x1, t):
        result[max(0,y):min(h,y+t), max(0,x0):min(w,x1)] = 0

    def vline(x, y0, y1, t):
        result[max(0,y0):min(h,y1), max(0,x):min(w,x+t)] = 0

    # Outer rectangle
    hline(p,           p, w-p, outer_thick)
    hline(h-p-outer_thick, p, w-p, outer_thick)
    vline(p,           p, h-p, outer_thick)
    vline(w-p-outer_thick, p, h-p, outer_thick)

    # Inner rectangle
    i = p + gap + outer_thick
    hline(i,           i, w-i, inner_thick)
    hline(h-i-inner_thick, i, w-i, inner_thick)
    vline(i,           i, h-i, inner_thick)
    vline(w-i-inner_thick, i, h-i, inner_thick)

    # Corner diamond ornaments — sits between outer and inner borders
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
    Renders Arabic text as a clean skeleton image ready for AI stylization.

    Pipeline:
      1. Strip harakat (diacritics) — prevents ornamental hallucination
      2. HarfBuzz shaping — linguistically correct glyph sequence
      3. FreeType rendering — precise Bézier bitmap
      4. Dot boost — ensures letter dots are not ignored by AI
      5. Geometric frame — reduces empty-space hallucination
      6. Scale to 1024px — optimal for Stability AI input
    """

    # Fix 1 — strip harakat before anything else
    clean_text = strip_harakat(text)
    if clean_text != text:
        stripped = [c for c in text if c not in clean_text or
                    re.match(r'[\u064B-\u065F\u0670\u0671]', c)]
        print(f"  Harakat stripped from input")

    # 1 — Shape with HarfBuzz
    blob    = hb.Blob.from_file_path(font_path)
    hb_face = hb.Face(blob)
    hb_font = hb.Font(hb_face)
    buf = hb.Buffer()
    buf.add_str(clean_text)
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
    pts         = []

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

    # Generous padding so the frame has room
    padding  = 90
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
        canvas[y1:y2, x1:x2] = np.minimum(
            canvas[y1:y2, x1:x2],
            255 - glyph_crop
        )
        cursor_x += adv_px

    # Fix 1 cont. — boost letter dots (not diacritics, those were stripped)
    if dot_boost > 1.0:
        canvas = _boost_dots(canvas, dot_boost)

    # Fix 2 — add geometric frame to reduce empty-space hallucination
    if add_border:
        canvas = add_frame(canvas)

    # 6 — Scale to 1024px wide
    img      = Image.fromarray(canvas, mode='L').convert('RGB')
    target_w = 1024
    ratio    = target_w / img.width
    target_h = int(img.height * ratio)
    img      = img.resize((target_w, target_h), Image.LANCZOS)

    img.save(output_path)
    print(f"Saved  -> {output_path}  ({img.width}x{img.height})")


def _boost_dots(canvas, boost_factor):
    """
    Enlarges small isolated ink regions (letter dots) so the AI
    cannot treat them as noise and ignore them.
    Only affects regions under 80px — well below any letter body size.
    """
    dark             = canvas < 128
    labeled, num     = ndimage.label(dark)
    boosted          = canvas.copy()

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

            h, w    = canvas.shape
            y_idx, x_idx = np.ogrid[:h, :w]
            circle  = (y_idx - cy)**2 + (x_idx - cx)**2 <= new_r**2
            boosted[circle] = 0

    return boosted


if __name__ == "__main__":
    render_skeleton(
        text        = "عزام",
        font_path   = "assets/fonts/Amiri-Regular.ttf",
        output_path = "outputs/skeleton_test.png",
        font_size   = 140,
        dot_boost   = 1.15,
        add_border  = True,
    )
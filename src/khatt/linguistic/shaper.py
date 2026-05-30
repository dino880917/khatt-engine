import uharfbuzz as hb

def shape_arabic(text, font_path):
    blob = hb.Blob.from_file_path(font_path)
    face = hb.Face(blob)
    font = hb.Font(face)
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(font, buf)
    glyphs = []
    for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
        glyphs.append({
            "glyph_id":  info.codepoint,
            "cluster":   info.cluster,
            "x_advance": pos.x_advance,
        })
    return glyphs

if __name__ == "__main__":
    font_path = "assets\\fonts\\Amiri-Regular.ttf"
    text = "بسم الله"
    result = shape_arabic(text, font_path)
    print(f"Input: {text}")
    print(f"Shaped glyphs: {len(result)}")
    for i, g in enumerate(result):
        print(f"  Glyph {i}: id={g['glyph_id']}  advance={g['x_advance']}")
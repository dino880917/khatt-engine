from khatt.geometry.skeleton import render_skeleton

# Test Ruqah without border
render_skeleton(
    text        = "عَزَّام",
    font_path   = "assets/fonts/ArefRuqaa-Regular.ttf",
    output_path = "outputs/skeleton_test.png",
    font_size   = 140,
    add_border  = False,
)
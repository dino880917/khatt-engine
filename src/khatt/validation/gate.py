import easyocr
import re
from PIL import Image

_reader = None

def get_reader():
    global _reader
    if _reader is None:
        print("Loading Arabic OCR model...")
        _reader = easyocr.Reader(['ar'], gpu=False, verbose=False)
    return _reader

def levenshtein(s1, s2):
    if len(s1) < len(s2):
        return levenshtein(s2, s1)
    if len(s2) == 0:
        return len(s1)
    prev = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        curr = [i + 1]
        for j, c2 in enumerate(s2):
            curr.append(min(prev[j+1]+1, curr[j]+1, prev[j]+(c1 != c2)))
        prev = curr
    return prev[-1]

def normalize_arabic(text):
    text = re.sub(r'[^\u0600-\u06FF]', '', text)
    return text.strip()

def sort_chars(text):
    return ''.join(sorted(text))

def preprocess_for_ocr(image_path, temp_path="outputs\\ocr_temp.png"):
    img = Image.open(image_path).convert("RGB")
    orig_w, orig_h = img.size
    target_w = 800
    if orig_w > target_w:
        ratio = target_w / orig_w
        img   = img.resize((target_w, int(orig_h * ratio)), Image.LANCZOS)
    img.save(temp_path)
    return temp_path

def validate_output(skeleton_path, expected_text, threshold=0.35):
    print(f"Validating          : {skeleton_path}")
    print(f"Expected            : {expected_text}")

    temp_path = preprocess_for_ocr(skeleton_path)
    reader    = get_reader()
    results   = reader.readtext(temp_path, detail=0, paragraph=False)

    detected_raw = " ".join(results)
    detected     = normalize_arabic(detected_raw)
    expected     = normalize_arabic(expected_text)

    print(f"Detected (Arabic)   : {detected}")
    print(f"Expected (Arabic)   : {expected}")

    if len(expected) == 0:
        return False, 0.0, detected_raw

    dist  = levenshtein(sort_chars(expected), sort_chars(detected))
    score = 1.0 - (dist / max(len(expected), len(detected)))

    print(f"Similarity score    : {score:.2f}  (threshold: {threshold})")
    passed = score >= threshold
    print(f"Validation result   : {'PASSED' if passed else 'FAILED'}")
    return passed, score, detected_raw
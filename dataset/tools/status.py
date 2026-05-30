"""
Shows the current state of the dataset collection.
Run this any time to see how many images you have per style.

Usage:
    python dataset/tools/status.py
"""

import json
from pathlib import Path
from collections import Counter

RAW_DIR = Path("dataset/raw")

print("\n" + "="*55)
print("  Khatt Engine — Dataset Status")
print("="*55)

# Count raw images per style
total = 0
print("\nRaw images collected:")
for style_dir in sorted(RAW_DIR.iterdir()):
    if style_dir.is_dir():
        images = list(style_dir.glob("*.jpg")) + \
                 list(style_dir.glob("*.png"))
        count  = len(images)
        total += count
        bar    = "█" * (count // 5) + "░" * max(0, 20 - count // 5)
        target_pct = min(100, int(count / 500 * 100))
        print(f"  {style_dir.name:12} {bar} {count:4d} / 500"
              f"  ({target_pct}%)")

print(f"\n  Total collected : {total}")
print(f"  Target (MVP)    : 3000  (500 per style)")
print(f"  Target (full)   : 12000 (2000 per style)")

# Labeling progress
labeled_file = Path("dataset/labeled/annotations.json")
if labeled_file.exists():
    with open(labeled_file, "r", encoding="utf-8") as f:
        labeled = json.load(f)
    transcribed = sum(1 for r in labeled if r.get("transcription"))
    print(f"\nLabeling progress:")
    print(f"  Transcribed     : {transcribed}")
    print(f"  Target (OCR)    : 5000 (early model)")
    print(f"  Target (full)   : 50000 (robust model)")
else:
    print(f"\nLabeling: not started yet")

print()
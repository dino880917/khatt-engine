"""
Metropolitan Museum of Art — Arabic Calligraphy Collector
Uses the Met's public CSV collection export for filtering.

Usage:
    python dataset/tools/fetch_met.py --style all --limit 100
    python dataset/tools/fetch_met.py --style naskh --limit 50
"""

import time
import json
import argparse
import csv
import requests
from pathlib import Path
from collections import Counter

BASE_URL  = "https://collectionapi.metmuseum.org/public/collection/v1"
CSV_URL   = "https://media.githubusercontent.com/media/metmuseum/openaccess/master/MetObjects.csv"
RAW_DIR   = Path("dataset/raw")
META_FILE = Path("dataset/met_metadata.json")
CSV_CACHE = Path("dataset/met_objects.csv")

# Expanded keywords — catches far more calligraphic works
STYLE_KEYWORDS = {
    "kufic": [
        "kufic", "koran fragment", "quran fragment",
        "umayyad", "early islamic inscription",
        "floriated kufic", "foliated kufic",
        "square kufic", "eastern kufic",
    ],
    "naskh": [
        "naskh", "quran leaf", "quran page",
        "leaf from a quran", "quranic leaf",
        "mamluk quran", "manuscript leaf", "manuscript folio",
        "folio from a quran", "bifolio", "ink on paper",
        "illuminated quran", "arabic manuscript",
    ],
    "thuluth": [
        "thuluth", "calligraphic panel",
        "calligraphy panel", "calligraphic composition",
        "calligraphic roundel", "calligraphic medallion",
        "inscribed panel", "arabic inscription panel",
        "calligraphic plaque",
    ],
    "nastaliq": [
        "nastaliq", "nasta'liq", "safavid calligraphy",
        "persian calligraphy", "persian manuscript",
        "timurid", "persian poetry", "divan manuscript",
        "shahnama", "album leaf persian",
    ],
    "diwani": [
        "diwani", "ottoman calligraphy",
        "ottoman script", "imperial ottoman",
        "firman", "tughra", "ottoman imperial",
        "ottoman document", "ottoman decree",
    ],
    "ruqah": [
        "ruqah", "ruq'ah", "arabic calligraphy",
        "islamic calligraphy", "arabic writing",
        "ottoman letter", "arabic letter",
        "calligraphic exercise",
    ],
}

# Expanded script signals — catches unlabeled calligraphic works
SCRIPT_SIGNALS = [
    "calligraph", "manuscript", "inscription", "quran", "koran",
    "script", "writing", "text", "letter", "folio", "leaf",
    "kufic", "naskh", "thuluth", "nastaliq", "diwani", "ruqah",
    "tughra", "firman", "ink on paper", "ink on vellum",
    "illuminated", "bifolio", "roundel", "medallion",
    "arabic", "persian", "ottoman", "islamic art",
]


def download_csv():
    if CSV_CACHE.exists():
        size_mb = CSV_CACHE.stat().st_size / 1024 / 1024
        print(f"Using cached CSV ({size_mb:.1f} MB): {CSV_CACHE}")
        return CSV_CACHE

    print("Downloading Met collection CSV (~300 MB, one-time)...")
    try:
        r = requests.get(CSV_URL, timeout=120, stream=True)
        if r.status_code == 200:
            total = 0
            with open(CSV_CACHE, "wb") as f:
                for chunk in r.iter_content(65536):
                    f.write(chunk)
                    total += len(chunk)
                    if total % (10 * 1024 * 1024) == 0:
                        print(f"  Downloaded {total // 1024 // 1024} MB...")
            print(f"CSV saved to {CSV_CACHE}")
            return CSV_CACHE
        else:
            print(f"CSV download failed: {r.status_code}")
    except Exception as e:
        print(f"CSV download error: {e}")
    return None


def classify_row(row):
    """
    Classify a CSV row into a calligraphic style.
    Uses expanded script signals to catch unlabeled works.
    """
    text = " ".join([
        row.get("Title",          ""),
        row.get("Medium",         ""),
        row.get("Culture",        ""),
        row.get("Period",         ""),
        row.get("Classification", ""),
        row.get("Object Name",    ""),
        row.get("Tags",           ""),
        row.get("Department",     ""),
    ]).lower()

    # Must be in Islamic Art department
    dept = row.get("Department", "")
    if "islamic" not in dept.lower():
        return None

    # Must be public domain
    if row.get("Is Public Domain", "").strip() != "True":
        return None

    # Must contain at least one script signal
    if not any(s in text for s in SCRIPT_SIGNALS):
        return None

    # Classify by style — most specific first
    priority = ["kufic", "nastaliq", "thuluth", "naskh", "diwani", "ruqah"]
    for style in priority:
        if any(kw in text for kw in STYLE_KEYWORDS[style]):
            return style

    # If it passed signal check but no specific style matched,
    # classify as naskh (most common Islamic manuscript script)
    if any(s in text for s in ["manuscript", "quran", "folio", "leaf",
                                "ink on paper", "illuminated", "bifolio"]):
        return "naskh"

    return None


def scan_csv(csv_path, target_styles, limit_per_style):
    print("Scanning CSV for calligraphic objects...")
    results = {s: [] for s in target_styles}
    counts  = Counter()

    with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if i % 50000 == 0 and i > 0:
                print(f"  Scanned {i:,} rows... {dict(counts)}")

            if all(counts[s] >= limit_per_style * 3 for s in target_styles):
                break

            style = classify_row(row)
            if style and style in target_styles:
                if counts[style] < limit_per_style * 3:
                    results[style].append(row)
                    counts[style] += 1

    print("CSV scan complete. Found:")
    for s, rows in results.items():
        print(f"  {s:12} : {len(rows)} candidates")
    return results


def get_image_url(obj_id):
    try:
        r = requests.get(f"{BASE_URL}/objects/{obj_id}", timeout=15)
        if r.status_code == 200:
            obj = r.json()
            url = obj.get("primaryImage") or obj.get("primaryImageSmall")
            return url, obj
    except Exception:
        pass
    return None, None


def download_image(url, dest):
    try:
        r = requests.get(url, timeout=60, stream=True)
        if r.status_code == 200:
            with open(dest, "wb") as f:
                for chunk in r.iter_content(8192):
                    f.write(chunk)
            return True
    except Exception as e:
        print(f"    Download error: {e}")
    return False


def run(target_styles, limit_per_style):
    # Load existing metadata
    all_metadata = []
    if META_FILE.exists():
        with open(META_FILE, "r", encoding="utf-8") as f:
            all_metadata = json.load(f)
        print(f"Loaded {len(all_metadata)} existing records.")

    existing_ids = {r["id"] for r in all_metadata}
    collected    = Counter(r["style"] for r in all_metadata)
    remaining    = {
        s: limit_per_style - collected.get(s, 0)
        for s in target_styles
    }
    remaining = {s: v for s, v in remaining.items() if v > 0}

    if not remaining:
        print("All targets met. Nothing to collect.")
        return

    # Download or load CSV
    csv_path = download_csv()
    if not csv_path:
        print("Cannot proceed without CSV.")
        return

    # Scan CSV
    candidates = scan_csv(csv_path, list(remaining.keys()), limit_per_style)

    # Create output directories
    for style in target_styles:
        (RAW_DIR / style).mkdir(parents=True, exist_ok=True)

    # Download images
    for style, rows in candidates.items():
        need = remaining.get(style, 0)
        if need <= 0:
            continue

        print(f"\n{'='*50}")
        print(f"Downloading: {style}  (need {need})")
        print(f"{'='*50}")
        got = 0

        for row in rows:
            if got >= need:
                break

            obj_id = row.get("Object ID", "").strip()
            if not obj_id:
                continue

            rec_id = f"met_{obj_id}"
            if rec_id in existing_ids:
                continue

            img_url, obj = get_image_url(obj_id)
            if not img_url:
                time.sleep(0.2)
                continue

            dest  = RAW_DIR / style / f"{rec_id}.jpg"
            title = row.get("Title", "")[:60]
            print(f"  {rec_id}: {title}")

            if download_image(img_url, dest):
                record = {
                    "id":            rec_id,
                    "source":        "metropolitan_museum",
                    "style":         style,
                    "license":       "CC0",
                    "url":           img_url,
                    "object_url":    f"https://www.metmuseum.org/art/collection/search/{obj_id}",
                    "title":         row.get("Title",       ""),
                    "date":          row.get("Object Date", ""),
                    "medium":        row.get("Medium",      ""),
                    "culture":       row.get("Culture",     ""),
                    "period":        row.get("Period",      ""),
                    "department":    row.get("Department",  ""),
                    "filename":      f"{rec_id}.jpg",
                    "transcription": "",
                    "caption":       "",
                }
                all_metadata.append(record)
                existing_ids.add(rec_id)
                got += 1
                print(f"    Saved {got}/{need}")

                # Save after every download
                with open(META_FILE, "w", encoding="utf-8") as f:
                    json.dump(all_metadata, f,
                              ensure_ascii=False, indent=2)

            time.sleep(0.25)

    # Final summary
    print(f"\nTotal records: {len(all_metadata)}")
    counts = Counter(r["style"] for r in all_metadata)
    for s, c in sorted(counts.items()):
        print(f"  {s:12} : {c}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--style", default="all",
        help="thuluth/naskh/kufic/nastaliq/diwani/ruqah/all"
    )
    parser.add_argument(
        "--limit", type=int, default=100,
        help="Max images per style"
    )
    args = parser.parse_args()

    all_styles = list(STYLE_KEYWORDS.keys())
    styles = all_styles if args.style == "all" else [args.style]
    run(styles, args.limit)
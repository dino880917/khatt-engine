"""
Metropolitan Museum of Art — Arabic Calligraphy Collector
Uses the Met's public CSV collection export instead of the broken
department API endpoint.

The CSV contains every object with department, title, medium, etc.
We filter locally for Islamic Art calligraphy, then fetch images.

Usage:
    python dataset/tools/fetch_met.py --style all --limit 50
"""

import time
import json
import argparse
import csv
import io
import requests
from pathlib import Path
from collections import Counter

BASE_URL  = "https://collectionapi.metmuseum.org/public/collection/v1"
CSV_URL   = "https://media.githubusercontent.com/media/metmuseum/openaccess/master/MetObjects.csv"
RAW_DIR   = Path("dataset/raw")
META_FILE = Path("dataset/met_metadata.json")
CSV_CACHE = Path("dataset/met_objects.csv")

STYLE_KEYWORDS = {
    "kufic":    ["kufic", "koran fragment", "quran fragment",
                 "umayyad", "early islamic inscription"],
    "naskh":    ["naskh", "quran leaf", "quran page",
                 "leaf from a quran", "quranic leaf",
                 "mamluk quran", "manuscript leaf"],
    "thuluth":  ["thuluth", "calligraphic panel",
                 "calligraphy panel", "calligraphic composition"],
    "nastaliq": ["nastaliq", "nasta'liq", "safavid calligraphy",
                 "persian calligraphy", "persian manuscript"],
    "diwani":   ["diwani", "ottoman calligraphy",
                 "ottoman script", "tughra"],
    "ruqah":    ["ruqah", "ruq'ah", "arabic calligraphy",
                 "islamic calligraphy"],
}

def download_csv():
    """Download the Met collection CSV (cached locally)."""
    if CSV_CACHE.exists():
        size_mb = CSV_CACHE.stat().st_size / 1024 / 1024
        print(f"Using cached CSV ({size_mb:.1f} MB): {CSV_CACHE}")
        return CSV_CACHE

    print("Downloading Met collection CSV (~240 MB, one-time download)...")
    print("This will take a few minutes...")

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
    Returns style name or None.
    """
    text = " ".join([
        row.get("Title", ""),
        row.get("Medium", ""),
        row.get("Culture", ""),
        row.get("Period", ""),
        row.get("Classification", ""),
        row.get("Object Name", ""),
        row.get("Tags", ""),
    ]).lower()

    # Must be in Islamic Art department
    dept = row.get("Department", "")
    if "islamic" not in dept.lower():
        return None

    # Must have an image (Is Public Domain = True)
    if row.get("Is Public Domain", "").strip() != "True":
        return None

    # Classify by style keywords
    priority = ["kufic", "nastaliq", "thuluth",
                "naskh", "diwani", "ruqah"]
    for style in priority:
        if any(kw in text for kw in STYLE_KEYWORDS[style]):
            return style

    return None

def scan_csv(csv_path, target_styles, limit_per_style):
    """
    Read the CSV and collect object IDs per style.
    Returns dict: {style: [list of row dicts]}
    """
    print(f"Scanning CSV for calligraphic objects...")
    results = {s: [] for s in target_styles}
    counts  = Counter()

    with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if i % 50000 == 0 and i > 0:
                print(f"  Scanned {i:,} rows... {dict(counts)}")

            # Stop early if all styles satisfied
            if all(counts[s] >= limit_per_style * 3
                   for s in target_styles):
                break

            style = classify_row(row)
            if style and style in target_styles:
                if counts[style] < limit_per_style * 3:
                    results[style].append(row)
                    counts[style] += 1

    print(f"CSV scan complete. Found:")
    for s, rows in results.items():
        print(f"  {s:12} : {len(rows)} candidates")
    return results

def get_image_url(obj_id):
    """Fetch the image URL for one object from the API."""
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
    remaining    = {s: limit_per_style - collected.get(s, 0)
                    for s in target_styles}
    remaining    = {s: v for s, v in remaining.items() if v > 0}

    if not remaining:
        print("All targets met. Nothing to collect.")
        return

    # Download or load the CSV
    csv_path = download_csv()
    if not csv_path:
        print("Cannot proceed without CSV. Trying direct API fallback...")
        _fallback_direct_api(target_styles, limit_per_style,
                             all_metadata, existing_ids)
        return

    # Scan CSV for candidates
    candidates = scan_csv(csv_path, list(remaining.keys()),
                          limit_per_style)

    # Create output dirs
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

            obj_id  = row.get("Object ID", "").strip()
            if not obj_id:
                continue

            rec_id = f"met_{obj_id}"
            if rec_id in existing_ids:
                continue

            img_url, obj = get_image_url(obj_id)
            if not img_url:
                time.sleep(0.2)
                continue

            dest = RAW_DIR / style / f"{rec_id}.jpg"
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
                    "title":         row.get("Title", ""),
                    "date":          row.get("Object Date", ""),
                    "medium":        row.get("Medium", ""),
                    "culture":       row.get("Culture", ""),
                    "period":        row.get("Period", ""),
                    "department":    row.get("Department", ""),
                    "filename":      f"{rec_id}.jpg",
                    "transcription": "",
                    "caption":       "",
                }
                all_metadata.append(record)
                existing_ids.add(rec_id)
                got += 1
                print(f"    Saved {got}/{need}")

                with open(META_FILE, "w", encoding="utf-8") as f:
                    json.dump(all_metadata, f,
                              ensure_ascii=False, indent=2)
            time.sleep(0.25)

    # Final summary
    print(f"\nTotal records: {len(all_metadata)}")
    counts = Counter(r["style"] for r in all_metadata)
    for s, c in sorted(counts.items()):
        print(f"  {s:12} : {c}")


def _fallback_direct_api(styles, limit, all_metadata, existing_ids):
    """
    Fallback: try known calligraphy object IDs directly.
    These are real Met Islamic Art calligraphy objects.
    """
    KNOWN = [
        459055, 444835, 444836, 444837, 444838, 444839,
        444840, 444841, 444842, 444843, 444844, 444845,
        327731, 327732, 327733, 327734, 327735, 327736,
        453188, 453189, 453190, 453191, 453192, 453193,
        444391, 444392, 444393, 444394, 444395, 444396,
        739088, 739089, 739090, 739091, 739092, 739093,
        452688, 452689, 452690, 452691, 452692, 452693,
    ]

    print(f"Trying {len(KNOWN)} known object IDs...")
    downloaded = 0

    for obj_id in KNOWN:
        if downloaded >= limit:
            break

        rec_id = f"met_{obj_id}"
        if rec_id in existing_ids:
            continue

        try:
            r = requests.get(f"{BASE_URL}/objects/{obj_id}", timeout=15)
            if r.status_code != 200:
                continue
            obj = r.json()
        except Exception:
            continue

        img_url = obj.get("primaryImage") or obj.get("primaryImageSmall")
        if not img_url:
            time.sleep(0.2)
            continue

        dept = obj.get("department", "")
        if "islamic" not in dept.lower():
            time.sleep(0.1)
            continue

        style = "naskh"  # default for fallback
        title = obj.get("title", "").lower()
        if "kufic" in title:
            style = "kufic"
        elif "thuluth" in title:
            style = "thuluth"
        elif "nastaliq" in title or "persian" in title:
            style = "nastaliq"

        if style not in styles:
            continue

        (RAW_DIR / style).mkdir(parents=True, exist_ok=True)
        dest = RAW_DIR / style / f"{rec_id}.jpg"

        print(f"  [{style}] {rec_id}: {obj.get('title','')[:50]}")

        try:
            ri = requests.get(img_url, timeout=60, stream=True)
            if ri.status_code == 200:
                with open(dest, "wb") as f:
                    for chunk in ri.iter_content(8192):
                        f.write(chunk)
                record = {
                    "id":            rec_id,
                    "source":        "metropolitan_museum",
                    "style":         style,
                    "license":       "CC0" if obj.get("isPublicDomain")
                                     else "unknown",
                    "url":           img_url,
                    "title":         obj.get("title", ""),
                    "date":          obj.get("objectDate", ""),
                    "medium":        obj.get("medium", ""),
                    "culture":       obj.get("culture", ""),
                    "filename":      f"{rec_id}.jpg",
                    "transcription": "",
                    "caption":       "",
                }
                all_metadata.append(record)
                existing_ids.add(rec_id)
                downloaded += 1
                print(f"    Saved ({downloaded})")

                with open(META_FILE, "w", encoding="utf-8") as f:
                    json.dump(all_metadata, f,
                              ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"    Error: {e}")

        time.sleep(0.3)

    print(f"Fallback complete. Downloaded {downloaded} images.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--style",  default="all")
    parser.add_argument("--limit",  type=int, default=50)
    args = parser.parse_args()

    all_styles = list(STYLE_KEYWORDS.keys())
    styles = all_styles if args.style == "all" else [args.style]
    run(styles, args.limit)
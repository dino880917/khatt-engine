"""
Harvard Art Museums — Arabic Calligraphy Collector
Free API, CC0 licensed images, stable connection.

Usage:
    python dataset/tools/fetch_harvard.py --key YOUR_KEY --style all --limit 100
    python dataset/tools/fetch_harvard.py --key YOUR_KEY --style diwani --limit 100
"""

import time
import json
import argparse
import requests
from pathlib import Path
from collections import Counter

RAW_DIR   = Path("dataset/raw")
META_FILE = Path("dataset/harvard_metadata.json")

HEADERS = {
    "User-Agent": "KhattEngine/1.0 (Arabic calligraphy research)"
}

BASE_URL = "https://api.harvardartmuseums.org"

STYLE_QUERIES = {
    "naskh": [
        "naskh", "quran manuscript", "arabic manuscript",
        "quranic folio", "islamic manuscript",
    ],
    "thuluth": [
        "thuluth", "calligraphic panel", "arabic calligraphy",
    ],
    "nastaliq": [
        "nastaliq", "persian calligraphy", "safavid manuscript",
    ],
    "diwani": [
        "ottoman calligraphy", "tughra", "firman",
        "ottoman document", "islamic calligraphy",
        "arabic calligraphy panel", "calligraphy",
    ],
    "kufic": [
        "kufic", "early islamic", "kufic inscription",
        "kufic calligraphy", "kufi",
    ],
    "ruqah": [
        "arabic calligraphy", "islamic calligraphy",
        "arabic script", "calligraphy",
        "arabic writing",
    ],
}


def search_objects(query, api_key, page=1, size=100):
    params = {
        "q":              query,
        "classification": "Calligraphy",
        "hasimage":       1,
        "size":           size,
        "page":           page,
        "fields":         "id,title,dated,culture,medium,primaryimageurl,url",
        "culture":        "Islamic|Persian|Ottoman|Arabic|Iranian|Mughal|Turkish|Mamluk|Safavid|Timurid",
        "apikey":         api_key,
    }
    try:
        r = requests.get(
            f"{BASE_URL}/object",
            params=params,
            headers=HEADERS,
            timeout=20
        )
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"    Search error: {e}")
    return None


def download_image(url, dest):
    try:
        r = requests.get(url, timeout=60, stream=True, headers=HEADERS)
        if r.status_code == 200:
            with open(dest, "wb") as f:
                for chunk in r.iter_content(8192):
                    f.write(chunk)
            return True
    except Exception as e:
        print(f"    Download error: {e}")
    return False


def collect_style(style, api_key, limit, existing_ids):
    out_dir = RAW_DIR / style
    out_dir.mkdir(parents=True, exist_ok=True)

    queries    = STYLE_QUERIES.get(style, [])
    metadata   = []
    downloaded = 0

    for query in queries:
        if downloaded >= limit:
            break

        print(f"  Searching: '{query}'")
        result = search_objects(query, api_key)
        if not result:
            continue

        records = result.get("records", [])
        print(f"  Found {len(records)} objects")

        for obj in records:
            if downloaded >= limit:
                break

            obj_id  = str(obj.get("id", ""))
            img_url = obj.get("primaryimageurl", "")
            if not img_url or not obj_id:
                continue

            rec_id = f"harvard_{obj_id}"
            if rec_id in existing_ids:
                downloaded += 1
                continue

            dest = out_dir / f"{rec_id}.jpg"
            if dest.exists():
                downloaded += 1
                continue
            # Skip non-Islamic calligraphy
            culture = (obj.get("culture") or "").lower()
            islamic_cultures = [
                "islamic", "persian", "ottoman", "arabic",
                "iranian", "mughal", "turkish", "mamluk",
                "safavid", "timurid", "arab", "moroccan",
                "egyptian", "syrian", "indian muslim",
            ]
            if not any(c in culture for c in islamic_cultures):
                print(f"  Skipping non-Islamic: {culture}")
                continue

            title = (obj.get("title") or "")[:55]
            print(f"  [{style}] {rec_id}: {title}")

            if download_image(img_url, dest):
                metadata.append({
                    "id":            rec_id,
                    "source":        "harvard_art_museums",
                    "style":         style,
                    "license":       "CC0",
                    "url":           img_url,
                    "title":         obj.get("title", ""),
                    "dated":         obj.get("dated", ""),
                    "culture":       obj.get("culture", ""),
                    "medium":        obj.get("medium", ""),
                    "filename":      f"{rec_id}.jpg",
                    "transcription": "",
                    "caption":       "",
                })
                downloaded += 1
                print(f"    Saved ({downloaded}/{limit})")

            time.sleep(0.3)

    return metadata


def run(api_key, styles, limit):
    all_metadata = []
    if META_FILE.exists():
        with open(META_FILE, "r", encoding="utf-8") as f:
            all_metadata = json.load(f)
        print(f"Loaded {len(all_metadata)} existing records.")

    existing_ids = {r["id"] for r in all_metadata}

    for style in styles:
        print(f"\n{'='*50}")
        print(f"Collecting from Harvard: {style}  (limit={limit})")
        print(f"{'='*50}")
        new = collect_style(style, api_key, limit, existing_ids)
        new = [r for r in new if r["id"] not in existing_ids]
        all_metadata.extend(new)
        existing_ids.update(r["id"] for r in new)
        print(f"  Added {len(new)} records for {style}")

    with open(META_FILE, "w", encoding="utf-8") as f:
        json.dump(all_metadata, f, ensure_ascii=False, indent=2)

    counts = Counter(r["style"] for r in all_metadata)
    print(f"\nTotal from Harvard: {len(all_metadata)}")
    for s, c in sorted(counts.items()):
        print(f"  {s:12} : {c}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--key",   required=True, help="Harvard API key")
    parser.add_argument("--style", default="all")
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()

    all_styles = list(STYLE_QUERIES.keys())
    styles = all_styles if args.style == "all" else [args.style]
    run(args.key, styles, args.limit)
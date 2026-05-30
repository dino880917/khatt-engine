"""
Wikimedia Commons — Arabic Calligraphy Collector
Uses verified category names.

Usage:
    python dataset/tools/fetch_wiki.py --style all --limit 40
"""

import time
import json
import argparse
import requests
from pathlib import Path
from collections import Counter

RAW_DIR   = Path("dataset/raw")
META_FILE = Path("dataset/wiki_metadata.json")

# Verified Wikimedia Commons category names
STYLE_CATEGORIES = {
    "kufic": [
        "Kufic script",
        "Kufic calligraphy",
        "Kufic inscriptions",
        "Early Kufic manuscripts",
    ],
    "naskh": [
        "Naskh (script)",
        "Arabic manuscripts",
        "Quran manuscripts",
        "Islamic manuscripts",
    ],
    "thuluth": [
        "Thuluth script",
        "Arabic calligraphy",
        "Islamic calligraphy",
    ],
    "nastaliq": [
        "Nastaliq script",
        "Persian calligraphy",
        "Safavid manuscripts",
    ],
    "diwani": [
        "Diwani script",
        "Ottoman calligraphy",
        "Tughra",
    ],
    "ruqah": [
        "Ruq'ah script",
        "Arabic calligraphy",
        "Modern Arabic calligraphy",
    ],
}

API_URL = "https://commons.wikimedia.org/w/api.php"
HEADERS = {
    "User-Agent": "KhattEngine/1.0 (Arabic calligraphy dataset collector; research use) python-requests"
}

FREE_LICENSES = [
    "CC0", "CC BY", "CC BY-SA", "CC-BY", "CC-BY-SA",
    "Public domain", "PD", "public domain",
    "Attribution", "pd-old",
]

def get_category_members(category, limit=100):
    """Get file members from a Wikimedia category."""
    params = {
        "action":      "query",
        "list":        "categorymembers",
        "cmtitle":     f"Category:{category}",
        "cmtype":      "file",
        "cmlimit":     min(limit, 500),
        "format":      "json",
        "cmnamespace": 6,
    }
    try:
        r = requests.get(API_URL, params=params, timeout=20, headers=HEADERS)
        if r.status_code == 200:
            data    = r.json()
            members = data.get("query", {}).get("categorymembers", [])
            return [m["title"] for m in members]
    except Exception as e:
        print(f"    Error: {e}")
    return []

def get_image_info(title):
    """Get URL and license for a file."""
    params = {
        "action":  "query",
        "titles":  title,
        "prop":    "imageinfo",
        "iiprop":  "url|mime|size|extmetadata",
        "format":  "json",
    }
    try:
        r = requests.get(API_URL, params=params, timeout=15, headers=HEADERS)
        if r.status_code == 200:
            pages = r.json().get("query", {}).get("pages", {})
            for page in pages.values():
                info = (page.get("imageinfo") or [{}])[0]
                mime = info.get("mime", "")
                if not mime.startswith("image/"):
                    return None, None
                url  = info.get("url", "")
                meta = info.get("extmetadata", {})
                lic  = (meta.get("LicenseShortName", {})
                           .get("value", "unknown"))
                w    = info.get("width", 0)
                h    = info.get("height", 0)
                # Skip tiny images
                if w < 400 or h < 400:
                    return None, None
                return url, lic
    except Exception as e:
        print(f"    Info error: {e}")
    return None, None

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

def collect_style(style, limit, existing_ids):
    categories = STYLE_CATEGORIES.get(style, [])
    out_dir    = RAW_DIR / style
    out_dir.mkdir(parents=True, exist_ok=True)
    on_disk    = set(f.stem for f in out_dir.glob("*"))

    all_titles = []
    for cat in categories:
        print(f"  Category: '{cat}'")
        titles = get_category_members(cat, limit * 3)
        print(f"    Found {len(titles)} files")
        all_titles.extend(titles)
        time.sleep(0.4)

    # Deduplicate
    seen, unique = set(), []
    for t in all_titles:
        if t not in seen:
            seen.add(t)
            unique.append(t)
    all_titles = unique
    print(f"  Unique files: {len(all_titles)}")

    metadata   = []
    downloaded = 0

    for title in all_titles:
        if downloaded >= limit:
            break

        # Build a safe filename
        safe = (title.replace("File:", "")
                     .replace(" ", "_")
                     .replace("/", "_"))
        ext  = safe.rsplit(".", 1)[-1].lower()
        if ext not in ("jpg", "jpeg", "png"):
            continue

        record_id = f"wiki_{safe}"
        if record_id in existing_ids or safe in on_disk:
            downloaded += 1
            continue

        url, lic = get_image_info(title)
        if not url:
            time.sleep(0.2)
            continue

        # Check license
        if not any(fl.lower() in (lic or "").lower()
                   for fl in FREE_LICENSES):
            time.sleep(0.1)
            continue

        dest_name = f"wiki_{safe}"
        dest      = out_dir / dest_name
        print(f"  [{style}] {safe[:55]}  [{lic}]")

        if download_image(url, dest):
            metadata.append({
                "id":            record_id,
                "source":        "wikimedia_commons",
                "style":         style,
                "license":       lic,
                "filename":      dest_name,
                "original_name": title,
                "transcription": "",
                "caption":       "",
            })
            downloaded += 1
            print(f"    Saved ({downloaded}/{limit})")

        time.sleep(0.3)

    return metadata

def run(styles, limit):
    all_metadata = []
    if META_FILE.exists():
        with open(META_FILE, "r", encoding="utf-8") as f:
            all_metadata = json.load(f)
        print(f"Loaded {len(all_metadata)} existing records.")

    existing_ids = {r["id"] for r in all_metadata}

    for style in styles:
        print(f"\n{'='*50}")
        print(f"Collecting: {style}  (limit={limit})")
        print(f"{'='*50}")
        new = collect_style(style, limit, existing_ids)
        new = [r for r in new if r["id"] not in existing_ids]
        all_metadata.extend(new)
        existing_ids.update(r["id"] for r in new)
        print(f"  Added {len(new)} records for {style}")

    with open(META_FILE, "w", encoding="utf-8") as f:
        json.dump(all_metadata, f, ensure_ascii=False, indent=2)

    counts = Counter(r["style"] for r in all_metadata)
    print(f"\nTotal: {len(all_metadata)} images")
    for s, c in sorted(counts.items()):
        print(f"  {s:12} : {c}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--style",  default="all")
    parser.add_argument("--limit",  type=int, default=40)
    args = parser.parse_args()

    styles = (list(STYLE_CATEGORIES.keys())
              if args.style == "all" else [args.style])
    run(styles, args.limit)
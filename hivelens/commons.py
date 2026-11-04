"""Fetches openly licensed frame photos from Wikimedia Commons, keeping author and licence.

    python -m hivelens.commons            # downloads the default demo set into data/demo/comb/
"""

from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request

from . import config

API = "https://commons.wikimedia.org/w/api.php"
UA = {"User-Agent": "HiveLens/0.1 (hackathon demo; https://github.com/AbulkasimovBakhtiyar2006/HiveLens)"}
OPEN_LICENSES = ("CC0", "CC BY", "CC BY-SA", "Public domain", "PD")

DEMO_FRAMES = [
    "File:Cadre de corps de ruche.JPG",
    "File:Frame from hive of honey bee (apis mellifera).jpg",
    "File:A slice of the brood nest.jpg",
]


def _clean(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html or "")).strip()


def fetch(title: str, width: int = 2000) -> dict:
    """Downloads one Commons file (scaled to `width`) into data/demo/comb/ and records its credit line."""
    if not title.startswith("File:"):
        title = "File:" + title
    q = urllib.parse.urlencode({
        "action": "query", "titles": title, "prop": "imageinfo", "format": "json",
        "iiprop": "url|extmetadata", "iiurlwidth": width,
        "iiextmetadatafilter": "LicenseShortName|Artist|LicenseUrl",
    })
    with urllib.request.urlopen(urllib.request.Request(f"{API}?{q}", headers=UA), timeout=30) as r:
        page = next(iter(json.load(r)["query"]["pages"].values()))
    if "imageinfo" not in page:
        raise ValueError(f"Not found on Commons: {title}")
    info = page["imageinfo"][0]
    meta = info.get("extmetadata", {})
    license_ = _clean(meta.get("LicenseShortName", {}).get("value", ""))
    if not license_.startswith(OPEN_LICENSES):
        raise ValueError(f"{title}: licence '{license_}' is not an open licence, skipped")
    url = info.get("thumburl") or info["url"]

    folder = config.DATA_DIR / "demo" / "comb"
    folder.mkdir(parents=True, exist_ok=True)
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", title[5:]).strip("_")
    name = re.sub(r"\.(jpe?g|png|webp)$", "", name, flags=re.I) + ".jpg"
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        (folder / name).write_bytes(r.read())

    credit = {
        "file": name, "title": title, "author": _clean(meta.get("Artist", {}).get("value", "")),
        "license": license_, "license_url": meta.get("LicenseUrl", {}).get("value", ""),
        "source": "https://commons.wikimedia.org/wiki/" + urllib.parse.quote(title.replace(" ", "_")),
    }
    credits_path = folder / "CREDITS.json"
    credits = json.loads(credits_path.read_text()) if credits_path.exists() else {}
    credits[name] = credit
    credits_path.write_text(json.dumps(credits, indent=2, ensure_ascii=False))
    return credit


if __name__ == "__main__":
    for t in DEMO_FRAMES:
        c = fetch(t)
        print(f"✓ {c['file']}  ·  {c['author']}  ·  {c['license']}")

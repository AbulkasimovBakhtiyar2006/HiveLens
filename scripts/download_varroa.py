"""Downloads the public varroa sticky-board dataset (CC BY 4.0) into data/varroa/.

Divasón J., Romero A., Martínez de Pisón F.J., Silvestre M.A., Santolaria P., Yániz J.L. (2023).
Dataset for varroa mite detection on sticky boards. Zenodo. https://doi.org/10.5281/zenodo.10231845

Only the images + expert annotations (dataset.zip, ~350 MB) and the train/validation
split are downloaded. None of the authors' models are used by HiveLens.
"""

from __future__ import annotations

import sys
import urllib.request
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from hivelens import config  # noqa: E402

BASE = "https://zenodo.org/records/10231845/files/"
FILES = ["dataset.zip", "df_dataset.csv"]


def fetch(name: str, dest: Path) -> None:
    if dest.exists() and dest.stat().st_size > 0:
        print(f"✓ {name} already downloaded")
        return
    url = f"{BASE}{name}?download=1"
    print(f"↓ {url}")
    tmp = dest.with_suffix(dest.suffix + ".part")

    def hook(blocks, block_size, total):
        if total > 0:
            done = min(blocks * block_size, total)
            print(f"\r  {done / 1e6:7.1f} / {total / 1e6:.1f} MB", end="", flush=True)

    urllib.request.urlretrieve(url, tmp, hook)
    print()
    tmp.rename(dest)


def main() -> None:
    out = config.DATA_DIR / "varroa"
    out.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        fetch(name, out / name)
    if not any(out.rglob("*.xml")):
        print("unzipping…")
        with zipfile.ZipFile(out / "dataset.zip") as z:
            z.extractall(out)
    imgs = list(out.rglob("*.jpg")) + list(out.rglob("*.JPG"))
    xmls = list(out.rglob("*.xml"))
    print(f"done: {len(imgs)} images, {len(xmls)} annotation files in {out}")


if __name__ == "__main__":
    main()

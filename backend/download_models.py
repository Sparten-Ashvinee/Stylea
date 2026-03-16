"""
download_models.py
------------------
Downloads the SAM ViT-B checkpoint used by the Stylea backend.

Usage:
    python download_models.py
"""

import hashlib
import os
import sys
import urllib.request
from pathlib import Path

MODELS_DIR = Path(__file__).parent / "models"
SAM_URL = "https://dl.fbaipublicfiles.com/segment_anything/sam_vit_b_01ec64.pth"
SAM_FILENAME = "sam_vit_b_01ec64.pth"
SAM_MD5 = "01ec64d29a2fca3f0661936605ae66be"


def _md5(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def download_with_progress(url: str, dest: Path) -> None:
    print(f"Downloading {url} → {dest} …")

    def _reporthook(block_num: int, block_size: int, total_size: int) -> None:
        downloaded = block_num * block_size
        if total_size > 0:
            pct = min(100, downloaded * 100 // total_size)
            bar = "#" * (pct // 2) + "-" * (50 - pct // 2)
            sys.stdout.write(f"\r[{bar}] {pct}%")
            sys.stdout.flush()

    urllib.request.urlretrieve(url, dest, reporthook=_reporthook)
    print()


def main() -> None:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    dest = MODELS_DIR / SAM_FILENAME

    if dest.exists():
        print(f"Verifying existing file {dest} …")
        if _md5(dest) == SAM_MD5:
            print("Checksum OK – nothing to download.")
            return
        print("Checksum mismatch – re-downloading.")
        dest.unlink()

    download_with_progress(SAM_URL, dest)

    print("Verifying download …")
    if _md5(dest) != SAM_MD5:
        print("ERROR: Checksum mismatch after download!", file=sys.stderr)
        sys.exit(1)
    print(f"Model saved to {dest}")


if __name__ == "__main__":
    main()

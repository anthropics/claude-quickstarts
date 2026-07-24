#!/usr/bin/env python3
"""Fetch a REAL financial-advisor board presentation from SEC EDGAR.

In going-private transactions, the financial advisors' board decks are
filed publicly as exhibits to Schedule 13E-3. For the Squarespace / Permira
take-private (2024), Centerview Partners' discussion materials were filed
as page-image exhibits — each slide is a scanned JPG. This script downloads
the first few slides and stitches them into a PDF, giving the notebook a
genuine chart-heavy document to normalize.

Public-record source: SEC EDGAR, CIK 1496963, accession 0001140361-24-030374,
exhibit (c)(ii). Requires: pillow. SEC asks for a descriptive User-Agent.
"""

import io
import sys
import urllib.request
from pathlib import Path

BASE = "https://www.sec.gov/Archives/edgar/data/1496963/000114036124030374"
SLIDES = [f"ny20030653x1_ex16cii-img{n:02d}.jpg" for n in range(1, 7)]
OUT = Path(__file__).parent / "example_data" / "deal_room_real" / "real_board_deck.pdf"
UA = {
    "User-Agent": "kg-cookbook-demo research contact: replace-with-your-email@example.com"
}


def main():
    try:
        from PIL import Image
    except ImportError:
        sys.exit("pip install pillow")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    pages = []
    for name in SLIDES:
        req = urllib.request.Request(f"{BASE}/{name}", headers=UA)
        data = urllib.request.urlopen(req, timeout=60).read()
        img = Image.open(io.BytesIO(data)).convert("RGB")
        pages.append(img)
        print(f"fetched {name} ({len(data):,} bytes)")
    pages[0].save(OUT, save_all=True, append_images=pages[1:])
    print(f"wrote {OUT} ({OUT.stat().st_size:,} bytes, {len(pages)} pages)")


if __name__ == "__main__":
    main()

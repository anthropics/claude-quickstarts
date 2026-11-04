#!/usr/bin/env python3
"""Build a REAL M&A data room from SEC EDGAR filings.

Downloads the public filings named in the tier manifest (see
build_manifest.py) and converts them to plain text for knowledge-wiki
extraction.

Usage:
    python3 fetch_data_room.py --tier=core        # 8 filings, 2.8 MB text: the recorded run (default)
    python3 fetch_data_room.py --tier=quickstart  # 8 short deal-window filings: the cheap path
    python3 fetch_data_room.py --tier=mini        # 26 docs, ~0.5 MB text
    python3 fetch_data_room.py --tier=standard    # +proxy, tender docs, 10-Qs
    python3 fetch_data_room.py --tier=full        # all 42 deal-window filings
    python3 fetch_data_room.py --convert          # re-extract docs/ from raw/

The notebook builds whatever is in data_room/docs/, and the tiers name some of the same filings differently, so
the script stops if docs/ already holds text files that are not part of the chosen tier: empty the folder (or
pass --keep-other-files if you mean to mix them) and run it again.

Stdlib only — no pip installs needed. SEC asks for a descriptive
User-Agent on all EDGAR requests; set EDGAR_USER_AGENT or edit below.
"""

import json
import os
import re
import sys
import time
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

HERE = Path(__file__).parent
RAW = HERE / "data_room" / "raw"
DOCS = HERE / "data_room" / "docs"


USER_AGENT = os.environ.get("EDGAR_USER_AGENT", "")
if not USER_AGENT:
    USER_AGENT = "research demo admin@example.com"
    print(
        "note: EDGAR_USER_AGENT not set — using a placeholder. SEC asks for a "
        "real 'name email' contact and may throttle placeholder agents."
    )


class TextExtractor(HTMLParser):
    """Extract readable text from an EDGAR HTML filing.

    Keeps rough table structure (cells joined with ' | ') so financial
    tables stay interpretable after conversion.
    """

    SKIP = {"script", "style", "head"}
    BLOCK = {"p", "div", "tr", "table", "br", "h1", "h2", "h3", "h4", "li", "hr"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out = []
        self.skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip_depth += 1
        elif tag in ("td", "th"):
            self.out.append(" | ")
        elif tag in self.BLOCK:
            self.out.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP:
            self.skip_depth = max(0, self.skip_depth - 1)
        elif tag in self.BLOCK:
            self.out.append("\n")

    def handle_data(self, data):
        if not self.skip_depth:
            self.out.append(data)

    def text(self):
        raw = "".join(self.out)
        raw = raw.replace("\xa0", " ")
        raw = re.sub(r"[ \t]+", " ", raw)
        raw = re.sub(r" ?\| (?:\| )+", " | ", raw)  # collapse empty cells
        lines = [ln.strip(" |") for ln in raw.split("\n")]
        text = "\n".join(ln for ln in lines if ln)
        return re.sub(r"\n{3,}", "\n\n", text)


def fetch(url: str, dest: Path):
    # cache key includes the URL: editing manifest.json invalidates stale raw files
    url_marker = dest.with_suffix(".url")
    if dest.exists() and url_marker.exists() and url_marker.read_text() == url:
        print(f"  cached  {dest.name}")
        return
    if not url.startswith("https://www.sec.gov/"):  # the manifests point at EDGAR only
        raise ValueError(f"refusing to fetch {url!r}: not an https://www.sec.gov/ URL")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as resp:
        dest.write_bytes(resp.read())
    url_marker.write_text(url)
    print(f"  fetched {dest.name} ({dest.stat().st_size:,} bytes)")
    time.sleep(0.5)  # stay well under EDGAR's 10 req/s limit


def convert(raw_path: Path, txt_path: Path, meta: dict):
    parser = TextExtractor()
    parser.feed(raw_path.read_text(encoding="utf-8", errors="replace"))
    body = parser.text()
    if len(body) < 500 or parser.skip_depth:
        print(
            f"  WARNING {raw_path.name}: suspiciously empty extraction "
            f"({len(body)} chars, skip_depth={parser.skip_depth}) — check the HTML"
        )
    header = (
        f"[SOURCE: SEC EDGAR | form: {meta['form']} | filed: {meta['filed']} | "
        f"accession: {meta['accession']} | url: {meta['url']}]\n\n"
    )
    txt_path.write_text(header + body, encoding="utf-8")
    print(f"  wrote   {txt_path.name} ({txt_path.stat().st_size:,} bytes)")


def main():
    tier = "core"
    for a in sys.argv[1:]:
        if a.startswith("--tier="):
            tier = a.split("=", 1)[1]
    manifest_path = HERE / f"manifest_{tier}.json"
    if not manifest_path.exists():
        sys.exit(f"{manifest_path.name} not found (the tiers are core, quickstart, mini, standard and full)")
    manifest = json.loads(manifest_path.read_text())
    print(f"tier={tier}: {len(manifest['documents'])} documents")
    RAW.mkdir(parents=True, exist_ok=True)
    DOCS.mkdir(parents=True, exist_ok=True)
    convert_only = "--convert" in sys.argv
    # The notebook builds every .txt file in docs/. Files left from another tier (or anything else) would be built
    # too, some of them the same filing under another name, so stop unless the caller says to keep them. The worked
    # example's own companions, which the notebook writes there, are fine.
    example_files = {"analyst_note.txt", "data_provider_extract.csv.txt", "board_deck_cii.txt"}
    wanted = {f"{item['slug']}.txt" for item in manifest["documents"]} | example_files
    others = sorted(p.name for p in DOCS.glob("*.txt") if p.name not in wanted)
    if others and "--keep-other-files" not in sys.argv:
        sys.exit(
            f"{DOCS} already holds {len(others)} text file(s) that are not part of tier {tier!r} "
            f"(first: {others[0]}). Empty the folder, or pass --keep-other-files to build them as well."
        )

    for item in manifest["documents"]:
        if not re.fullmatch(r"[a-z0-9_.-]+", item["slug"]) or ".." in item["slug"]:  # a file name, nothing more
            sys.exit(f"bad slug in {manifest_path.name}: {item['slug']!r}")
        raw_path = RAW / f"{item['slug']}.htm"
        txt_path = DOCS / f"{item['slug']}.txt"
        if not convert_only:
            fetch(item["url"], raw_path)
        if raw_path.exists():
            convert(raw_path, txt_path, item)
        else:
            print(f"  MISSING raw file for {item['slug']} — run without --convert")


if __name__ == "__main__":
    main()

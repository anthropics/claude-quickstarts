#!/usr/bin/env python3
"""Build tiered document manifests for the deal data room from SEC EDGAR.

Queries the submissions index for Squarespace, Inc. (CIK 1496963) and emits
four manifest_*.json files describing real public filings from the 2024
Permira take-private:

- quickstart (~8 docs)               — the ~40-minute path.
- mini       (~26 docs, <1 MB text)  — announce/amend/close press releases,
             small schedules, a handful of insider Form 4s. Start here.
- standard   (~37 docs, ~4 MB text)  — adds the merger proxy (DEFM14A), the
             tender offer documents, quarterly reports, and more Form 4s.
             This is study scale; expect a build in the tens of dollars.
- full       (everything the window offers, ~42 docs) — for the ambitious.

Stdlib only. Set EDGAR_USER_AGENT to "your-name your-email" per SEC policy.
"""

import json
import os
import urllib.request
from pathlib import Path

CIK = "0001496963"
HERE = Path(__file__).parent
UA = {
    "User-Agent": os.environ.get(
        "EDGAR_USER_AGENT", "kg-cookbook-demo replace@example.com"
    )
}
ARCH = f"https://www.sec.gov/Archives/edgar/data/{int(CIK)}"

# forms worth having, and the date window that makes them deal-relevant
WINDOW = ("2024-02-01", "2024-11-01")
CORE_FORMS = {
    "8-K",
    "DEFM14A",
    "DEFA14A",
    "SC 13E3",
    "SC 13E3/A",
    "SC TO-T",
    "SC 14D9",
    "SC 14D9/A",
    "PX14A6G",
    "25-NSE",
    "S-8 POS",
}
BACKGROUND = {"10-K", "10-Q", "DEF 14A"}  # any date >= 2023-01-01
MAX_STANDARD_BYTES = 10_000_000  # skip the 40 MB monsters in standard


def main():
    d = json.load(
        urllib.request.urlopen(
            urllib.request.Request(
                f"https://data.sec.gov/submissions/CIK{CIK}.json", headers=UA
            )
        )
    )
    r = d["filings"]["recent"]
    rows = list(
        zip(
            r["form"],
            r["accessionNumber"],
            r["filingDate"],
            r["primaryDocument"],
            r["size"],
        )
    )

    docs = []
    form4_count = 0
    for form, acc, date, doc, size in rows:
        accn = acc.replace("-", "")
        url = f"{ARCH}/{accn}/{doc}"
        entry = {
            "slug": f"{form.lower().replace(' ', '').replace('/', '')}_{date.replace('-', '')}",
            "form": form,
            "filed": date,
            "accession": acc,
            "url": url,
            "bytes": size,
        }
        in_window = WINDOW[0] <= date <= WINDOW[1]
        if form in CORE_FORMS and in_window:
            entry["tier"] = "standard" if size > 700_000 else "mini"
            if form == "8-K" and size < 3_000_000:
                entry["tier"] = "mini"  # every deal-window 8-K tells the story
            if size > MAX_STANDARD_BYTES and form != "DEFM14A":
                entry["tier"] = "full"
            docs.append(entry)
        elif form in BACKGROUND and date >= "2023-11-01":
            entry["tier"] = "standard" if size < 9_000_000 else "full"
            docs.append(entry)
        elif form == "4" and in_window:
            form4_count += 1
            # the aggregated multi-holder filings (larger) tell the ownership
            # story best; cap how many land in each tier
            if size > 12_000 and form4_count <= 30:
                entry["tier"] = (
                    "mini"
                    if len(
                        [x for x in docs if x["form"] == "4" and x["tier"] == "mini"]
                    )
                    < 4
                    else "standard"
                )
                entry["slug"] += f"_{acc[-4:]}"
                docs.append(entry)

    # dedupe slugs
    seen = {}
    for e in docs:
        if e["slug"] in seen:
            e["slug"] += "_" + e["accession"][-4:]
        seen[e["slug"]] = True

    # quickstart: ~8 docs chosen for cross-document connectivity — the merger
    # agreement + amendment pair, deal-window 8-Ks, the proxy, and two Form 4s
    # give entity resolution, temporal supersession, and code-name work in a
    # ~40-minute build. Hand-ranked by form priority, then recency.
    mini_docs = [e for e in docs if e["tier"] == "mini"]
    # Drop the June 6 proxy-supplement 8-K so the eight slots keep the full
    # deal arc: original May 7 announcement -> September revised terms ->
    # October closing (the original/revised pair is the supersession demo).
    eightks = sorted(
        (e for e in mini_docs if e["form"] == "8-K" and e["filed"] != "2024-06-06"),
        key=lambda e: e["filed"],
    )
    form4s = sorted(
        (e for e in mini_docs if e["form"] == "4"), key=lambda e: e["filed"]
    )
    others = [e for e in mini_docs if e["form"] not in ("8-K", "4")]
    quick = (eightks[-6:] + form4s[:2] + others)[:8]
    quick_slugs = {e["slug"] for e in quick}
    for tier_name, allowed in [
        ("quickstart", {"mini"}),
        ("mini", {"mini"}),
        ("standard", {"mini", "standard"}),
        ("full", {"mini", "standard", "full"}),
    ]:
        subset = [e for e in docs if e["tier"] in allowed]
        if tier_name == "quickstart":
            subset = [e for e in docs if e["slug"] in quick_slugs]
        manifest = {
            "deal": "Squarespace, Inc. / Permira take-private (2024) — all documents are public SEC EDGAR filings",
            "tier": tier_name,
            "documents": subset,
        }
        out = HERE / f"manifest_{tier_name}.json"
        out.write_text(json.dumps(manifest, indent=1))
        total = sum(e["bytes"] for e in subset)
        print(f"{tier_name:9} {len(subset):3} docs  {total / 1e6:6.1f} MB raw html")


if __name__ == "__main__":
    main()

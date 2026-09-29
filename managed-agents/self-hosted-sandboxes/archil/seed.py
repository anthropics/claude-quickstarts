#!/usr/bin/env python3
"""Load SEC EDGAR bulk data sets onto the Archil disk.

Runs in a throwaway Archil sandbox with the disk mounted at /mnt/edgar and
downloads, quarter by quarter, three of the SEC's structured data sets
(https://www.sec.gov/data-research/sec-markets-data), each unpacked to
/mnt/edgar/<set>/<quarter>/ as tab-separated tables:

  insider/     Forms 3, 4, 5 since 2006: who holds and trades what at which
               company. SUBMISSION (issuer), REPORTINGOWNER (the person,
               role, title), NONDERIV_TRANS / DERIV_TRANS (the trades), joined
               on ACCESSION_NUMBER.
  financials/  Financial Statement Data Sets since 2009: every number in
               every 10-K and 10-Q. sub (the filing), num (the values), pre
               (where each value sits in the statements), tag (definitions).
  formd/       Form D since 2008: private offerings, with ISSUERS and
               RELATEDPERSONS (officers and directors of private companies).

plus EDGAR's two bulk indexes, submissions.zip (every company's filing
history) and companyfacts.zip (every XBRL fact). The whole load is about
70 GB and takes an hour or two; re-runs skip what is already there. Set
EDGAR_FROM (e.g. 2021q1) to load fewer years of the quarterly sets.

Set SEC_USER_AGENT in .env; the SEC requires it on every request.
"""

import os
from datetime import date

import sandboxes

disk, region = os.environ["ARCHIL_DISK"], os.environ["ARCHIL_REGION"]
start = os.environ.get("EDGAR_FROM", "2006q1")
today = date.today()
last = f"{today.year}q{(today.month - 1) // 3 + 1}"

# (directory, URL pattern with {q}, first quarter published, file proving a quarter is complete)
SETS = [
    (
        "insider",
        "https://www.sec.gov/files/structureddata/data/insider-transactions-data-sets/{q}_form345.zip",
        "2006q1",
        "REPORTINGOWNER.tsv",
    ),
    (
        "financials",
        "https://www.sec.gov/files/dera/data/financial-statement-data-sets/{q}.zip",
        "2009q1",
        "num.txt",
    ),
    (
        "formd",
        "https://www.sec.gov/files/structureddata/data/form-d-data-sets/{q}_d.zip",
        "2008q1",
        "FORMDSUBMISSION.tsv",
    ),
]


def quarters(first: str) -> list[str]:
    first = max(first, start)
    return [
        f"{y}q{n}"
        for y in range(int(first[:4]), today.year + 1)
        for n in range(1, 5)
        if first <= f"{y}q{n}" <= last
    ]


# One shell function does the download-and-unpack; the Form D zips nest a
# directory, so the unpacked files are flattened into place afterwards.
script = """
set -e
mkdir -p /mnt/edgar
archil -q mount {disk} /mnt/edgar --region {region} >/dev/null
cd /mnt/edgar
curl -fsS -A "$SEC_USER_AGENT" -o company_tickers.json https://www.sec.gov/files/company_tickers.json

fetch() {{  # fetch <dir> <url> <done-marker>
  [ -f $1/$3 ] && return 0
  # The newest quarter or two may not be published yet: 404 is not an error.
  curl -fsS -A "$SEC_USER_AGENT" -o /tmp/q.zip $2 || {{ echo "$1: not published"; return 0; }}
  rm -rf $1 && mkdir -p $1 && unzip -q /tmp/q.zip -d $1 && rm /tmp/q.zip
  find $1 -mindepth 2 -type f -exec mv -t $1 {{}} + 2>/dev/null; find $1 -mindepth 1 -type d -delete
  echo "$1: $(du -sh --apparent-size $1 | cut -f1)"
}}
{fetches}

# Two bulk indexes: every company's complete filing history (submissions/
# CIK##########.json: form types, dates, accession numbers, document names)
# and every XBRL financial fact (companyfacts/CIK##########.json). The zips
# land on the disk itself, so the sandbox's own disk size does not matter.
for name in submissions companyfacts; do
  [ -d $name ] && continue
  curl -fsS -A "$SEC_USER_AGENT" -o $name.zip https://www.sec.gov/Archives/edgar/daily-index/$( [ $name = companyfacts ] && echo xbrl || echo bulkdata )/$name.zip
  mkdir -p $name && unzip -q $name.zip -d $name && rm $name.zip
  echo "$name: $(ls $name | wc -l) files"
done
du -sh --apparent-size /mnt/edgar/*/
cd / && archil unmount /mnt/edgar
""".format(
    disk=disk,
    region=region,
    fetches="\n".join(
        f"fetch {name}/{q} {url.format(q=q)} {marker}"
        for name, url, first, marker in SETS
        for q in quarters(first)
    ),
)

sandbox = sandboxes.create("edgar-seed")
try:
    sandboxes.run(sandbox, sandboxes.BOOTSTRAP, stream=False)
    sandboxes.run(
        sandbox,
        script,
        env={
            "ARCHIL_MOUNT_TOKEN": os.environ["ARCHIL_MOUNT_TOKEN"],
            "SEC_USER_AGENT": os.environ["SEC_USER_AGENT"],
        },
    )
finally:
    sandboxes.destroy(sandbox)

# EDGAR analysts on Archil

Run managed-agent sessions in [Archil](https://archil.com) persistent
sandboxes, with the whole SEC EDGAR insider-filing history mounted as a
directory. Ask for a profile of a company or a person and an analyst agent
maps the insiders, their roles and trades over time, and the other
companies those people file at, working on the data in place. Fan out one
analyst per subject: they all read the same disk and each writes its report
back to it.

The control plane is a normal self-hosted environment. A host process runs
`ant beta:worker poll`, and for each claimed session `on-work.py` creates an
Archil sandbox, mounts the disk at `/mnt/edgar` in shared mode, checks out a
per-session report directory, and runs `ant beta:worker run` there until the
session idles.

## How to use it

Needs Python 3.10+ with the Archil SDK (`pip install -r requirements.txt`),
`jq`, and the [`ant` CLI](https://platform.claude.com/docs/en/cli-sdks-libraries/cli/quickstart)
1.30 or later (`brew install anthropics/tap/ant`) with `ant auth login`. On
the Archil side, in the [console](https://console.archil.com): a disk (use
its `dsk-...` ID), an **API key** from the API keys page, and a **Disk
Token** from the disk's page.

```sh
cd managed-agents/self-hosted-sandboxes/archil
claude "help me set up and run this Archil EDGAR demo"
```

Or by hand, from this directory:

```sh
pip install -r requirements.txt
ant apply .            # creates the self-hosted environment + agent, records their IDs in claude-lock.json
cp .env.example .env
# Fill in .env: ANTHROPIC_ENVIRONMENT_KEY (Console -> Environments -> Keys),
# ARCHIL_API_KEY, ARCHIL_REGION, ARCHIL_DISK, ARCHIL_MOUNT_TOKEN, SEC_USER_AGENT
set -a; . ./.env; set +a
python seed.py         # loads the EDGAR data sets onto the disk (see below)
./start.sh             # polls the environment with 3 workers
```

[`ant apply`](https://platform.claude.com/docs/en/cli-sdks-libraries/cli/apply)
reads the agent from `agents/edgar-analyst.md`, whose frontmatter is the
configuration and whose prose is the system prompt that describes the
tables, and the environment from `environments/self-hosted.yaml`. It shows
the plan and creates both once you approve. To retune the analyst, edit its
file and run `ant apply` again: it publishes a new version of the same
agent, because `claude-lock.json` remembers which resources these files
became. This repository ignores that file, since every reader creates their
own resources. In a project of your own, commit it.

From another terminal, start one analyst per subject, a company or a
person:

```sh
./fanout.sh "Tesla" "Venture Global (NYSE: VG)" "Sanjit Biswas, CEO of Samsara"
```

Insider filings only cover SEC registrants. A private company can still
appear in the Form D data with its officers and directors, and the agent
says what the data cannot show.

`start.sh` streams every sandbox's log. When an analyst finishes, its
five-line summary is the last message in the session (`fanout.sh` prints
the command) and the full report is on the disk at
`reports/<session>/report.md`, readable from any machine that mounts the
disk.

## The data

`seed.py` starts with the SEC's
[insider transactions data sets](https://www.sec.gov/data-research/sec-markets-data/insider-transactions-data-sets):
every Form 3, 4, and 5 since 2006 as quarterly tab-separated tables, about
10 MB zipped and 100 MB unpacked per quarter, 80-odd quarters in all. Each
quarter's `REPORTINGOWNER.tsv` (who filed: CIK, name, relationship, title)
joins `SUBMISSION.tsv` (which company) and `NONDERIV_TRANS.tsv` (what they
traded) on `ACCESSION_NUMBER`, which is what lets an agent walk from a
person to their companies to the other people at those companies.
Re-runs only fetch missing quarters.

Two more quarterly series load the same way: the
[Financial Statement Data Sets](https://www.sec.gov/data-research/sec-markets-data/financial-statement-data-sets)
(every number in every 10-K and 10-Q since 2009, about 640 MB a quarter)
and the [Form D data sets](https://www.sec.gov/data-research/sec-markets-data/form-d-data-sets)
(private offerings since 2008, with the officers and directors of the
private companies raising money).

`seed.py` also loads EDGAR's two bulk indexes: `submissions.zip` (every
company's complete filing history, about a million JSON files, 5 GB) and
`companyfacts.zip` (every XBRL financial fact, 20k files, 18 GB). With
those, an agent can walk from an insider to the company's proxy statements
and 8-Ks, fetch the ones it needs from sec.gov, and put the trades against
the financials. The full load is about 70 GB on the disk and takes an hour
or two. `EDGAR_FROM=2021q1` cuts the quarterly series to five years.

The SEC requires a `User-Agent` naming you on every download: set
`SEC_USER_AGENT` in `.env`.

## How it works

| | |
|---|---|
| `agents/edgar-analyst.md`, `environments/self-hosted.yaml` | The agent and the self-hosted environment, as files for `ant apply`. The system prompt describes the tables, and the agent pins `tools: [{type: agent_toolset_20260401}]`, the toolset `ant beta:worker run` serves. |
| `sandboxes.py` | Three helpers over the [Archil Python SDK](https://pypi.org/project/archil/): create a sandbox, run a command to completion over the sandbox's process API (a websocket that streams stdout and stderr back while the command runs, reattaching if the connection drops), stop and delete. Also the bootstrap script that installs `ant` and `archil` in a fresh sandbox. |
| `seed.py` | One sandbox, exclusive mount, downloads and unpacks the three quarterly series and the two bulk indexes. |
| `on-work.py` | Once per claimed session: sandbox, `archil mount --shared`, `archil checkout reports/<session>`, `ant beta:worker run`, `checkin`, unmount, delete. |
| `start.sh` | Launches `WORKERS` pollers (default 3). One poller serves one session at a time, because the CLI stops a work item when `on-work.py` returns. |
| `fanout.sh` | One session per argument, on the agent and environment recorded in `claude-lock.json`. |

Sandboxes start from the stock `python:3.13` image and install the two
CLIs at boot (about 30s). Archil publishes its client through an install
script pinned by `ARCHIL_CLIENT_VERSION`. Vendor the binary for production.

Shared mode is how many sandboxes read one disk at once: the mount is
read-only until a path is checked out, and `archil checkout` gives one
client exclusive write access to that path. Each session checks out only
its own `reports/<session>/`, so analysts never block each other and cannot
overwrite the data or each other's reports. Archil's
[sharing disks](https://docs.archil.com/concepts/sharing-disks) page covers
the model.

Credentials: the environment key claims work and goes into each sandbox for
`ant beta:worker run`, the Archil mount token goes into each sandbox for
`archil mount`, and the Archil API key stays on the host. An agent runs bash in
its sandbox and can read the two tokens there, so the sandboxes protect the
host, not sessions from each other. Scope the token to a disk that holds
nothing else.

If `on-work.py` exits non-zero (bad disk ID, expired token), the poller
stops that work item and the session is not re-queued. Fix `.env` and
create a new session.

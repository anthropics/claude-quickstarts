"""Functions for the knowledge-wiki quickstart notebook: normalizing and batching the documents, uploading files,
following one workflow run and saving its records, stopping runs, the
checks on what ran, reading, copying and exporting memory stores, asking one question in a read-only session,
pricing, the tables and diagram the notebook shows, and the clean-up. The notebook keeps what you edit for your own
corpus (the schema, the extractor, resolver and analyst prompts, the steering) and the calls that create the
environment, the wiki store, the agents and the sessions.

The transcript files and wiki exports it writes are plain JSON and markdown, so they can be read, diffed and
reused outside this notebook."""

import contextlib
import difflib
import html
import itertools
import json
import os
import re
import stat
import tempfile
import textwrap
import threading
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

import anthropic
from anthropic import Anthropic

# --- Transcript files ---------------------------------------------------------------------------

# The event types that make up a transcript. Status changes, usage spans and thinking markers are left out.
CONVERSATION_EVENTS = {
    "user.message",
    "agent.message",
    "agent.tool_use",
    "agent.tool_result",
    "agent.custom_tool_use",
    "user.custom_tool_result",
    "agent.mcp_tool_use",
    "agent.mcp_tool_result",
    "agent.thread_message_sent",
    "agent.thread_message_received",
    "session.thread_created",
    "session.error",
}
DROPPED_FIELDS = {"processed_at", "evaluation"}  # say nothing about what the agent did or saw
MAX_FILES_PER_SESSION = 500  # the platform's limit on file resources in one session
UPLOAD_TTL_SECONDS = 24 * 3600  # uploaded copies expire after a day even if the clean-up never runs


def compact_events(events):
    """The events of one thread that make up its transcript, as plain dicts. Everything kept is kept whole."""
    kept = []
    for event in events:
        ev = event if isinstance(event, dict) else event.model_dump(mode="json")
        if ev.get("type") in CONVERSATION_EVENTS:
            kept.append({k: v for k, v in ev.items() if k not in DROPPED_FIELDS and v is not None})
    return kept


def export_session(client, session_id, compact=True):
    """One Managed Agents session as plain JSON: the session, the agent it ran, and every thread's events in
    order (with compact=False, every event as the API returns it). The top-level shape is log_format, session,
    agent, threads."""
    sessions = client.beta.sessions
    session = sessions.retrieve(session_id)
    keep = compact_events if compact else (lambda evs: [e.model_dump(mode="json") for e in evs])
    threads = {t.id: t for t in sessions.threads.list(session_id)}
    exported = [
        {
            "id": t.id,
            "parent_thread_id": t.parent_thread_id,
            "agent_name": getattr(t.agent, "name", None) or getattr(t.agent, "type", "agent"),
            "events": keep(sessions.threads.events.list(t.id, session_id=session_id)),
        }
        for t in threads.values()
    ]
    if not any(t["parent_thread_id"] is None for t in exported):
        # No primary thread in the list: the session's own event list stands in for it.
        events = keep(sessions.events.list(session_id, order="asc"))
        exported.insert(
            0,
            {
                "id": "primary",
                "parent_thread_id": None,
                "agent_name": session.agent.name,
                "events": events,
            },
        )
    return {
        "log_format": "managed_agents_export",
        "session": session.model_dump(
            mode="json", include={"id", "title", "status", "created_at", "updated_at"}
        ),
        "agent": session.agent.model_dump(
            mode="json", include={"id", "version", "name", "description", "model"}
        ),
        "threads": exported,
    }


def export_sessions(client, out_dir, session_ids=(), agent_id=None, since=None, limit=100, compact=True):
    """Write one transcript file per finished session into out_dir and return the paths written. Pass the
    session ids you want, or an agent_id (and optionally since, an ISO timestamp) to export that agent's idle
    and terminated sessions, newest first, at most limit. compact=False keeps every event as the API returns
    it (usage spans and status changes included). A session that can't be exported is printed and skipped."""
    out_dir = private_dir(out_dir)
    ids = list(session_ids)
    if agent_id:
        query = {"agent_id": agent_id, "include_archived": True}
        if since:
            query["created_at_gte"] = since
        for s in client.beta.sessions.list(**query):
            if s.status in ("idle", "terminated") and s.id not in ids:
                ids.append(s.id)
            if len(ids) >= limit:
                break
    written = []
    for sid in ids:
        try:
            export = export_session(client, sid, compact=compact)
        except anthropic.APIError as exc:
            print(f"Could not export {sid}: {exc}")
            continue
        path = Path(out_dir) / f"{sid}.json"
        private_write(path, json.dumps(export, ensure_ascii=False, indent=1))
        written.append(path)
    return written


@dataclass
class Uploaded:
    """One uploaded file: its Files API id, the name the agents see, the mount_path given in the session's
    resources (the sandbox sees it under /mnt/session/uploads), and its size in bytes."""

    file_id: str
    name: str
    mount_path: str
    size: int


def upload_file(client, name, data, mount_path, uploaded=None):
    """Upload one file's bytes with the Files API and return its Uploaded record. Pass a list as uploaded to
    have the record appended as soon as the upload succeeds, so a failure part-way through a batch still
    leaves a record of what to delete. The copy expires after a day even if the clean-up never runs."""
    meta = client.files.upload(
        file=(name, data, "application/octet-stream"), expires_in_seconds=UPLOAD_TTL_SECONDS
    )
    record = Uploaded(meta.id, name, mount_path, len(data))
    if uploaded is not None:
        uploaded.append(record)
    return record


def check_file_count(n):
    """Raise before uploading if n files are more than one session mounts."""
    if n > MAX_FILES_PER_SESSION:
        raise ValueError(
            f"{n} files is more than the {MAX_FILES_PER_SESSION} one session can mount. Combine small "
            "documents into shared files (each keeping its [SOURCE: ...] header), or build the corpus in two "
            "sessions into the same store."
        )


def file_resources(uploaded):
    """The resources entries that mount the uploaded files in a session."""
    return [{"type": "file", "file_id": u.file_id, "mount_path": u.mount_path} for u in uploaded]


def sandbox_path(mount_path):
    """Where a file resource with this mount_path appears in the session's sandbox."""
    return "/mnt/session/uploads" + mount_path


def delete_uploads(client, uploaded):
    """Delete the uploaded copies and return the ones that could not be deleted (each is printed, and expires
    within a day anyway)."""
    return [
        u
        for u in uploaded
        if not remove(
            f"delete file {u.file_id} ({u.name})",
            client.files.delete,
            u.file_id,
            retry=f"client.files.delete({u.file_id!r}); it expires within a day anyway",
        )
    ]


# --- The records folder -------------------------------------------------------------------------


def private_dir(path):
    """Create a folder (and any missing parents) readable only by you, mode 0o700, and return it."""
    path = Path(path)
    for folder in reversed([p for p in (path, *path.parents) if not p.exists()]):
        folder.mkdir(mode=0o700, exist_ok=True)
        os.chmod(folder, 0o700)  # mkdir's mode is filtered by the umask
    return path


def private_write(path, text):
    """Write a file readable only by you, mode 0o600, creating its folder privately if it is new. A symbolic
    link at the path is not followed and a file that isn't yours is not written into: both raise ValueError."""
    path = Path(path)
    private_dir(path.parent)
    flags = os.O_WRONLY | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags, 0o600)
    except OSError as why:
        if os.path.islink(path):
            raise ValueError(f"{path} is a link; remove it or use another folder.") from why
        raise
    found = os.fstat(fd)
    if not stat.S_ISREG(found.st_mode) or (hasattr(os, "getuid") and os.getuid() != found.st_uid):
        os.close(fd)
        raise ValueError(f"{path} is not a file of yours; remove it or use another folder.")
    if hasattr(os, "fchmod"):
        os.fchmod(fd, 0o600)
    os.ftruncate(fd, 0)
    with os.fdopen(fd, "w", encoding="utf-8", errors="backslashreplace") as handle:
        handle.write(text)


def records_root():
    """The folder runs are recorded under: COOKBOOK_RECORDS_DIR if set, else a folder of your own under the
    system's temporary directory (/tmp/knowledge_wiki-<uid>/runs on Linux), which most systems clear on restart.
    Either way it is meant to be outside any repository. The temporary folder is created with mode 0o700 (and set
    back to it if it was wider); if something else is already at that path, or the folder is not yours, ValueError
    says to remove it or to set COOKBOOK_RECORDS_DIR."""
    configured = os.getenv("COOKBOOK_RECORDS_DIR")
    if configured:
        return Path(configured)
    uid = os.getuid() if hasattr(os, "getuid") else os.getlogin()
    root = Path(tempfile.gettempdir()) / f"knowledge_wiki-{uid}"
    try:
        root.mkdir(mode=0o700, exist_ok=True)
    except FileExistsError:
        raise ValueError(f"{root} exists but is not a folder; remove it, or set COOKBOOK_RECORDS_DIR.") from None
    if hasattr(os, "getuid"):
        # POSIX: the folder must be a real directory of yours, and it is kept private.
        found = root.lstat()
        if not stat.S_ISDIR(found.st_mode) or found.st_uid != os.getuid():
            raise ValueError(
                f"{root} exists but is not a folder of yours; remove it, or set "
                "COOKBOOK_RECORDS_DIR to a folder only you can read."
            )
        if found.st_mode & 0o077:
            os.chmod(root, 0o700)
    return root / "runs"


def new_run_dir():
    """A new time-stamped folder under records_root() for this run's records (not created yet)."""
    return records_root() / datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%SZ")


def display_path(path):
    """A folder as it is fine to print: ~/... when it is under your home directory, otherwise just its last
    two components, so a run on a server doesn't print that server's paths."""
    path = Path(path)
    try:
        return "~/" + str(path.relative_to(Path.home()))
    except ValueError:
        return str(Path("...") / Path(*path.parts[-2:]))


# --- Memory stores ----------------------------------------------------------------------------------


def fill(template, **values):
    """A prompt template with each {name} placeholder replaced by its value. Only the named placeholders are
    touched, so the JSON braces elsewhere in the templates survive, which str.format would not allow."""
    for name, value in values.items():
        template = template.replace("{" + name + "}", str(value))
    return template


def list_memories(client, store_id, path_prefix="/"):
    """Every memory in a store under path_prefix, without content, in the server's order."""
    listing = client.beta.memory_stores.memories.list(store_id, path_prefix=path_prefix, limit=100)
    return [m for m in listing if getattr(m, "type", "memory") == "memory"]


def read_memory(client, store_id, path, memories=None):
    """The content of the memory at this path, or None if there is none. Pass memories (from list_memories)
    to avoid listing the store again."""
    for m in memories if memories is not None else list_memories(client, store_id):
        if m.path == path:
            return client.beta.memory_stores.memories.retrieve(
                m.id, memory_store_id=store_id, view="full"
            ).content
    return None


STUB = re.compile(r"\s*MOVED TO \[\[([^\]]+)\]\]\s*\Z")


def find_stubs(client, store_id, memories=None):
    """The memories whose whole content is one "MOVED TO [[slug]]" line: what the agents leave behind when they
    merge or rename a file, since their tools can't delete. Returns (memory, target slug, target exists)
    triples; the target exists when a memory that is not itself a stub carries that slug as its file name, without
    .md, in any folder, or when the stubs with that file name lead to such a memory (a node merged twice)."""
    memories = list_memories(client, store_id) if memories is None else memories
    found = []  # (the stub memory read in full, its target slug)
    for m in memories:
        if m.content_size_bytes > 200:
            continue
        full = client.beta.memory_stores.memories.retrieve(
            m.id, memory_store_id=store_id, view="full"
        )
        match = STUB.match(full.content or "")
        if match:
            found.append((full, match.group(1).strip()))
    stub_ids = {full.id for full, _ in found}
    # The file names (without .md, in any folder) of the memories that are NOT stubs: a node can move folders
    # and keep its name. A stub that points at another stub is followed; a stub, or a loop of stubs, that leads
    # to no such file has a missing target.
    real_stems = {Path(m.path).stem for m in memories if m.id not in stub_ids}
    moved = {}  # a stub's file name -> the slugs its stubs point to
    for full, target in found:
        moved.setdefault(Path(full.path).stem, set()).add(target)

    def exists(slug, seen):
        if slug in real_stems:
            return True
        return slug not in seen and any(exists(t, seen | {slug}) for t in moved.get(slug, ()))

    return [(full, target, exists(target, {Path(full.path).stem})) for full, target in found]


def sweep_stubs(client, store_id):
    """Delete each "MOVED TO" stub whose target exists and return (removed, left): the (path, slug) pairs
    deleted, and the stubs left in place because no memory other than a stub carries their slug, which is worth a
    look. A stub
    is deleted only if its content is still the line that was read (the delete carries its hash)."""
    removed, left = [], []
    for memory, target, exists in find_stubs(client, store_id):
        if not exists:
            left.append((memory.path, target))
            continue
        try:
            client.beta.memory_stores.memories.delete(
                memory.id, memory_store_id=store_id, expected_content_sha256=memory.content_sha256
            )
            removed.append((memory.path, target))
        except anthropic.APIError as exc:
            print(f"Left {memory.path} in place: {exc}")
            left.append((memory.path, target))
    return removed, left


def copy_store(client, source_id, target_id):
    """Copy every memory of one store into another, path for path, and return how many were copied. Raises if
    any memory could not be copied, so a run never starts from a partial copy."""
    memories = list_memories(client, source_id)
    for m in memories:
        full = client.beta.memory_stores.memories.retrieve(
            m.id, memory_store_id=source_id, view="full"
        )
        client.beta.memory_stores.memories.create(
            target_id, path=m.path, content=full.content or ""
        )
    return len(memories)


def download_store(client, store_id, out_dir):
    """Write every memory of a store into out_dir, one file per memory at its path, and return the paths. A
    memory whose path would land outside out_dir, or cannot be written, is printed and skipped."""
    out_dir = private_dir(out_dir).resolve()
    written = []
    for m in list_memories(client, store_id):
        target = (out_dir / m.path.lstrip("/")).resolve()
        if out_dir not in target.parents:
            print(f"Skipped {m.path}: it would be written outside {out_dir.name}/")
            continue
        full = client.beta.memory_stores.memories.retrieve(
            m.id, memory_store_id=store_id, view="full"
        )
        try:
            private_write(target, full.content or "")
        except (OSError, ValueError) as exc:  # e.g. a path another memory uses as a folder
            print(f"Skipped {m.path}: {exc}")
            continue
        written.append(target)
    return written


# --- Checks on the wiki's files --------------------------------------------------------------------

WIKILINK = re.compile(r"\[\[([^\[\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")  # linear: "[" excluded from the target
SLUG_RULE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
ROOT_FILES = {"_index", "_schema", "SKILL", "escalations", "escalations-lower-priority"}
LEGAL_SUFFIXES = {"inc", "inc.", "llc", "l.l.c.", "lp", "l.p.", "ltd", "ltd.", "n.a.", "corp", "corp.", "co."}


def frontmatter_of(text):
    """The key: value lines of a file's leading frontmatter block as a dict of raw strings (no YAML parser:
    the files are written by agents and read by agents, and the checks below only need name and aliases)."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    fields = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" in line and not line.startswith((" ", "\t")):
            key, _, value = line.partition(":")
            fields[key.strip()] = value.strip()
    return fields


def alias_list(raw):
    """Split a frontmatter aliases value written as an inline list, the way an agent reading it would:
    [a, "b, Inc.", c] -> ["a", "b, Inc.", "c"]. Quoted items keep their commas; unquoted ones split on them."""
    raw = raw.strip()
    if raw.startswith("[") and raw.endswith("]"):
        raw = raw[1:-1]
    items, current, quote = [], "", ""
    for ch in raw:
        if quote:
            if ch == quote:
                quote = ""
            else:
                current += ch
        elif ch in "\"'":
            quote = ch
        elif ch == ",":
            items.append(current.strip())
            current = ""
        else:
            current += ch
    items.append(current.strip())
    return [i for i in items if i]


def wiki_lint(files, large_bytes=20_000):
    """Checks on the wiki as a set of files: files maps each store-relative path ("entities/permira.md") to its
    text. Returns a dict of findings, each a list, empty when the check passes:
      dangling_links   (path, target) for every [[link]] whose target is no file's stem; expected in
                       open_questions/ (a redlink marks a gap); elsewhere read them: the target may be a document
                       the corpus lacks, or a node the organizer should have written
      path_links       (path, target) for links written as paths or with .md; they resolve, but the schema
                       asks for bare slugs
      bad_slugs        paths whose stem breaks the slug rule (lowercase letters, digits, single hyphens)
      name_mismatch    (path, name) where the frontmatter name is not the file's stem
      split_aliases    (path, alias) for an alias that is only a legal suffix: an unquoted comma split a name
      shared_aliases   (alias, [paths]) for an alias claimed by more than one entity node
      stubs            paths whose whole content is a MOVED TO line
      not_indexed      paths that _index.md neither links ([[stem]]) nor names by path
      indexed_missing  index entries whose target is no file
      oversized        (path, bytes) for files over large_bytes, largest first (information, not an error)
    """
    stems = {}
    for path in files:
        stems.setdefault(Path(path).stem, []).append(path)
    findings = {k: [] for k in (
        "dangling_links", "path_links", "bad_slugs", "name_mismatch", "split_aliases", "shared_aliases",
        "stubs", "not_indexed", "indexed_missing", "oversized")}
    claimed = {}
    code_span = re.compile(r"`[^`\n]*`")  # links quoted as examples in backticks are not edges
    index_text = files.get("_index.md", "")
    index_targets = {Path(t.strip()).stem for t in WIKILINK.findall(index_text)}
    # per-document files share the document node's slug, so the index may name them by path instead of a link
    # named by path counts with or without the .md suffix, as a whole word (part1 must not match part10)
    index_paths = {
        p for p in files
        if re.search(r"(?<![\w/-])" + re.escape(p.removesuffix(".md")) + r"(?:\.md)?(?![\w-])", index_text)
    }
    for path, text in files.items():
        stem = Path(path).stem
        if path == "_schema.md":  # seeded by the notebook, never edited; its links are examples
            continue
        if STUB.match(text or ""):
            findings["stubs"].append(path)
            continue
        if stem not in ROOT_FILES and not SLUG_RULE.match(stem):
            findings["bad_slugs"].append(path)
        fm = frontmatter_of(text)
        if stem != "SKILL" and fm.get("name") and fm["name"].strip("\"'") != stem:
            findings["name_mismatch"].append((path, fm["name"]))
        if path.startswith("entities/"):
            for alias in alias_list(fm.get("aliases", "")):
                if alias.lower() in LEGAL_SUFFIXES:
                    findings["split_aliases"].append((path, alias))
                else:
                    claimed.setdefault(alias.lower(), []).append(path)
        for target in WIKILINK.findall(code_span.sub("", text)):
            target = target.strip()
            target_stem = Path(target).stem if ("/" in target or target.endswith(".md")) else target
            if target_stem not in stems:
                findings["dangling_links"].append((path, target))
            elif target_stem != target:
                findings["path_links"].append((path, target))
        if stem not in ROOT_FILES and stem not in index_targets and path not in index_paths:
            findings["not_indexed"].append(path)
        size = len((text or "").encode())
        if size > large_bytes:
            findings["oversized"].append((path, size))
    findings["shared_aliases"] = [(a, sorted(p)) for a, p in claimed.items() if len(set(p)) > 1]
    findings["indexed_missing"] = sorted(index_targets - set(stems) - {""})
    findings["oversized"].sort(key=lambda item: -item[1])
    return findings


def lint_summary(findings, show=5):
    """One line per check: the count and the first few findings (for oversized files, which are information and
    not an error, the count alone; export_report prints the largest one)."""
    lines = []
    for name, items in findings.items():
        label = name.replace("_", " ")
        if not items:
            lines.append(f"{label}: none")
            continue
        if name == "oversized":
            lines.append(f"{label}: {len(items)} (information, not an error; the largest is shown below)")
            continue
        sample = "; ".join(str(i) for i in items[:show])
        more = f" (+{len(items) - show} more)" if len(items) > show else ""
        lines.append(f"{label}: {len(items)} - {sample}{more}")
    return "\n".join(lines)


def read_sizes(events):
    """From one session's events (export dicts or SDK objects), the characters each read or search returned,
    keyed by the store-relative path (or the search pattern): where a question's new tokens came from."""
    inputs, sizes = {}, {}
    for ev in events:
        get = ev.get if isinstance(ev, dict) else (lambda k, d=None, ev=ev: getattr(ev, k, d))
        kind = get("type", "")
        if kind == "agent.tool_use":
            inp = get("input") or {}
            inp = inp if isinstance(inp, dict) else dict(inp)
            path = inp.get("file_path") or inp.get("path") or ""
            label = _store_rel(str(path)) if path else ""
            if get("name") in ("grep", "glob"):
                label = f"{get('name')} {inp.get('pattern', '')!s:.40} {label}".strip()
            inputs[get("id")] = label or get("name", "?")
        elif kind == "agent.tool_result":
            label = inputs.get(get("tool_use_id"), "?")
            chars = sum(len(text_of([block])) for block in (get("content") or []))
            sizes[label] = sizes.get(label, 0) + chars
    return sizes


VERSIONS_LISTED = 2000  # how many memory versions written_by_session lists at most


def written_by_session(client, store_id, session_id, limit=VERSIONS_LISTED):
    """The memory versions in a store that a given session wrote, newest first (at most limit): each create,
    change or delete its agents made through the store's mount."""
    listing = client.beta.memory_stores.memory_versions.list(
        store_id, session_id=session_id, limit=100
    )
    return list(itertools.islice(listing, limit))


# --- Prices and the estimate ------------------------------------------------------------------------

# US dollars per million tokens at list price, from https://platform.claude.com/docs/en/about-claude/pricing.
# cache_write is the 5-minute rate; a 1-hour cache write costs twice the input price. Prices change: check the
# page before relying on a figure. These feed the estimate; what a run actually cost is read from the platform.
PRICES = {
    "claude-opus-5-5": {"input": 4.00, "cache_write": 5.00, "cache_read": 0.20, "output": 20.00},
    "claude-sonnet-5-5": {"input": 2.00, "cache_write": 2.50, "cache_read": 0.10, "output": 10.00},
    "claude-haiku-5-5": {"input": 0.10, "cache_write": 0.125, "cache_read": 0.01, "output": 0.50},
    "claude-fable-5-1": {"input": 10.00, "cache_write": 12.50, "cache_read": 0.25, "output": 50.00},
    "claude-opus-5": {"input": 5.00, "cache_write": 6.25, "cache_read": 0.50, "output": 25.00},
    "claude-sonnet-5": {"input": 2.00, "cache_write": 2.50, "cache_read": 0.20, "output": 10.00},
}
# A Claude Haiku 5.5 request whose prompt is over 100,000 tokens pays these instead (same page, "Long context
# pricing"). The estimate and question_usd apply them to any request whose prompt passes that size.
LONG_PROMPT_PRICES = {
    "claude-haiku-5-5": {
        "over": 100_000,
        "input": 0.50,
        "cache_write": 0.625,
        "cache_read": 0.05,
        "output": 2.50,
    }
}
DEFAULT_PRICED_AS = "claude-opus-5-5"
SESSION_HOUR_USD = 0.08  # session running time, per hour

# What the estimate assumes about each agent's work: rough figures to start from, not measurements of your
# corpus. After a run the notebook prints what the run cost beside the estimate, so you can adjust them. An
# extractor reads its whole batch and writes many wiki files, so its output is large; an analyzer reads the same
# batch again plus the wiki files on its topics, and writes less.
CHARS_PER_TOKEN = 3.5  # filings and notes are mostly prose and tables
FIXED_TOKENS = 6_000  # system prompt, tool definitions and task, present on every request
# Calibrated on one recorded build (25 batches of about 110,000 characters each, claude-sonnet-5): requests per
# agent, and what it reads and writes as multiples of its batch's tokens. Your corpus and model will differ.
EXTRACTOR = {"requests": 41, "reads": 3.2, "output": 1.75}
ANALYZER = {"requests": 56, "reads": 5.2, "output": 1.2}
MIN_OUTPUT_TOKENS = 3_000
# The single agents, from the same run; the resolver's and organizer's reading grows with the wiki's size.
RESOLVER_TOKENS = {"cache_write": 180_000, "cache_read": 7_700_000, "output": 52_000}
ORGANIZER_TOKENS = {"cache_write": 400_000, "cache_read": 31_000_000, "output": 120_000}
LEAD_TOKENS = {
    "cache_write": 90_000,
    "cache_read": 135_000,
    "output": 18_000,
}  # writing and watching one run


def prices_of(model, prompt_tokens=0):
    """(prices, note): the list prices for a model at this prompt size, or DEFAULT_PRICED_AS's with a note
    saying so."""
    long_prices = LONG_PROMPT_PRICES.get(model)
    if long_prices and prompt_tokens > long_prices["over"]:
        return long_prices, ""
    if model in PRICES:
        return PRICES[model], ""
    return PRICES[DEFAULT_PRICED_AS], (
        f"{model} has no price in utilities.PRICES, so the estimate uses {DEFAULT_PRICED_AS}'s "
        "prices for it and may be off."
    )


def dollars(tokens, prices):
    """The list price of {input, cache_write, cache_write_1h, cache_read, output} token counts."""
    usd_amount = sum(
        tokens.get(k, 0) * prices[k] for k in ("input", "cache_write", "cache_read", "output")
    )
    usd_amount += tokens.get("cache_write_1h", 0) * prices["input"] * 2
    return usd_amount / 1e6


def usd(amount):
    """A dollar amount for printing, such as $1,234.56."""
    return f"${amount:,.2f}"


def question_usd(stats, model=None):
    """The list price of one question session. Requests recorded in stats["calls"] are priced one by one, so a
    prompt past a model's long-context threshold (LONG_PROMPT_PRICES) pays those prices; otherwise the totals pay
    base prices. The model is stats["model"], else model, else DEFAULT_PRICED_AS."""
    model = stats.get("model") or model or DEFAULT_PRICED_AS
    calls = stats.get("calls")
    if not calls:
        prices, _ = prices_of(model)
        return dollars(stats, prices)
    total = 0.0
    for call in calls:
        prompt_tokens = call.get("input", 0) + call.get("cache_write", 0) + call.get("cache_read", 0)
        prices, _ = prices_of(model, prompt_tokens=prompt_tokens)
        total += dollars(call, prices)
    return total


def agent_model(agent):
    """The model id an agent was created with (its model field is a string or an object with an id), or None."""
    model = getattr(agent, "model", None)
    return getattr(model, "id", model) if model else None


def worker_tokens(batch_chars, profile):
    """The token counts the estimate assumes for one extractor or analyzer on a batch of this size. What it
    reads and writes enters the context once (cache writes); every later request re-reads the context so far
    (cache reads), taken as half the final context on average."""
    batch = batch_chars / CHARS_PER_TOKEN
    output = max(MIN_OUTPUT_TOKENS, batch * profile["output"])
    context = FIXED_TOKENS + batch * profile["reads"] + output
    return {
        "cache_write": context,
        "cache_read": profile["requests"] * context / 2,
        "output": output,
    }


def _priced(tokens, model, notes):
    prices, note = prices_of(model, prompt_tokens=tokens["cache_write"])
    notes.append(note)
    return dollars(tokens, prices)


def estimate_build_cost(batch_sizes, build_model, consolidate_model, lead_model):
    """(usd, lines): a rough list-price estimate for one build run over batches of these sizes (characters),
    and the lines that explain it. Extractors and the resolver run on build_model, analyzers and the organizer
    on consolidate_model, the lead agent on lead_model."""
    notes = []
    extract = sum(_priced(worker_tokens(s, EXTRACTOR), build_model, notes) for s in batch_sizes)
    analyze = sum(
        _priced(worker_tokens(s, ANALYZER), consolidate_model, notes) for s in batch_sizes
    )
    resolve = _priced(RESOLVER_TOKENS, build_model, notes)
    organize = _priced(ORGANIZER_TOKENS, consolidate_model, notes)
    lead = _priced(LEAD_TOKENS, lead_model, notes)
    total = extract + resolve + analyze + organize + lead
    chars = sum(batch_sizes)
    lines = [
        f"{len(batch_sizes)} batches, {chars / 1000:,.0f} KB of text in all "
        f"(about {chars / CHARS_PER_TOKEN:,.0f} tokens).",
        f"Estimated list price {usd(total)}: extraction on {build_model} {usd(extract)} + resolver "
        f"{usd(resolve)}, consolidation on {consolidate_model} {usd(analyze)} (analyzers) + {usd(organize)} "
        f"(organizer), lead agent on {lead_model} {usd(lead)}. Session running time is extra, at "
        f"{usd(SESSION_HOUR_USD)} an hour.",
    ]
    lines += sorted({n for n in notes if n})
    return total, lines


def usage_tokens(usage):
    """A thread's or session's usage object as token counts: input, cache_write (5-minute), cache_write_1h,
    cache_read and output."""
    counts = {"input": 0, "cache_write": 0, "cache_write_1h": 0, "cache_read": 0, "output": 0}
    if usage is None:
        return counts
    u = usage if isinstance(usage, dict) else usage.model_dump(mode="json")
    counts["input"] = int(u.get("input_tokens") or 0)
    counts["cache_read"] = int(u.get("cache_read_input_tokens") or 0)
    counts["output"] = int(u.get("output_tokens") or 0)
    creation = u.get("cache_creation") if isinstance(u.get("cache_creation"), dict) else {}
    counts["cache_write_1h"] = int(creation.get("ephemeral_1h_input_tokens") or 0)
    five_minute = creation.get("ephemeral_5m_input_tokens")
    if five_minute is None:  # older shape: one total for all cache writes
        five_minute = (u.get("cache_creation_input_tokens") or 0) - counts["cache_write_1h"]
    counts["cache_write"] = max(0, int(five_minute or 0))
    return counts


def thread_model(thread):
    """The model id that the thread's agent snapshot names, or None."""
    model = getattr(thread.agent, "model", None)
    return getattr(model, "id", model) if model else None


def usage_rows(threads, default_model):
    """One row per thread: agent name, model, status, token counts, the platform's own list_cost for the thread
    (tokens at public list rates, rounded per thread; None until the thread has been idle once), and the same
    tokens priced from PRICES for comparison. A thread whose snapshot names no model is priced at
    default_model."""
    rows = []
    for t in threads:
        model = thread_model(t) or default_model
        tokens = usage_tokens(t.usage)
        prices, _ = prices_of(model)
        list_cost = getattr(t.usage, "list_cost", None) if t.usage else None
        rows.append(
            {
                "thread": t.id,
                "agent": getattr(t.agent, "name", None) or getattr(t.agent, "type", ""),
                "model": model,
                "status": t.status,
                "workflow_run_id": t.workflow_run_id,
                **tokens,
                "list_cost_usd": int(list_cost.amount) / 100 if list_cost else None,
                "priced_usd": dollars(tokens, prices),
                "active_seconds": getattr(t.usage, "active_seconds", None) if t.usage else None,
            }
        )
    return rows


def usage_summary(rows):
    """Totals over usage_rows, per agent name and overall, as printable lines. "list" is the platform's figure,
    "priced" the same tokens at the prices in PRICES."""
    lines, by_agent = [], {}
    for r in rows:
        a = by_agent.setdefault(
            r["agent"], {"threads": 0, "list": 0.0, "priced": 0.0, "out": 0, "in": 0}
        )
        a["threads"] += 1
        a["list"] += r["list_cost_usd"] or 0.0
        a["priced"] += r["priced_usd"]
        a["out"] += r["output"]
        a["in"] += r["input"] + r["cache_write"] + r["cache_write_1h"] + r["cache_read"]
    for name, a in by_agent.items():
        lines.append(
            f"{name:>20}: {a['threads']:3} threads, {a['in']:>12,} tokens in, {a['out']:>10,} out, "
            f"list {usd(a['list'])}, priced {usd(a['priced'])}"
        )
    total_list = sum((r["list_cost_usd"] or 0.0) for r in rows)
    total_priced = sum(r["priced_usd"] for r in rows)
    lines.append(
        f"{'all threads':>20}: list {usd(total_list)}, priced {usd(total_priced)} (tokens only)"
    )
    unpriced = [r["thread"] for r in rows if not r["list_cost_usd"] and r["output"]]
    if unpriced:
        lines.append(
            f"{len(unpriced)} threads used tokens but carry no list cost (yet): their 'list' figure "
            "above is low; the 'priced' figure is the estimate to go by for them."
        )
    long_models = sorted({r["model"] for r in rows if r["model"] in LONG_PROMPT_PRICES})
    if long_models:
        lines.append(
            f"'priced' uses base prices. On {', '.join(long_models)}, a request with a prompt over "
            f"{min(LONG_PROMPT_PRICES[m]['over'] for m in long_models):,} tokens costs more, and only 'list' includes "
            "that. Go by 'list' for any thread that has one."
        )
    return lines


def row_usd(row):
    """A thread's cost for the tables: the platform's list cost when it gave one above zero, else the same
    tokens priced from PRICES (an estimate)."""
    return row["list_cost_usd"] if row["list_cost_usd"] else row["priced_usd"]


def usage_by_agent(rows):
    """{agent name: dollars} over usage_rows, by row_usd."""
    totals = {}
    for r in rows:
        totals[r["agent"]] = totals.get(r["agent"], 0.0) + row_usd(r)
    return totals


def list_usd(usage):
    """The platform's list cost on a session's or thread's usage object, in dollars (the amount is a string of
    whole US cents), or None when it carries none."""
    cost = getattr(usage, "list_cost", None) if usage is not None else None
    return int(cost.amount) / 100 if cost is not None and cost.amount is not None else None


# --- Following the session until the work is done -------------------------------------------------


@dataclass
class RunRecord:
    """What the event stream showed of one workflow run. Times are seconds since the message was sent."""

    id: str
    name: str = ""
    description: str | None = None
    phases: dict = field(default_factory=dict)  # phase id: phase name, from workflow_run.created
    phase_log: list = field(default_factory=list)  # (seconds, "started" or "ended", phase name)
    result: dict | None = None  # from workflow_run.status_ended
    # thread id: {"agent": name, "started": s, "ended": s}
    threads: dict = field(default_factory=dict)
    errors: list = field(default_factory=list)


@dataclass
class Followed:
    """What follow() saw: every run by id, why it stopped, the agent's last message, how long it took, the tool
    confirmations it denied, and the session errors it saw."""

    runs: dict = field(default_factory=dict)
    stop: str = ""
    last_message: str = ""
    seconds: float = 0.0
    # (thread id, tool name or event id) answered with deny
    denied: list = field(default_factory=list)
    errors: list = field(default_factory=list)  # (error type, message) of each session.error
    # the same, for errors the server said it was retrying
    retried: list = field(default_factory=list)


STOP_REASONS = {
    "idle": "the agent finished, with no run left open",
    "budget_reached": "the session reached its budget and paused; the clean-up below ends the run, so the "
    "wiki holds only part of the corpus. Raise BUDGET_USD (or COOKBOOK_BUDGET_USD) and build again "
    "into a new store",
    "retries_exhausted": "the agent's turn failed after retries; the session errors are printed above",
    "refusal": "the model declined the request",
    "terminated": "the session was terminated; any session errors are printed above",
    "timeout": "this notebook stopped waiting; the run may still be going",
}


def describe_stop(stop):
    """A stop code from follow() in words."""
    return STOP_REASONS.get(stop, stop)


def text_of(content):
    """The text of a message's content blocks (objects or plain dicts)."""
    parts = []
    for b in content or []:
        kind = b.get("type") if isinstance(b, dict) else getattr(b, "type", "")
        if kind == "text":
            parts.append(b.get("text", "") if isinstance(b, dict) else b.text)
    return "".join(parts)


def deny_event(event_id):
    """The event that denies one tool call waiting for confirmation."""
    return {
        "type": "user.tool_confirmation",
        "tool_use_id": event_id,
        "result": "deny",
        "deny_message": "This run is unattended; calls that need confirmation are denied.",
    }


def same_text(event, message):
    """Whether a user.message event carries message, ignoring differences in whitespace."""
    blocks = getattr(event, "content", None) or []
    text = "".join((b.get("text") if isinstance(b, dict) else getattr(b, "text", None)) or "" for b in blocks)
    return squash(text) == squash(message or "")


def follow(client, session_id, message, timeout_s=6 * 3600, quiet=False, on_event=None, out=None, sent=False):
    """Send message (unless sent=True says the caller already has), then read the session's events until every
    workflow run seen has ended and the session is idle with end_turn; with sent=True nothing listed before the
    caller's message (the newest user.message with that text, whitespace aside) counts, so an earlier turn is
    passed over, and everything the stream then delivers is read. Prints
    runs, phases and thread starts unless quiet, and denies tool calls that wait for confirmation. Returns a
    Followed whose stop is "idle", budget_reached, retries_exhausted, refusal, terminated, or timeout after
    timeout_s. on_event(ev) may return a string to stop with it; pass your own Followed as out to keep what was
    seen if this call is interrupted."""
    events = client.beta.sessions.events
    out = Followed() if out is None else out
    seen, answered, pending = set(), set(), {}
    started = time.monotonic()
    last_retry = {"at": 0.0}
    deadline = started + timeout_s
    grace = {
        "until": None
    }  # after retries_exhausted with no run open, wait this long for a new turn

    def say(text):
        if not quiet:
            print(f"[{time.monotonic() - started:5.0f}s] {text}", flush=True)

    def now():
        return round(time.monotonic() - started)

    def run_of(ev):
        return out.runs.setdefault(ev.workflow_run_id, RunRecord(ev.workflow_run_id))

    def deny(event_id, thread_id, label):
        if event_id in answered:
            return
        try:
            events.send(session_id, events=[deny_event(event_id)])
        except anthropic.APIError as exc:
            # A 400 can mean the call's own event hasn't reached this stream yet (or that it was already
            # answered); other errors are transient. The id stays pending and is tried again on later events.
            pending[event_id] = (thread_id, label)
            say(f"could not deny the {label} call yet: {exc}")
        else:
            answered.add(event_id)
            pending.pop(event_id, None)
            out.denied.append((thread_id, label))

    def retry_pending():
        if pending and time.monotonic() - last_retry["at"] > 10:
            last_retry["at"] = time.monotonic()
            for event_id, (thread_id, label) in list(pending.items()):
                deny(event_id, thread_id, label)

    def handle(ev, live=False):
        if ev.id in seen:
            return None
        seen.add(ev.id)
        retry_pending()
        if on_event:
            stop = on_event(ev)
            if stop:
                return stop
        kind = ev.type
        if waiting["message"]:
            # sent=True and the caller's message not read yet. Anything from the stream is newer than the caller's
            # send, so it ends the wait and is read; in a listing, the newest user.message with the caller's text
            # ends it, and whatever is listed before that belongs to an earlier turn and is passed over.
            if live:
                waiting["message"] = False
            elif kind == "user.message" and ev.id == waiting["id"]:
                waiting["message"] = False
                return None
            else:
                return None
        if kind == "workflow_run.created":
            run = run_of(ev)
            run.name, run.description = ev.name, ev.description
            run.phases = {p.id: p.name for p in ev.phases}
            say(f"run started: {ev.name!r}, phases {list(run.phases.values())}")
        elif kind in ("workflow_run.phase_started", "workflow_run.phase_ended"):
            run = run_of(ev)
            name = run.phases.get(ev.workflow_run_phase_id, ev.workflow_run_phase_id)
            verb = kind.rsplit("_", 1)[1]
            run.phase_log.append((now(), verb, name))
            say(f"phase {verb}: {name}")
        elif kind == "workflow_run.status_ended":
            run = run_of(ev)
            run.result = ev.result.model_dump(mode="json")
            error = run.result.get("error") or {}
            detail = f" ({error.get('type')}: {error.get('message')})" if error else ""
            say(f"run ended: {run.result.get('type')}{detail}")
        elif kind == "workflow_run.status_idle":
            say("run paused; the event doesn't say why (a session at its budget is one cause)")
        elif kind == "workflow_run.error":
            error = f"{ev.error.type}: {ev.error.message}"
            if ev.workflow_run_id:
                run_of(ev).errors.append(error)
            out.errors.append(("workflow_run.error", error))
            say(f"workflow error: {error}")
        elif kind == "session.thread_created" and getattr(ev, "workflow_run_id", None):
            run = run_of(ev)
            run.threads[ev.session_thread_id] = {
                "agent": ev.agent_name,
                "started": now(),
                "ended": None,
            }
            counts = {}
            for t in run.threads.values():
                counts[t["agent"]] = counts.get(t["agent"], 0) + 1
            shown = ", ".join(f"{c} {n}" for n, c in counts.items())
            say(f"thread started: {ev.agent_name} ({shown} threads so far)")
        elif kind in ("session.thread_status_idle", "session.thread_status_terminated"):
            thread_id = getattr(ev, "session_thread_id", None)
            stop_reason = getattr(ev, "stop_reason", None)
            if getattr(stop_reason, "type", None) == "requires_action":
                # A run thread waits for a confirmation: deny it; the thread has not ended.
                for event_id in getattr(stop_reason, "event_ids", None) or []:
                    deny(event_id, thread_id, event_id)
            else:
                for run in out.runs.values():
                    if thread_id in run.threads and run.threads[thread_id]["ended"] is None:
                        run.threads[thread_id]["ended"] = now()
        elif kind in ("agent.tool_use", "agent.mcp_tool_use"):
            # A tool whose permission policy asks for confirmation waits on your client; nobody is watching
            # this run, so the call is denied. A run thread's waiting call arrives on this stream too.
            if getattr(ev, "evaluated_permission", None) == "ask":
                deny(ev.id, getattr(ev, "session_thread_id", None), getattr(ev, "name", ev.id))
        elif kind == "agent.message":
            out.last_message = text_of(ev.content)
        elif kind == "session.error":
            error = getattr(ev, "error", None)
            entry = (getattr(error, "type", ""), getattr(error, "message", ""))
            retrying = getattr(getattr(error, "retry_status", None), "type", None) == "retrying"
            (out.retried if retrying else out.errors).append(entry)
            say(f"session error{' (server retrying)' if retrying else ''}: {entry[0]} {entry[1]}")
        elif kind == "session.status_running":
            grace["until"] = None  # the server started another turn
        elif kind == "session.status_idle":
            reason = getattr(ev.stop_reason, "type", None)
            open_runs = [r for r in out.runs.values() if r.result is None]
            if reason == "requires_action":
                # Deny whatever is still waiting, in case its tool_use event was missed.
                for event_id in getattr(ev.stop_reason, "event_ids", None) or []:
                    deny(event_id, None, event_id)
            elif reason == "budget_reached":
                return reason
            elif reason in ("end_turn", "refusal") and not open_runs:
                return "idle" if reason == "end_turn" else reason
            elif reason == "retries_exhausted" and not open_runs:
                # The server may start one more turn by itself (a run ended unread); give it two minutes.
                grace["until"] = time.monotonic() + 120
            # With a run still open, keep reading: the agent gets another turn when the run ends.
        elif kind in ("session.status_terminated", "session.deleted"):
            return "terminated"
        return None

    def finish(stop):
        out.stop, out.seconds = stop, time.monotonic() - started
        return out

    # sent=True: the caller already sent the message, so the first connection starts from the event list, where
    # everything before that message is an earlier turn's and is passed over.
    waiting = {"message": sent, "id": None}
    last_seen, failures = None, 0
    while time.monotonic() < deadline:
        fired = threading.Event()
        timer = None
        # Each connection lives at most until the deadline, the end of a grace period, or ten minutes: its read
        # timeout is set just past that, and a timer closes it too, so a silent stream can't outwait timeout_s.
        wake = min(deadline, grace["until"] or deadline, time.monotonic() + 600)
        # Counted from the last byte received, so it is also capped: a quiet connection is reopened every couple
        # of minutes (a reconnect costs one list call; events already seen are skipped).
        read_timeout = min(max(5.0, wake - time.monotonic()), 120.0) + 5
        try:
            retry_pending()
            with events.stream(session_id, timeout=read_timeout) as stream:

                def cut(stream=stream, fired=fired):
                    fired.set()
                    with contextlib.suppress(Exception):
                        stream.close()

                timer = threading.Timer(max(0.0, wake - time.monotonic()), cut)
                timer.daemon = True
                timer.start()
                if sent:
                    # Catch up on what arrived while disconnected; handle() skips what it has seen.
                    query = {"order": "asc"}
                    if last_seen is not None:
                        query["created_at_gte"] = last_seen - timedelta(minutes=1)
                    missed = events.list(session_id, **query)
                    if waiting["message"]:
                        # The newest listed user.message with the caller's text is the one (the same text may have
                        # been sent before in this session).
                        missed = list(missed)
                        ours = [ev.id for ev in missed if ev.type == "user.message" and same_text(ev, message)]
                        waiting["id"] = ours[-1] if ours else None
                else:
                    content = [{"type": "text", "text": message}]
                    events.send(session_id, events=[{"type": "user.message", "content": content}])
                    sent, missed = True, []
                tagged = itertools.chain(((ev, False) for ev in missed), ((ev, True) for ev in stream))
                for ev, live in tagged:  # live: from the stream, so newer than the caller's send
                    if getattr(ev, "processed_at", None):
                        last_seen = (
                            ev.processed_at
                            if last_seen is None
                            else max(last_seen, ev.processed_at)
                        )
                    stop = handle(ev, live)
                    if stop:
                        return finish(stop)
                    if time.monotonic() > deadline:
                        return finish("timeout")
                failures = 0
        except Exception as exc:
            if not sent:
                raise
            timed_out = (
                "Timeout" in type(exc).__name__
            )  # the connection's own read timeout: reconnect now
            if not fired.is_set() and not timed_out:
                if isinstance(exc, (AttributeError, TypeError, KeyError, NameError)):
                    raise  # a bug, not a connection problem
                if isinstance(exc, anthropic.APIStatusError) and exc.status_code in (
                    400,
                    401,
                    403,
                    404,
                    422,
                ):
                    raise  # retrying won't help
                failures += 1
                say(f"stream error ({type(exc).__name__}); reconnecting")
                time.sleep(min(60, 2**failures))
        else:
            say("(stream closed; reconnecting)")
            time.sleep(1)
        finally:
            if timer is not None:
                timer.cancel()
        if grace["until"] is not None and time.monotonic() >= grace["until"]:
            return finish("retries_exhausted")
    return finish("timeout")


def waiting_confirmations(client, session_id):
    """The event ids the session is waiting on a confirmation for, from its latest idle event, or []."""
    listing = client.beta.sessions.events.list(
        session_id, order="desc", types=["session.status_idle"], limit=1
    )
    for ev in listing:
        if getattr(ev.stop_reason, "type", None) == "requires_action":
            return list(getattr(ev.stop_reason, "event_ids", None) or [])
        break
    return []


def open_run_ids(client, session_id, followed=None):
    """The ids of workflow runs created in the session and not ended, rebuilt from the event list, which is
    where runs are recorded, plus any that followed saw open."""
    events = client.beta.sessions.events
    created = {
        e.workflow_run_id
        for e in events.list(session_id, types=["workflow_run.created"], limit=100)
    }
    ended = {
        e.workflow_run_id
        for e in events.list(session_id, types=["workflow_run.status_ended"], limit=100)
    }
    seen_open = {rid for rid, r in (followed.runs.items() if followed else []) if r.result is None}
    return (created | seen_open) - ended


def stop_runs(client, session_id, followed=None, wait_s=180):
    """Deny any confirmation the session is waiting on; if any workflow run is open (by the server's events,
    plus what followed saw), ask the agent to stop its runs and wait up to wait_s in all for them to end;
    then interrupt the session if it is still running and deny anything left waiting. Returns the ids of
    runs still open afterwards. A session idle at its budget can't take a message, so its runs are left to
    the delete or archive that follows."""
    sessions = client.beta.sessions
    for event_id in waiting_confirmations(client, session_id):
        with contextlib.suppress(anthropic.APIError):
            sessions.events.send(session_id, events=[deny_event(event_id)])
    open_runs = open_run_ids(client, session_id, followed)
    at_budget = followed is not None and followed.stop == "budget_reached"
    if open_runs and not at_budget:
        content = [
            {"type": "text", "text": "Stop all of your workflow runs now and end your turn."}
        ]
        try:
            sessions.events.send(session_id, events=[{"type": "user.message", "content": content}])
        except anthropic.BadRequestError as exc:
            print(
                f"Could not ask the agent to stop its runs ({exc}); archiving the session will end them, and "
                "any run still open is listed below."
            )
        else:
            deadline = time.monotonic() + wait_s
            while open_runs and time.monotonic() < deadline:
                time.sleep(10)
                open_runs = open_run_ids(client, session_id)
    status = sessions.retrieve(session_id).status
    if status == "running":
        with contextlib.suppress(anthropic.APIError):
            sessions.events.send(session_id, events=[{"type": "user.interrupt"}])
        deadline = time.monotonic() + 60
        while status == "running" and time.monotonic() < deadline:
            time.sleep(3)
            status = sessions.retrieve(session_id).status
    for event_id in waiting_confirmations(client, session_id):
        with contextlib.suppress(anthropic.APIError):
            sessions.events.send(session_id, events=[deny_event(event_id)])
    return sorted(open_runs)


ASK_FOR_WORKFLOW = (
    "Print the workflow that you started the run with, word for word, in one code block. "
    "Do not start another run."
)


def ask_for_workflow(client, session_id, timeout_s=900):
    """Ask the agent to print the workflow it started the run with; return (code, the whole reply, what
    follow() saw). Send it once the run has ended and the session is idle. The code is the first fenced block of
    the reply, or an empty string. It is the agent's own account: the platform does not return the program it ran."""
    reply = follow(client, session_id, ASK_FOR_WORKFLOW, timeout_s=timeout_s, quiet=True)
    return extract_code_block(reply.last_message), reply.last_message, reply


FENCE = chr(96) * 3  # three backticks


def extract_code_block(text):
    """The contents of the first fenced code block in text, or an empty string if there is none."""
    m = re.search(FENCE + r"[^\n]*\n(.*?)" + FENCE, text or "", flags=re.DOTALL)
    return m.group(1).strip() if m else ""


def extract_json_object(text):
    """The last top-level JSON object in text, parsed, or None: the report the message asks the agent to end
    its reply with."""
    decoder, found, position = json.JSONDecoder(), None, 0
    text = text or ""
    while (start := text.find("{", position)) != -1:
        try:
            value, end = decoder.raw_decode(text, start)
        except json.JSONDecodeError:
            position = start + 1
            continue
        if isinstance(value, dict):
            found = value
        position = end
    return found


# --- What ran: the run's threads and the checks ----------------------------------------------------


def complete_threads(client, session_id, threads, followed):
    """The session's threads, each once, plus any run thread that the event stream announced but the list left
    out, fetched by id. The list includes archived threads, so this is usually a no-op."""
    by_id = {}
    for t in threads:
        by_id.setdefault(t.id, t)
    announced = [tid for run in (followed.runs.values() if followed else []) for tid in run.threads]
    for thread_id in announced:
        if thread_id not in by_id:
            with contextlib.suppress(anthropic.APIError):
                by_id[thread_id] = client.beta.sessions.threads.retrieve(
                    thread_id, session_id=session_id
                )
    return sorted(by_id.values(), key=lambda t: t.created_at)


def tool_paths(tool_input):
    """The file-system paths a file tool call names in its input (file_path, path, or a pattern's folder)."""
    found = []
    for key in ("file_path", "path", "directory", "pattern"):
        value = (tool_input or {}).get(key)
        if isinstance(value, str) and value.startswith("/"):
            found.append(value)
    return found


def thread_records(client, session_id, threads, mem_dir=""):
    """For each of a run's threads, what its own event stream shows: the prompt the workflow gave it (its first
    agent.thread_message_received, whose wording the docs don't guarantee), the sandbox paths its tool calls read,
    how many writes it made under mem_dir, the errors its stream recorded (those the server said it was retrying
    under "retried"), and a preview of its last message. Returns {thread id: record}."""
    records = {}
    for t in threads:
        rec = {"prompt": "", "reads": set(), "writes": 0, "tool_calls": 0, "errors": [], "retried": [], "last": ""}
        first_user = ""
        for ev in client.beta.sessions.threads.events.list(t.id, session_id=session_id):
            if ev.type == "agent.thread_message_received" and not rec["prompt"]:
                rec["prompt"] = text_of(ev.content)
            elif ev.type == "user.message" and not first_user:
                first_user = text_of(ev.content)
            elif ev.type == "agent.tool_use":
                rec["tool_calls"] += 1
                paths = tool_paths(getattr(ev, "input", None))
                if ev.name in ("write", "edit"):
                    if mem_dir and any(p.startswith(mem_dir) for p in paths):
                        rec["writes"] += 1
                elif ev.name == "read":  # a glob or grep lists a folder; only read opens a file
                    rec["reads"].update(paths)
            elif ev.type == "session.error":
                error = getattr(ev, "error", None)
                text = f"{getattr(error, 'type', '')}: {getattr(error, 'message', '')}"
                retrying = getattr(getattr(error, "retry_status", None), "type", None) == "retrying"
                rec["retried" if retrying else "errors"].append(text)
            elif ev.type == "agent.message":
                rec["last"] = text_of(ev.content)[:300]
        rec["prompt"] = rec["prompt"] or first_user
        rec["reads"] = sorted(rec["reads"])
        records[t.id] = rec
    return records


@dataclass
class Check:
    what: str
    passed: bool | None  # None: information, neither pass nor fail
    detail: str = ""


@dataclass
class Expected:
    """One kind of agent the message asked the run to start, in the order the message gave: the role (a key into
    the agents the notebook created), the input paths it should have been started once each for (an empty list
    means at least once, with no input of its own), and, for the record of each thread's prompt, the task
    template the message embedded and the placeholder each input path replaced in it."""

    role: str
    inputs: list = field(default_factory=list)
    task: str = ""
    placeholder: str = ""


def squash(text):
    """Text with its whitespace runs collapsed, for comparisons that ignore wrapping."""
    return " ".join((text or "").split())


def threads_by_role(threads, agents):
    """({role: [threads, oldest first]}, [descriptions of threads that ran something else or another version])."""
    by_id = {a.id: role for role, a in agents.items()}
    roles, strangers = {}, []
    for t in sorted(threads, key=lambda t: t.created_at):
        role = by_id.get(getattr(t.agent, "id", None))
        if role is None:
            strangers.append(
                f"{t.id} ran {getattr(t.agent, 'type', '?')} {getattr(t.agent, 'name', '')}"
            )
            continue
        roles.setdefault(role, []).append(t)
        if getattr(t.agent, "version", None) != agents[role].version:
            strangers.append(
                f"{t.id} ran {role} version {t.agent.version}, not {agents[role].version}"
            )
    return roles, strangers


def check_run(
    run, threads, records, agents, expected, report, want_name, want_phases, report_counts=None
):
    """The checks the notebook makes on one run from the platform's records, not from the agent's words: the
    run's recorded name and phases (shown as the lead agent declared them, or compared with the ones the message asked
    for when it named them) and that the phases ran one at a time in the declared order; every thread ran one of your agents at the version you created; for each expected role, enough
    threads started, after every thread of the role before it had ended, each input was read by at least one
    of them (from the threads' own tool calls), and none recorded an error; the run ended completed; and the
    agent's report agrees with the thread list. run is follow()'s RunRecord; records is thread_records()."""
    checks = []
    declared = list(run.phases.values())
    if want_name is not None:  # the message named the run and its phases: compare (with none named, show_checks prints what the lead agent chose)
        matched = run.name == want_name and declared == list(want_phases or [])
        checks.append(
            Check(
                "The run the platform recorded has the name and the phases the message asked for",
                matched,
                f"recorded {run.name!r} with phases {declared}"
                + ("" if matched else f"; the message asked for {want_name!r} with phases {list(want_phases)}"),
            )
        )
    log = [(verb, name) for _, verb, name in run.phase_log]
    started = [name for verb, name in log if verb == "started"]
    overlapped = any(log[i][0] == "started" == log[i + 1][0] for i in range(len(log) - 1))
    checks.append(
        Check(
            "The phases ran one at a time, in the declared order",
            bool(started) and started == declared[: len(started)] and not overlapped,
            f"ran {started}" + ("; two phases were open at once" if overlapped else ""),
        )
    )
    roles, strangers = threads_by_role(threads, agents)
    checks.append(
        Check(
            "Every thread of the run ran one of your agents, at the version you created",
            not strangers,
            "; ".join(strangers) or f"{len(threads)} threads",
        )
    )
    previous = None
    for want in expected:
        got = roles.get(want.role, [])
        name = agents[want.role].name
        need = max(1, len(want.inputs))
        retried = " (more than one per input: the platform or the workflow retried some)"
        checks.append(
            Check(
                f"{name}: at least {need} thread{'s' if need > 1 else ''}",
                len(got) >= need,
                f"{len(got)} threads" + (retried if len(got) > need else ""),
            )
        )
        if previous is not None:
            prev_name, prev_threads = previous
            ends = [run.threads.get(t.id, {}).get("ended") for t in prev_threads]
            start = run.threads.get(got[0].id, {}).get("started") if got else None
            if not got or not prev_threads:
                ordered, detail = False, "one of the two never started"
            elif None in ends or start is None:
                ordered, detail = (
                    False,
                    "could not confirm: some thread status events were not seen",
                )
            else:
                gap = start - max(ends)
                ordered = gap >= 0
                detail = (
                    f"{gap:.0f} s after the last one ended"
                    if ordered
                    else f"started {-gap:.0f} s before the last one ended"
                )
            checks.append(
                Check(f"{name}: started after every {prev_name} thread had ended", ordered, detail)
            )
        if want.inputs and got:
            read = set()
            for t in got:
                for path in records.get(t.id, {}).get("reads", []):
                    read.update(p for p in want.inputs if path == p or path.startswith(p + "/"))
            unread = [p for p in want.inputs if p not in read]
            checks.append(
                Check(
                    f"{name}: every input was read by at least one of them (from their tool calls)",
                    not unread,
                    f"nothing read under {unread}" if unread else f"all {len(want.inputs)} inputs",
                )
            )
        if got:
            failed = [t.id for t in got if records.get(t.id, {}).get("errors")]
            checks.append(
                Check(
                    f"{name}: no thread recorded an error on its own stream",
                    not failed,
                    f"read these threads: {failed}" if failed else f"{len(got)} threads",
                )
            )
            previous = (name, got)
    ended = run.result or {}
    checks.append(
        Check(
            "The run's result is completed",
            ended.get("type") == "completed",
            json.dumps(ended) or "none",
        )
    )
    if report is None:
        checks.append(
            Check("The agent's report is a JSON object", False, "no JSON object in its reply")
        )
    else:
        problems = []
        for key, role in (report_counts or {}).items():
            finished = [t for t in roles.get(role, []) if t.status != "running"]
            value = report.get(key)
            if not isinstance(value, int) or value > len(finished):
                problems.append(
                    f"{key}={value!r} but {len(finished)} finished {agents[role].name} threads"
                )
        shown = {k: report.get(k) for k in (report_counts or {})}
        checks.append(
            Check(
                "The agent's report agrees with the thread list",
                not problems,
                "; ".join(problems) or json.dumps(shown),
            )
        )
    return checks


def compare_text(want, got):
    """How got relates to want: "identical" (leading and trailing whitespace aside), "spacing" (equal once every
    whitespace run is one space), "changed", or "none" when got is empty."""
    if not (got or "").strip():
        return "none"
    if got.strip() == (want or "").strip():
        return "identical"
    return "spacing" if squash(got) == squash(want) else "changed"


def diff_lines(want, got, cap=None):
    """The removed (-) and added (+) lines of a diff from want to got, without the file headers or context lines;
    with cap, at most cap of them and then a count of the rest."""
    out = list(difflib.unified_diff((want or "").splitlines(), (got or "").splitlines(), lineterm="", n=0))
    lines = [line for line in out[2:] if line[:1] in "-+"]
    if cap is not None and len(lines) > cap:
        return lines[:cap] + [f"… {len(lines) - cap} more lines"]
    return lines


def task_for_prompt(want, prompt):
    """The task text one thread should have received, given what its prompt shows: want.task with the placeholder
    replaced by the input path the prompt names (or, for a count placeholder, by the number the prompt carries
    there), and that input ("" if none applies). (None, "") when the prompt names none of want.inputs."""
    if want.inputs:
        path = next((p for p in sorted(want.inputs, key=len, reverse=True) if p in prompt), None)
        return (None, "") if path is None else (want.task.replace(want.placeholder, path), path)
    if want.placeholder and want.placeholder in want.task:
        head, tail = (re.escape(squash(part)) for part in want.task.split(want.placeholder, 1))
        m = re.fullmatch(f"{head}\\s*(\\d+)\\s*{tail}", squash(prompt))
        return want.task.replace(want.placeholder, m.group(1) if m else "N"), ""
    return want.task, ""


def measure_briefs(records, threads, agents, expected):
    """For each expected agent, by name: how many of its threads' recorded prompts are the task text the message
    sent with that thread's input filled in (identical, or equal but for spacing), which ones differ (with the
    differing lines), how many name none of the expected inputs, and how many have no recorded prompt."""
    roles, _ = threads_by_role(threads, agents)
    out = {}
    for want in expected:
        if not want.task:
            continue
        m = {"threads": 0, "identical": 0, "spacing": 0, "changed": [], "no_input_named": 0, "no_prompt": 0}
        for t in roles.get(want.role, []):
            m["threads"] += 1
            prompt = records.get(t.id, {}).get("prompt", "")
            if not prompt.strip():
                m["no_prompt"] += 1
                continue
            task, path = task_for_prompt(want, prompt)
            if task is None:
                m["no_input_named"] += 1
                continue
            verdict = compare_text(task, prompt)
            if verdict in ("identical", "spacing"):
                m[verdict] += 1
            else:
                m["changed"].append({"thread": t.id, "input": path, "diff": diff_lines(task, prompt, cap=12)})
        out[agents[want.role].name] = m
    return out


def check_prompts(records, threads, agents, expected):
    """Each run thread's recorded prompt (its first agent.thread_message_received): for each agent with inputs, a row
    saying whether every input appears in some prompt, and, when the message carried a task text for the agent, a row
    counting prompts that are identical to it, equal but for spacing, different, or missing. Every row is information
    (passed True or None), never a failure: the agent writes the workflow from your message, and the platform does not
    guarantee this event's wording."""
    # The Session threads page says of this event: "The API doesn't guarantee the prompt's text, so don't parse
    # it." Nothing that decides whether a run is usable reads it; these rows only measure.
    checks = []
    roles, _ = threads_by_role(threads, agents)
    measured = measure_briefs(records, threads, agents, expected)
    for want in expected:
        name = agents[want.role].name
        if want.inputs:
            named = {task_for_prompt(want, records.get(t.id, {}).get("prompt", ""))[1] for t in roles.get(want.role, [])}
            missing = [p for p in want.inputs if p not in named]
            checks.append(
                Check(
                    f"{name}: inputs named in the prompts",
                    True if not missing else None,
                    f"no prompt names {missing}" if missing else f"all {len(want.inputs)} inputs",
                )
            )
        m = measured.get(name)
        if m is None:  # the message carried no task text for this agent: nothing to compare its prompts with
            continue
        same = m["identical"] + m["spacing"]
        if not m["threads"]:
            detail = "no thread of this agent ran"
        else:
            detail = f"{m['identical']} of {m['threads']} identical"
            if m["spacing"]:
                detail += f"; {m['spacing']} equal but for spacing"
            if m["changed"]:
                n, ids = len(m["changed"]), ", ".join(c["thread"] for c in m["changed"])
                detail += f"; {n} {'differs: thread' if n == 1 else 'differ: threads'} {ids}"
            if m["no_input_named"]:
                n = m["no_input_named"]
                detail += f"; {n} {'names' if n == 1 else 'name'} no expected input"
            if m["no_prompt"]:
                n = m["no_prompt"]
                detail += f"; {n} {'has' if n == 1 else 'have'} no recorded prompt"
        checks.append(
            Check(
                f"{name}: prompts against the task text the message sent",
                True if m["threads"] and same == m["threads"] else None,
                detail,
            )
        )
    return checks


def check_workflow_text(code, run, agents, input_paths, wave_size):
    """Checks on the agent's copy of its workflow (what it returned when asked) against the run the platform
    recorded: the run's name and phase names appear in it, it names your agents, and, when the message set one,
    your limit on agents working at once."""
    text = code or ""
    checks = [
        Check("The agent returned a workflow in a code block", bool(text), f"{len(text):,} chars")
    ]
    names = [run.name, *run.phases.values()] if run else []
    missing = [n for n in names if n and n not in text]
    checks.append(
        Check(
            "It carries the run name and phase names the platform recorded",
            bool(names) and not missing,
            f"missing {missing}" if missing else ", ".join(repr(n) for n in names),
        )
    )
    for role, agent in agents.items():
        checks.append(
            Check(f"It names your {role} agent", agent.name in text, f"looks for {agent.name!r}")
        )
    if wave_size is not None:
        checks.append(
            Check(
                f"It mentions your limit of {wave_size} agents at once",
                re.search(rf"(?<![\d-]){wave_size}(?![\d-])", text) is not None,
                f"the number {wave_size} appears on its own"
                if re.search(rf"(?<![\d-]){wave_size}(?![\d-])", text)
                else f"the number {wave_size} does not appear on its own; read the workflow printed below to see how it limits the agents running at once",
            )
        )
    return checks


def checks_html(title, checks):
    """The checks as a small HTML table for the notebook."""
    rows = "".join(
        f"<tr><td>{'&#183;' if c.passed is None else '&#10003;' if c.passed else '&#10007;'}</td>"
        f"<td>{html.escape(c.what)}</td>"
        f"<td>{html.escape(c.detail)}</td></tr>"
        for c in checks
    )
    return (
        f"<p><b>{html.escape(title)}</b></p><table><thead><tr><th></th><th>Check</th><th>Detail</th></tr>"
        f"</thead><tbody>{rows}</tbody></table>"
    )


# --- A diagram of the run -----------------------------------------------------------------------------


def run_svg(run, width=760):
    """An SVG picture of one run as follow() recorded it: a box per phase, in order, each with the threads that
    started after it began and before the next phase began, counted by agent name, and the run's result. No
    event says which phase a thread belongs to, so threads are placed by their start times."""
    spans, open_at = [], {}
    for seconds, verb, name in run.phase_log:
        if verb == "started":
            open_at[name] = seconds
        elif name in open_at:
            spans.append((name, open_at.pop(name), seconds))
    spans += [(name, start, float("inf")) for name, start in open_at.items()]
    if not spans:
        spans = [(name, 0, float("inf")) for name in run.phases.values()] or [("(no phases)", 0, 0)]
    counts = {name: {} for name, _, _ in spans}
    ordered = sorted(spans, key=lambda s: s[1])
    for t in run.threads.values():
        # Times are whole seconds, so a phase's first threads share a timestamp with the previous phase's end:
        # place each thread in the latest phase that had begun when it started.
        begun = [name for name, start, _ in ordered if start <= t["started"]]
        name = begun[-1] if begun else ordered[0][0]
        counts[name][t["agent"]] = counts[name].get(t["agent"], 0) + 1
    box_w = min(240, (width - 40 - 30 * (len(spans) - 1)) // max(1, len(spans)))
    height = 160
    result = (run.result or {}).get("type", "not ended")
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'font-family="sans-serif" font-size="13">',
        f'<text x="20" y="22" font-weight="bold">{html.escape(run.name or run.id)}</text>',
        f'<text x="{width - 20}" y="22" text-anchor="end">result: {html.escape(str(result))}</text>',
    ]
    x = 20
    for i, (name, _, _) in enumerate(spans):
        label = ", ".join(f"{n} x {html.escape(agent)}" for agent, n in counts[name].items())
        shown = name if len(name) <= 30 else name[:29] + "…"
        parts += [
            f'<rect x="{x}" y="40" width="{box_w}" height="80" rx="8" fill="#f5f4ef" stroke="#8a8578"/>',
            f'<text x="{x + box_w / 2}" y="70" text-anchor="middle" font-weight="bold">'
            f"{html.escape(shown)}</text>",
            f'<text x="{x + box_w / 2}" y="96" text-anchor="middle" fill="#555">{label}</text>',
        ]
        if i < len(spans) - 1:
            ax = x + box_w
            parts.append(
                f'<path d="M{ax + 4} 80 L{ax + 26} 80 M{ax + 20} 74 L{ax + 26} 80 L{ax + 20} 86" '
                'stroke="#8a8578" fill="none" stroke-width="1.5"/>'
            )
        x += box_w + 30
    parts.append(
        f'<text x="20" y="{height - 16}" fill="#555">Phases and threads as the run\'s events reported '
        "them. Threads are placed in phases by start time; no event says which phase a thread is in."
        "</text></svg>"
    )
    return "".join(parts)


# --- Cleaning up ------------------------------------------------------------------------------------


def remove(label, call, *args, retry=None, **kwargs):
    """Call one clean-up function; on an API error print what failed (and, given retry, the call that does it
    later) instead of raising, so the rest of the clean-up still runs. Returns whether the call succeeded."""
    try:
        call(*args, **kwargs)
        return True
    except anthropic.APIError as exc:
        print(f"Could not {label}: {exc}." + (f" To do it later: {retry}" if retry else ""))
        return False


def clean_up(client, created, keep=()):
    """Remove what the notebook created and has not removed yet, as listed in created (the notebook's CREATED:
    environment ids, agents by role, session ids, Uploaded records, memory store ids): archive the sessions
    (waiting for one that is still running, since the platform refuses to archive it), delete the uploaded
    files, archive the agents and the environments, and delete the memory stores except those whose id is in
    keep. Whatever is removed is taken out of created, so what it still lists afterwards is the kept stores and
    anything that could not be removed, which is printed with the call that removes it later."""
    for sid in list(created["sessions"]):
        try:
            wait_for_idle_status(client, sid)
        except Exception as exc:  # archived or gone already: the archive call below then says so
            print(f"  {sid}: {exc}")
        if remove(
            f"archive session {sid}",
            client.beta.sessions.archive,
            sid,
            retry=f"client.beta.sessions.archive({sid!r})",
        ):
            created["sessions"].remove(sid)
    created["uploads"] = delete_uploads(client, created["uploads"])
    for role, agent in list(created["agents"].items()):
        if remove(
            f"archive the {role} agent ({agent.id})",
            client.beta.agents.archive,
            agent.id,
            retry=f"client.beta.agents.archive({agent.id!r})",
        ):
            del created["agents"][role]
    for env_id in list(created["environments"]):
        if remove(
            f"archive the environment ({env_id})",
            client.beta.environments.archive,
            env_id,
            retry=f"client.beta.environments.archive({env_id!r})",
        ):
            created["environments"].remove(env_id)
    for store_id in list(created["stores"]):
        if store_id in keep:
            continue
        if remove(
            f"delete memory store {store_id}",
            client.beta.memory_stores.delete,
            store_id,
            retry=f"client.beta.memory_stores.delete({store_id!r})",
        ):
            created["stores"].remove(store_id)
    left = [
        kind
        for kind, ids in created.items()
        if ids and not (kind == "stores" and set(ids) <= set(keep))
    ]
    if left:
        print(
            f"Not everything was removed ({', '.join(left)}: see above, and created.json in the records folder)."
        )
    return not left


# --- Driving a single-agent session by polling (the query sessions) --------------------------------


def wait_for_idle_status(
    client: Anthropic,
    session_id: str,
    max_wait: float = 30.0,
    max_total_wait: float = 300.0,
) -> None:
    """Poll until the session's server-side status field is `idle`.

    The `session.status_idle` event in the SSE stream can arrive
    slightly before `sessions.retrieve` reports `status == "idle"`,
    which causes an `archive()` call issued immediately after the
    stream exits to 400 with "cannot be archived while its status
    is running." This function absorbs that race with a short poll.
    Call it after breaking out of a stream/poll loop and before
    `archive()`. Raises `TimeoutError` if the session is still not
    idle after `max_total_wait` seconds.
    """
    deadline = time.monotonic() + max_wait
    while time.monotonic() < deadline:
        if client.beta.sessions.retrieve(session_id).status == "idle":
            return
        time.sleep(0.25)
    # Still not idle: the stream may have died mid-turn (a transient SSE
    # error leaves the session genuinely running). Keep polling at a gentler
    # cadence until the turn actually finishes - archiving a running session
    # is a 400, and the work it is doing is work you want kept. Bounded so
    # a stuck session doesn't hang forever.
    hard_deadline = time.monotonic() + max_total_wait
    while client.beta.sessions.retrieve(session_id).status != "idle":
        if time.monotonic() >= hard_deadline:
            raise TimeoutError(f"session {session_id} still not idle after {max_total_wait}s")
        time.sleep(5.0)


def _store_rel(path: str) -> str:
    """Store-relative path from an absolute /mnt/memory/... tool path."""
    parts = path.split("/")
    for i, seg in enumerate(parts):
        if seg == "memory" and i + 1 < len(parts):
            return "/".join(parts[i + 2 :]) or parts[-1]
    return parts[-1]


def poll_until_end_turn(
    client: Anthropic,
    session_id: str,
    poll_s: float = 5.0,
    timeout_s: float = 3600.0,
    sink: list | None = None,
    stats: dict | None = None,
    after: str | None = None,
) -> str:
    """Poll a session's events until the current turn ends, printing agent text.

    The current turn is what follows the message that started it: pass that message's event id as `after` (the
    id `events.send` returned) and the poll waits until the listing shows it (up to six polls), then reads only
    what comes after it. Without `after`, or if that id never shows, the turn is taken to follow the last
    user.message listed, which is right for a session sent one message, and for a re-sent one once it is listed.

    The query sessions run one agent for one short turn, so polling
    `events.list` is enough: every request is short and independently
    retryable, and a network blip costs one poll instead of the turn. Sessions can also be RESCHEDULED server-side
    mid-turn (you'll see session.error / session.status_rescheduled events);
    the work still completes — keep polling, which is why the default
    timeout is generous. Prints `agent.message` text and marks tool use.

    Returns the turn outcome: "end_turn" on success, or the stop reason if
    the turn ended abnormally (e.g. repeated server errors) — callers can
    re-send the message to the same session to retry the turn. Pass `sink`
    to collect the agent's message text instead of printing it — useful
    when the reply is markdown you want to render properly. Pass `stats`
    (a dict) to collect token usage and the turn's `reads_searches` count
    (every tool call that inspected the store rather than writing to it,
    reads and searches alike). When `sink` is passed too,
    `stats["answer_from"]` is the index in `sink` of the first text after
    the agent's last tool call, so `sink[answer_from:]` is the answer
    without the notes the agent wrote between tool calls. It is absent when
    the agent made no tool call. The exported transcript keeps the whole
    turn.
    """
    outcome = "end_turn"
    seen: set[str] = set()
    touched: dict[str, int] = {}
    searches = [0]
    deadline = time.time() + timeout_s
    idle = False
    anchor_misses = 0
    while time.time() < deadline and not idle:
        try:
            events = list(client.beta.sessions.events.list(session_id=session_id))
        except Exception as e:  # transient network/API blip: retry
            print(f"  [poll retry] {type(e).__name__}")
            time.sleep(poll_s)
            continue
        # Only the current turn counts: the events after the message that started it (by id when the caller passed
        # it, else the last user.message listed). An idle state listed before it belongs to an earlier turn.
        last = None
        if after is not None:
            last = next((i for i, ev in enumerate(events) if ev.id == after), None)
            if last is None and anchor_misses < 6:  # not listed yet; past six polls, fall back to the rule below
                anchor_misses += 1
                time.sleep(poll_s)
                continue
            if last is None and anchor_misses == 6:
                anchor_misses += 1  # say it once
                print("  [the sent message's id is not in the session's event list; following its last message instead]")
        if last is None:
            last = max((i for i, ev in enumerate(events) if getattr(ev, "type", "") == "user.message"), default=None)
        if last is None:  # the message just sent is not listed yet
            time.sleep(poll_s)
            continue
        for ev in events[last + 1 :]:
            if ev.id in seen:
                continue
            seen.add(ev.id)
            et = getattr(ev, "type", "")
            if et == "agent.message":
                for block in getattr(ev, "content", []) or []:
                    if getattr(block, "type", "") == "text":
                        if sink is not None:
                            sink.append(block.text)  # caller renders (e.g. as Markdown)
                        else:
                            print(textwrap.fill(block.text, width=100))
            elif et == "agent.tool_use":
                if stats is not None and sink is not None:
                    stats["answer_from"] = len(sink)  # text before a tool call is a working note, not the reply
                # semantic progress: name wiki files as they are written,
                # count everything else quietly
                name = getattr(ev, "name", "?")
                inp = getattr(ev, "input", None) or {}
                path = str(inp.get("file_path") or inp.get("path") or "")
                if name in ("write", "create", "edit", "str_replace", "insert") and path:
                    rel = _store_rel(path)
                    verb = "+" if name in ("write", "create") and rel not in touched else "~"
                    if touched.get(rel, 0) == 0 or verb == "+":
                        print(f"  {verb} {rel}")
                    touched[rel] = touched.get(rel, 0) + 1
                else:
                    searches[0] += 1
            elif et == "span.model_request_end" and stats is not None:
                mu = getattr(ev, "model_usage", None)
                if mu is not None:
                    # One entry per model request, in order: the first shows what a session pays before it
                    # has read anything (system prompt, tool definitions, the question).
                    stats.setdefault("calls", []).append(
                        {
                            "input": getattr(mu, "input_tokens", 0) or 0,
                            "cache_write": getattr(mu, "cache_creation_input_tokens", 0) or 0,
                            "cache_read": getattr(mu, "cache_read_input_tokens", 0) or 0,
                            "output": getattr(mu, "output_tokens", 0) or 0,
                        }
                    )
                    stats["input"] = stats.get("input", 0) + (getattr(mu, "input_tokens", 0) or 0)
                    stats["cache_write"] = stats.get("cache_write", 0) + (
                        getattr(mu, "cache_creation_input_tokens", 0) or 0
                    )
                    stats["cache_read"] = stats.get("cache_read", 0) + (
                        getattr(mu, "cache_read_input_tokens", 0) or 0
                    )
                    stats["output"] = stats.get("output", 0) + (
                        getattr(mu, "output_tokens", 0) or 0
                    )
                    stats["tokens_in"] = stats["input"] + stats["cache_write"] + stats["cache_read"]
                    stats["tokens_out"] = stats["output"]
            elif et == "session.status_idle":
                idle = True
                stop = getattr(ev, "stop_reason", None)
                outcome = getattr(stop, "type", "end_turn") if stop is not None else "end_turn"
        if not idle:
            time.sleep(poll_s)
    if not idle:
        raise TimeoutError(f"session {session_id} did not go idle within {timeout_s}s")
    if stats is not None:
        stats["reads_searches"] = searches[0]
    if touched or searches[0]:
        ents = sum(1 for k in touched if k.startswith("entities/"))
        shared = sorted(k for k in touched if not k.startswith("entities/"))
        bits = []
        if ents:
            bits.append(f"{ents} entity file(s)")
        if shared:
            bits.append("updated " + ", ".join(shared[:4]) + ("…" if len(shared) > 4 else ""))
        bits.append(f"{searches[0]} reads/searches")
        print("  done: " + " · ".join(bits))
    if outcome != "end_turn":
        print(f"  [turn ended: {outcome}]")
    return outcome


# --- The notebook's steps, as functions ---------------------------------------------------------------------
# Everything below is what the notebook's cells call so that each cell shows only the Managed Agents calls that
# matter: what the notebook created, normalizing documents, batching, rendering the run's message, following a
# pass and collecting its records, the checks, reading and exporting the store, asking a question, the raw-documents store and the
# economics table.


class Created(dict):
    """The ids of everything the notebook created and has not yet removed (environments, agents by role, sessions,
    uploaded files, memory stores), saved to created.json in the records folder each time something is added and
    again by finish_pass and release after they remove things, so the clean-up, or you after a dead kernel, can
    find them."""

    def __init__(self, records):
        super().__init__(environments=[], agents={}, sessions=[], uploads=[], stores=[])
        self.path = Path(records) / "created.json"

    def save(self):
        ids = {**self, "agents": {role: a.id for role, a in self["agents"].items()}}
        ids["uploads"] = [u.file_id for u in self["uploads"]]
        private_write(self.path, json.dumps(ids, indent=1))

    def add(self, kind, value, role=None):
        """Record one created thing (an id, an agent under its role, or an Uploaded) and save; returns value."""
        if role is None:
            self[kind].append(value)
        else:
            self[kind][role] = value
        self.save()
        return value


# --- Normalizing documents (Step 1) ---

NORMALIZE_SYSTEM = """You transcribe business documents into clean markdown
for a due-diligence corpus. Rules:
- Transcribe ALL substantive content faithfully; no summarizing, no commentary.
- Tables become markdown pipe-tables.
- EVERY chart or figure becomes a bracketed description that includes the
  values readable from it.
- Preserve any notes about metric definitions or bases verbatim - they matter.
- Keep document order."""


def normalize_pdf(client, path, model, system=NORMALIZE_SYSTEM, max_tokens=8000):
    """Transcribe a PDF to markdown with one Messages API call: the file goes in as a document block, so the
    model sees the rendered pages as well as the text layer (charts and scanned slides included). Raises if the
    reply was cut at max_tokens, since a shortened transcription would drop part of the document silently; split
    such a PDF or raise max_tokens."""
    import base64

    pdf_b64 = base64.standard_b64encode(Path(path).read_bytes()).decode()
    resp = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": pdf_b64,
                        },
                    },
                    {
                        "type": "text",
                        "text": "Transcribe this document to markdown per your rules.",
                    },
                ],
            }
        ],
    )
    if resp.stop_reason == "max_tokens":
        raise RuntimeError(
            f"{path}: the transcription stopped at max_tokens={max_tokens}, so it is incomplete; "
            "split the PDF into parts or call normalize_pdf with a larger max_tokens."
        )
    return "".join(b.text for b in resp.content if b.type == "text")


def normalize_docx(path):
    """A Word document's paragraphs and tables as markdown (python-docx reads the XML; nothing is rasterized)."""
    from docx import Document

    doc = Document(str(path))
    parts = []
    for para in doc.paragraphs:
        if not para.text.strip():
            continue
        prefix = "# " if para.style.name.startswith("Heading 1") else ""
        parts.append(prefix + para.text)
    for table in doc.tables:
        rows = [[cell.text.strip() for cell in row.cells] for row in table.rows]
        parts.append("| " + " | ".join(rows[0]) + " |")
        parts.append("|" + "---|" * len(rows[0]))
        for row in rows[1:]:
            parts.append("| " + " | ".join(row) + " |")
    return "\n\n".join(parts)


def normalize_any(path, client=None, model=None):
    """One entry point per document type for your own data room: extend it rather than filter. Text and
    markdown pass through; Word, Excel, PowerPoint and email are parsed; PDFs (and, through the PDF path,
    scans) go to the model, which needs client and model. Anything else raises, so nothing is skipped silently.
    The Office formats are parsed in this process by python-docx, openpyxl and python-pptx, which sit on C XML
    parsers: a counterparty's files are untrusted input, so convert them somewhere a malformed file can do no
    harm (a container or a throwaway machine), or convert them to text first with a tool you trust.
    Example: corpus = {f.stem: normalize_any(f, client, model) for f in Path("my_deal_room").iterdir()}"""
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix in (".txt", ".md"):
        return path.read_text(errors="replace")
    if suffix == ".docx":
        return normalize_docx(path)  # python-docx: paragraphs + tables
    if suffix == ".pdf":
        return normalize_pdf(client, path, model)  # native PDF blocks: text + charts
    if suffix == ".xlsx":
        import openpyxl  # pip install openpyxl

        wb = openpyxl.load_workbook(str(path), data_only=True)
        parts = []
        for ws in wb.worksheets:
            parts.append(f"## Sheet: {ws.title}")
            for row in ws.iter_rows(values_only=True):
                cells = ["" if v is None else str(v) for v in row]
                if any(c.strip() for c in cells):
                    parts.append(" | ".join(cells))
        return "\n".join(parts)
    if suffix == ".pptx":
        from pptx import Presentation  # pip install python-pptx

        prs = Presentation(str(path))
        parts = []
        for i, slide in enumerate(prs.slides, 1):
            parts.append(f"## Slide {i}")
            for shape in slide.shapes:
                if shape.has_text_frame:
                    parts.append(shape.text_frame.text)
        return "\n".join(parts)
    if suffix == ".eml":
        import email
        import email.policy

        msg = email.message_from_bytes(path.read_bytes(), policy=email.policy.default)
        hdr = "\n".join(f"{k}: {msg.get(k, '')}" for k in ("From", "To", "Date", "Subject"))
        body = msg.get_body(preferencelist=("plain", "html"))
        return hdr + "\n\n" + (body.get_content() if body else "")
    # Anything else (scans, images, exotic formats): the PDF path reads pixels.
    raise ValueError(f"unhandled document type: {path.name} - add a branch, don't skip it")


# --- Batching (Step 1) ---


def batch_documents(doc_files, batch_chars=120_000):
    """Pack documents into batches of about batch_chars characters: small files share a batch; a file larger
    than batch_chars is split into parts, each keeping the document's [SOURCE: ...] provenance header plus
    "part n of N", one part per batch. Returns a list of batches, each a list of (file name, text)."""
    batches, current, size = [], [], 0
    for f in doc_files:
        text = Path(f).read_text()
        if len(text) > batch_chars:
            first = text.split("\n", 1)[0]
            if first.startswith("[SOURCE:") and first.endswith("]"):
                header = first[:-1]
            else:
                header = f"[SOURCE: {Path(f).name}"
            body = text[len(first) :] if first.startswith("[SOURCE:") else text
            pieces = [body[i : i + batch_chars] for i in range(0, len(body), batch_chars)]
            for n, piece in enumerate(pieces, 1):
                name = f"{Path(f).stem}.part{n}.txt"
                batches.append([(name, f"{header} | part {n} of {len(pieces)}]\n\n{piece}")])
            continue
        if size + len(text) > batch_chars and current:
            batches.append(current)
            current, size = [], 0
        current.append((Path(f).name, text))
        size += len(text)
    if current:
        batches.append(current)
    return batches


def describe_batches(batches, batch_dirs):
    """Print one line per batch: its mount directory, file count, size and first file names."""
    for d, b in zip(batch_dirs, batches, strict=True):
        names = ", ".join(name for name, _ in b[:3]) + (", …" if len(b) > 3 else "")
        print(f"  {d}: {len(b)} file(s), {sum(len(t) for _, t in b) / 1000:.0f} KB — {names}")


# --- The message that describes the build run (Step 1) ---

def print_estimate(estimate, lines, budget_usd):
    """Print the estimate's lines and how the budget compares with it."""
    print("\n".join(lines))
    if estimate > budget_usd:
        print(
            f"Budget: ${budget_usd:,.0f}. Over budget: the build will not start; raise COOKBOOK_BUDGET_USD "
            "(or BUDGET_USD), or build a smaller tier."
        )
    elif budget_usd < 2 * estimate:
        print(
            f"Budget: ${budget_usd:,.0f}. OK to run, but under twice the estimate: a run that costs more than "
            "estimated would stop part-way. Consider raising it."
        )
    else:
        print(f"Budget: ${budget_usd:,.0f}. OK to run.")


# --- Running the workflow pass and collecting its records (Step 1) ---


def budget(usd_amount):
    """A session budget: whole US cents, as a string ("6000" is $60.00)."""
    return {
        "type": "limit",
        "max_list_cost": {"currency": "USD", "amount": str(round(usd_amount * 100))},
    }


def upload_batches(client, batches, batch_dirs, created, uploaded):
    """Upload every batch's files with the Files API, one mount directory per batch, appending each Uploaded
    record to uploaded (and to created) as it succeeds, so a failure part-way still leaves the earlier ones
    listed for deletion. Returns the sandbox path of each batch directory."""
    for mount_dir, batch in zip(batch_dirs, batches, strict=True):
        for name, text in batch:
            upload_file(client, name, text.encode(), f"{mount_dir}/{name}", uploaded=uploaded)
            created.add("uploads", uploaded[-1])
    return [sandbox_path(d) for d in batch_dirs]


def wiki_mount_path(client, session, store_id):
    """Where the store is mounted in this session's sandbox, as the platform reports it on the session's
    memory_store resource. Read once more if the create response didn't carry it yet."""
    for attempt in range(2):
        for r in session.resources:
            if r.type == "memory_store" and r.memory_store_id == store_id and r.mount_path:
                return r.mount_path
        if attempt == 0:
            session = client.beta.sessions.retrieve(session.id)
    raise RuntimeError("the session's resources don't give a mount path for the wiki store")


class WorkflowPass:
    """What one run cell produced, kept for the cells after it: the store it worked on, the session, what was
    uploaded, the message sent (and its task texts, when the message carries any), what follow() saw, the agent's report and its copy of
    the workflow, the thread list with each thread's own record, the session's usage and full export, the
    store's version history for the session, and what the clean-up did."""

    def __init__(self, store_id, title):
        self.store_id, self.title, self.session = store_id, title, None
        self.uploaded, self.input_paths, self.tasks = [], [], {}
        self.request = self.mem_dir = self.workflow = self.workflow_reply = ""
        self.followed = self.report = self.export = self.session_usage = self.reprint = None
        self.threads, self.records, self.versions = [], {}, []
        self.stubs_removed, self.stubs_left, self.open_runs = [], [], []
        self.usage_rows, self.list_usd = [], None

    @property
    def folder(self):
        """The name of this pass's records folder: the title in lower case with underscores."""
        return self.title.lower().replace(" ", "_")


def follow_pass(client, p, message, timeout_minutes):
    """Follow the run that message, already sent to p.session, starts; then read the agent's report, ask it to
    reprint the workflow it started, and collect the thread list, each run thread's record, the session's usage and
    export, and the store's versions from this session. Set p.mem_dir before calling; it sets p.request to message."""
    p.request = message
    print(f"Session {p.session.id}; wiki directory {p.mem_dir}; {len(p.input_paths)} inputs.")
    p.followed = follow(client, p.session.id, message, sent=True, timeout_s=(timeout_minutes + 30) * 60)
    print(f"After {p.followed.seconds / 60:.1f} minutes: {describe_stop(p.followed.stop)}.")
    if not p.followed.runs:
        print(f"The lead agent started no workflow run. Its reply: {p.followed.last_message[:1000]}")
    p.report = extract_json_object(p.followed.last_message)
    if p.report:
        print("The lead agent's report:", json.dumps(p.report))
    else:
        print("The lead agent's last reply carried no JSON report; the reply is in the records folder.")
    if p.followed.stop == "idle" and p.followed.runs:
        p.workflow, p.workflow_reply, p.reprint = ask_for_workflow(client, p.session.id)
    threads = list(client.beta.sessions.threads.list(p.session.id))
    p.threads = complete_threads(client, p.session.id, threads, p.followed)
    in_runs = [t for t in p.threads if t.workflow_run_id in p.followed.runs]
    p.records = thread_records(client, p.session.id, in_runs, p.mem_dir)
    p.session_usage = client.beta.sessions.retrieve(p.session.id).usage
    p.export = export_session(client, p.session.id, compact=False)
    p.versions = written_by_session(client, p.store_id, p.session.id)
    return p


def save_records(client, p, records):
    """Write what one pass sent and got to the records folder: the message, the agent's report and workflow
    reprint, the thread list, each run thread's own record (prompt, reads, errors), the session's full export,
    the store's version history for this session, what follow() saw, and the wiki files as they stand now."""
    out = Path(records) / p.folder
    saved = {
        "request.md": p.request,
        "report.json": json.dumps(p.report, indent=1),
        "workflow_reprint.md": p.workflow_reply,
        "threads.json": json.dumps([t.model_dump(mode="json") for t in p.threads], indent=1),
        "thread_records.json": json.dumps(p.records, indent=1),
        "session_export.json": json.dumps(p.export, indent=1) if p.export else "",
        "memory_versions.json": json.dumps(
            [v.model_dump(mode="json") for v in p.versions], indent=1
        ),
        "followed.json": json.dumps(vars(p.followed), indent=1, default=vars) if p.followed else "",
    }
    for name, text in saved.items():
        if text:
            private_write(out / name, text)
    download_store(client, p.store_id, out / "wiki")
    print(f"Records saved in {display_path(out)}")


def finish_pass(client, p, created, records, budget_usd):
    """The clean-up every pass gets, whatever happened before it: stop a run that is still open, remove the
    MOVED TO stubs the agents left where they merged files, save the records, archive the session (tried twice; a
    session that could not be archived is reported with its id, because it can keep spending until the budget),
    and delete the uploaded copies unless that session may still be reading them."""
    if p.session:
        # A run that is still open keeps writing and spending: stop it before anything else.
        try:
            p.open_runs = stop_runs(client, p.session.id, p.followed)
        except Exception as exc:  # noqa: BLE001 - keep cleaning up; assume a run may be open
            print(f"Could not check or stop the session's runs: {exc}")
            p.open_runs = ["unknown"]
        if p.open_runs:
            print(f"Runs {p.open_runs} did not report an end; archiving the session ends them.")
    try:
        p.stubs_removed, p.stubs_left = sweep_stubs(client, p.store_id)
        if p.stubs_removed:
            print(f"Removed {len(p.stubs_removed)} MOVED TO stubs.")
        if p.stubs_left:
            print(
                f"Left {len(p.stubs_left)} stubs whose target is missing: {p.stubs_left}; read them before "
                "relying on the wiki: a merge may have lost its target."
            )
    except Exception as exc:  # noqa: BLE001
        print(f"Could not sweep the MOVED TO stubs: {exc}. The store may still hold them.")
    try:
        save_records(client, p, records)
    except Exception as exc:  # noqa: BLE001
        print(f"Could not save all the records: {exc}")
    if p.session:
        sid = p.session.id
        archived = remove(
            f"archive session {sid}",
            client.beta.sessions.archive,
            sid,
            retry=f"client.beta.sessions.archive({sid!r})",
        )
        if not archived:
            # Archiving is refused while the session is working. A message sent just before this can start a turn
            # after the first stop, so stop again and retry once.
            with contextlib.suppress(Exception):
                p.open_runs = stop_runs(client, sid, p.followed)
            archived = remove(f"archive session {sid}", client.beta.sessions.archive, sid,
                              retry=f"client.beta.sessions.archive({sid!r})")
            if archived:
                print(f"Archived session {sid} on the second try.")
        if archived:
            created["sessions"].remove(sid)
        else:
            print(
                f"Session {sid} was not archived and may still be working: it can keep spending until it "
                f"reaches the ${budget_usd:,.0f} budget. Archive it by hand."
            )
    if p.session and p.session.id in created["sessions"]:
        print(
            "The uploaded files are kept while that session may still be reading them; they expire in a day."
        )
    else:
        delete_uploads(client, p.uploaded)
        created["uploads"] = [u for u in created["uploads"] if u not in p.uploaded]
    created.save()


def print_thread_usage(p, model, records=None, budget_usd=None, estimate=None):
    """Print one pass's threads grouped by agent with the platform's list cost and the token-priced cost, the
    session's own list cost (what the budget was enforced against; it includes session running time) and the
    time the pass took; keep the rows on p (p.usage_rows, p.list_usd) and, given records, write them to
    <folder>_usage.json there (the build's is build_usage.json)."""
    if not (p and p.threads):
        return
    p.usage_rows = usage_rows(p.threads, model)
    print("\n".join(usage_summary(p.usage_rows)))
    p.list_usd = list_usd(p.session_usage)
    if p.list_usd is not None:
        shown = f" (budget ${budget_usd:,.0f})" if budget_usd is not None else ""
        print(f"The session's list cost, as the platform metered it: ${p.list_usd:,.2f}{shown}")
    if estimate is not None and p.followed:
        print(
            f"The estimate was ${estimate:,.2f}; the pass took {p.followed.seconds / 60:.0f} minutes."
        )
    if records is not None:
        name = "build_usage.json" if p.folder.startswith("build") else f"{p.folder}_usage.json"
        private_write(Path(records) / name, json.dumps(p.usage_rows, indent=1, default=str))


# --- The checks on what ran (Step 1) ---


def show_checks(p, agents, expected, want_name, want_phases, report_counts, records):
    """Display the checks on one pass from the platform's records (check_run), each thread's recorded prompt
    beside the task text (check_prompts) and the run's diagram; print the number of declined tool pauses if
    any; write checks.json. agents maps roles to the created agents. Returns (the run, its threads)."""
    from IPython.display import HTML, SVG, display

    if not (p and p.followed and p.followed.runs):
        if p:
            print("No workflow run was recorded for this pass, so there is nothing to check.")
        return None, []
    # The message asks for one run. If the lead agent started more than one (a first try may end early and the
    # agent start again), check the run that completed, or else the last one that started agent threads, and say so below.
    with_threads = [r for r in p.followed.runs.values() if any(t.workflow_run_id == r.id for t in p.threads)]
    completed = [r for r in with_threads if (r.result or {}).get("type") == "completed"]
    the_run = (completed or with_threads or list(p.followed.runs.values()))[-1]
    by_role = {want.role: agents[want.role] for want in expected}
    threads = sorted(
        (t for t in p.threads if t.workflow_run_id == the_run.id), key=lambda t: t.created_at
    )
    checks = check_run(
        the_run,
        threads,
        p.records,
        by_role,
        expected,
        p.report,
        want_name,
        want_phases,
        report_counts,
    )
    if want_name is None:
        print(f"The lead agent named the run {the_run.name!r}, with phases {list(the_run.phases.values())}.")
    display(HTML(checks_html("From the platform's records", checks)))
    prompts = check_prompts(p.records, threads, by_role, expected)
    display(
        HTML(
            checks_html(
                "Each thread's recorded prompt: the inputs it names (best effort)", prompts
            )
        )
    )
    private_write(
        Path(records) / p.folder / "checks.json",
        json.dumps([vars(c) for c in checks + prompts], indent=1),
    )
    try:  # the diagram is a convenience; the record above is what matters
        display(SVG(run_svg(the_run)))
    except Exception as exc:  # noqa: BLE001
        print(f"(No run diagram: {exc})")
    if len(p.followed.runs) > 1:
        others = [
            f"{r.id} ended {(r.result or {}).get('type', 'with no result')} with {sum(1 for t in p.threads if t.workflow_run_id == r.id)} agent threads"
            for r in p.followed.runs.values()
            if r.id != the_run.id
        ]
        which = "the one that completed" if completed else "the last one that started agent threads" if with_threads else "the last one"
        print(f"The lead agent started {len(p.followed.runs)} runs ({'; '.join(others)}); the checks above read {the_run.id}, {which}.")
    if p.followed.denied:
        print(
            f"{len(p.followed.denied)} tool calls paused for approval and were declined, so they did not run; "
            "followed.json in the records folder lists them."
        )
    return the_run, threads


def show_reprint_checks(p, agents, expected, the_run, wave_size, print_script=True):
    """Print the agent's copy of its workflow (unless print_script is False) and display the checks of that text
    against the records, including that asking for it started no new run. It is the agent's account, not a record."""
    from IPython.display import HTML, display

    if not (p and p.workflow):
        if p and print_script:
            print("The agent did not return a workflow when asked; the records above are what there is.")
        return
    if print_script:
        print(p.workflow)
    roles = {want.role: agents[want.role] for want in expected}
    text_checks = check_workflow_text(p.workflow, the_run, roles, p.input_paths, wave_size)
    text_checks.append(
        Check(
            "Asking for the workflow started no new run",
            not p.reprint.runs,
            f"{len(p.reprint.runs)} runs started by the request" if p.reprint.runs else "none",
        )
    )
    display(HTML(checks_html("Checks on the lead agent's copy of its workflow", text_checks)))


# --- Reading the store and the exported files (Step 1) ---


def describe_store(client, store_id, versions, schema):
    """Print the store's memory count and size by top-level folder, whether _schema.md still equals schema,
    how many versions the build session wrote, and the part of escalations.md before its digest. Returns the
    memory list."""
    memories = list_memories(client, store_id)
    folders = {}
    for m in memories:
        top = m.path.strip("/").split("/")[0] if "/" in m.path.strip("/") else "(root)"
        folders[top] = folders.get(top, 0) + 1
    size = sum(m.content_size_bytes for m in memories)
    print(f"{len(memories)} memories, {size:,} bytes, in {store_id}: {folders}")
    schema_now = read_memory(client, store_id, "/_schema.md", memories)
    print(
        "_schema.md is",
        "unchanged" if schema_now == schema else "CHANGED: read it before trusting the wiki",
    )
    if versions is not None:
        counts = {}
        for v in versions:
            counts[v.operation] = counts.get(v.operation, 0) + 1
        capped = " (at least: the listing was capped)" if len(versions) >= VERSIONS_LISTED else ""
        print(f"{len(versions)} memory versions written by the build session{capped}: {counts}\n")
    # The ranked red-flag file: its size and its opening (front matter and any reading note), stopping before the
    # digest, which ranks the leads and names the people and entities in them. The whole file is in the records folder.
    escalations = read_memory(client, store_id, "/escalations.md", memories)
    if escalations:
        head = before_digest(escalations)
        print(f"escalations.md ({len(escalations):,} characters); its opening, before the digest:\n{head}")
    else:
        print("No escalations.md in the wiki.")
    return memories


DIGEST_START = re.compile(r"(?im)^(?:#{1,6}[^\n]*\bdigest\b|\s*(?:R\d+|\d+)[.)]\s)")
FRONT_MATTER = re.compile(r"\A---\r?\n.*?\r?\n---[ \t]*(?:\r?\n|\Z)", re.S)


def before_digest(text, cap=900):
    """The opening of escalations.md: everything before the first heading that says "digest" or the first ranked
    item ("R1." / "1." / "1)"), whichever comes first, and at most cap characters. If neither marker is found, only
    the front matter (or nothing), since the digest's layout is the organizer's and the ranked items name people."""
    m = DIGEST_START.search(text)
    if m is None:
        front = FRONT_MATTER.match(text)
        return front.group(0).rstrip()[:cap] if front else ""
    return text[: min(m.start(), cap)].rstrip()


def markdown_sections(text):
    """(name, number of non-blank lines under it) for each '## ' heading of a markdown file."""
    rows, current = [], None
    for line in text.splitlines():
        if line.startswith("## "):
            current = [line[3:].strip(), 0]
            rows.append(current)
        elif current is not None and line.strip():
            current[1] += 1
    return rows


def export_report(export_dir):
    """Check the exported wiki files as a set (wiki_lint: links that point nowhere, links written as paths,
    slugs that break the rule, aliases an unquoted comma split, an alias two nodes both claim, leftover
    stubs, files the index misses, and the largest files, which is information) and print the shape of what
    an analyst reads first: _index.md's sections with their line counts, and the largest file's size with the
    lines in each of its sections. Returns the lint findings."""
    export_dir = Path(export_dir)
    exported = {
        p.relative_to(export_dir).as_posix(): p.read_text()
        for p in export_dir.rglob("*")
        if p.is_file()
    }
    print(f"{len(exported)} wiki files in {display_path(export_dir)}")
    lint = wiki_lint(exported)
    print(lint_summary(lint))
    index_sections = markdown_sections(exported.get("_index.md", ""))
    more = ", the first 12 below" if len(index_sections) > 12 else ""
    print(f"\n_index.md: {len(index_sections)} sections{more}")
    for name, count in index_sections[:12]:
        print(f"  {name if len(name) <= 70 else name[:69] + '…'}: {count} lines")
    if lint["oversized"]:
        largest, size = lint["oversized"][0]
        counts = [str(count) for _, count in markdown_sections(exported[largest])]
        shown = ", ".join(counts[:12]) + (", …" if len(counts) > 12 else "")
        detail = f", {len(counts)} sections of {shown} lines" if counts else ""
        print(f"\n{largest}, the largest file: {size:,} bytes{detail}")
    return lint


# --- Asking a question (Step 2, and the raw-documents baseline) ---

# Why a query turn can end other than with an answer, in words.
OUTCOMES = {
    "budget_reached": "the session reached its budget: raise it and ask again before quoting this",
    "retries_exhausted": "the turn failed after retries: ask again",
    "refusal": "the model declined the question",
    "requires_action": "a tool call is waiting for confirmation, which this notebook never grants",
}


def run_question(client, session, question, model, label, show="full"):
    """Send one question to a session the notebook created, poll its events until the turn ends, and return
    the usage stats with the answer: tokens per model request, reads and searches, the session's list cost,
    the answer text (what came after the agent's last tool call) and the turn's outcome. The answer is
    displayed under the question with label saying where it came from; show="collapsed" folds it."""
    sent = client.beta.sessions.events.send(
        session_id=session.id,
        events=[{"type": "user.message", "content": [{"type": "text", "text": question}]}],
    )
    sent_id = sent.data[0].id if getattr(sent, "data", None) else None  # the question's own event id
    reply = []
    stats = {"session_id": session.id, "model": model, "question": question}
    stats["outcome"] = poll_until_end_turn(client, session.id, sink=reply, stats=stats, after=sent_id)
    if stats["outcome"] != "end_turn":  # the answer and its cost below are cut short
        print(f"  [{OUTCOMES.get(stats['outcome'], stats['outcome'])}; the cost below is a floor]")
    wait_for_idle_status(client, session.id)  # the status, and the usage with it, can lag the idle event
    stats["list_usd"] = list_usd(client.beta.sessions.retrieve(session.id).usage)
    # text after the agent's last tool call, or all of it if none came after
    stats["trimmed"] = 0 < stats.get("answer_from", 0) < len(reply)
    stats["answer"] = "\n\n".join(reply[stats.get("answer_from", 0) :]) or "\n\n".join(reply)
    show_answer(f"Q: {question}", label, stats["answer"], show, trimmed=stats["trimmed"])
    print("  " + cost_line(stats))
    return stats


def inert_markdown(text):
    """text with its Markdown formatting (headings, bullets, bold, tables) kept but its active parts defanged
    before Jupyter renders it: "&" is escaped first so no character reference written into the text survives as
    one, then "<" and "[" become entities (no HTML tag, image or link: a tag renders, an image's URL is fetched
    on display, a link's text and target would be the writer's choice), "://", "www." (in any letter case) and
    "@" are broken with entities (no bare-URL or e-mail autolink), and so are the dollar sign and the backslash
    (no math delimiter in the Markdown source); a diagram fence (mermaid) becomes a plain one, and a line that
    would draw a horizontal rule is escaped so an answer cannot imitate the notebook's own framing. show_answer
    also puts the result in a container the math renderer skips, because the browser turns the entities back
    into characters before that renderer scans the page. The text reads the same once rendered; inside a code
    span the entities show as written, a cosmetic cost of not parsing the Markdown."""
    for old, new in (("&", "&amp;"), ("\\", "&#92;"), ("<", "&lt;"), ("[", "&#91;"), ("$", "&#36;"),
                     ("://", "&#58;//"), ("@", "&#64;")):
        text = text.replace(old, new)
    text = re.sub(r"(?i)(www)\.", r"\1&#46;", text)
    text = re.sub(r"(?i)((?:" + FENCE + r"+|~{3,})[ \t]*)mermaid", r"\1text", text)  # no diagram renderer either
    return re.sub(r"(?m)^( {0,3})([-*_])(?=(?:[ \t]*\2){2,}[ \t]*$)", r"\1\\\2", text)


# Answers are shown inside this element, whose classes are the ones MathJax's default configuration skips
# (tex2jax_ignore for MathJax 2 and 3.0, mathjax_ignore from 3.1 on), so the math renderer leaves an answer alone
# even after the browser has turned the entities back into characters.
NO_MATH = '<div class="tex2jax_ignore mathjax_ignore">'


def show_answer(title, label, answer, show="full", trimmed=False):
    """Render an agent's answer as Markdown: in full under a bold title, or folded under a summary line. With
    trimmed=True a closing line says that the agent's notes before its last tool call were left out."""
    from IPython.display import Markdown, display

    answer = inert_markdown(answer)  # the answer derives from untrusted documents
    title, label = inert_markdown(title), inert_markdown(label)
    if trimmed:
        answer += (
            "\n\n_(The agent's notes before its last tool call are left out here; the saved transcript has "
            "the whole turn.)_"
        )
    # "- #1 ..." after a bullet renders as a giant heading; escape the hash
    answer = re.sub(r"(?m)^(\s*[-*]\s+)#", r"\1\\#", answer)
    if show == "collapsed":
        display(
            Markdown(
                f"{NO_MATH}\n\n<details><summary><b>{title}</b> · {label}</summary>\n\n{answer}\n\n</details>\n\n</div>"
            )
        )
    else:
        display(
            Markdown(
                f"{NO_MATH}\n\n**{title}**\n\n**{label}** *(everything until the rule below)*:\n\n{answer}\n\n---\n\n</div>"
            )
        )


def cost_line(stats):
    """Tokens in, the new tokens among them (cache writes: what each read adds once), reads and searches,
    and the cost two ways: priced from the tokens by question_usd, and the session's list cost."""
    priced = question_usd(stats)
    listed = f" · ${stats['list_usd']:.2f} list" if stats.get("list_usd") is not None else ""
    return (
        f"[{stats.get('tokens_in', 0):,} tokens in, {stats.get('cache_write', 0):,} of them new · "
        f"{stats.get('reads_searches', 0)} reads/searches · ${priced:.3f} from tokens{listed}]"
    )


# --- The comparison with the raw documents, and the economics table ---


def make_raw_store(client, doc_files, created, max_chars=85_000):
    """One raw-documents store for the no-wiki baseline: each corpus file uploaded as it is, the large ones
    chunked into .partN files of max_chars characters. Returns the store (recorded in created)."""
    store = client.beta.memory_stores.create(
        name=f"Raw documents (baseline) {datetime.now(UTC):%Y%m%d-%H%M}",
        description="The un-extracted document room, for the no-wiki cost baseline.",
    )
    created.add("stores", store.id)
    for f in doc_files:
        text = Path(f).read_text()
        if len(text) <= max_chars:
            client.beta.memory_stores.memories.create(
                store.id, path=f"/{Path(f).stem}.txt", content=text
            )
        else:
            for i in range(0, len(text), max_chars):
                part = f"/{Path(f).stem}.part{i // max_chars + 1}.txt"
                client.beta.memory_stores.memories.create(
                    store.id, path=part, content=text[i : i + max_chars]
                )
    return store


def economics(
    client,
    *,
    build,
    battery,
    agents,
    query_model,
    build_model,
    consolidate_model,
    records,
    lead_model=None,
    baseline_model=None,
):
    """Price this run from the platform's list costs, display the per-question and summary tables with the
    break-even line and the break-even chart, and write economics.json to records. build is the WorkflowPass; battery maps a
    label to {"wiki": stats, "raw": stats} from run_question. The model arguments name each role in the tables, and
    query_model and build_model also price any question or thread that records no model; baseline_model defaults
    to query_model, lead_model to build_model. Returns the summary dict."""
    from IPython.display import SVG, Markdown, display

    lead_model = lead_model or build_model
    baseline_model = baseline_model or query_model

    def token_usd(stats):
        return question_usd(stats, query_model)

    def listed_usd(stats):
        return stats["list_usd"] if stats.get("list_usd") is not None else token_usd(stats)

    if not build.usage_rows:  # print_thread_usage was not run on the build: price its threads here
        build.usage_rows, build.list_usd = usage_rows(build.threads, build_model), list_usd(build.session_usage)
    # each thread's list cost, grouped by the agent it ran
    by_agent = usage_by_agent(build.usage_rows)
    extract_usd = by_agent.get(agents["extractor"].name, 0.0)
    resolve_usd = by_agent.get(agents["resolver"].name, 0.0)
    consolidate_usd = by_agent.get(agents["analyzer"].name, 0.0) + by_agent.get(
        agents["organizer"].name, 0.0
    )
    build_usd = build.list_usd if build.list_usd is not None else sum(by_agent.values())
    rest_usd = build_usd - extract_usd - resolve_usd - consolidate_usd  # the lead agent's thread + running time

    # Question by question: the wiki answer beside the raw-documents answer to the same question.
    rows, totals = [], {"wiki": [0.0, 0.0], "raw": [0.0, 0.0]}
    for label, pair in battery.items():
        cells = []
        for side in ("wiki", "raw"):
            s = pair[side]
            t_usd, l_usd = token_usd(s), listed_usd(s)
            totals[side][0] += t_usd
            totals[side][1] += l_usd
            reads = read_sizes(export_session(client, s["session_id"])["threads"][0]["events"])
            biggest = max(reads.items(), key=lambda kv: kv[1], default=("-", 0))
            # The label is a file path or the agent's own grep pattern, shown as code so dollars, stars and underscores
            # stay literal; a pipe would still split the table row (a backslash escape is not enough when the pattern
            # already has a backslash before the pipe), so it is shown as the look-alike │.
            largest = "`" + biggest[0].replace("|", "│").replace("`", "'").replace("\n", " ").replace("\r", " ") + "`"
            cells.append(
                f"{s.get('tokens_in', 0):,} / {s.get('cache_write', 0):,} / {s.get('reads_searches', 0)} / "
                f"\\${t_usd:.3f} / \\${l_usd:.2f} / {largest} ({biggest[1]:,} chars)"
            )
        rows.append(f"| {label} | {cells[0]} | {cells[1]} |")
    n = max(1, len(battery))  # no questions asked means nothing to compare; the table is then empty
    wiki_mean, raw_mean = totals["wiki"][0] / n, totals["raw"][0] / n
    saving = raw_mean - wiki_mean  # mean saving per question at token prices
    savings = [
        token_usd(p["raw"]) - token_usd(p["wiki"]) for p in battery.values()
    ]  # per question; negative = wiki dearer
    cheaper = sum(s > 0 for s in savings)
    if abs(saving) < 0.1 * max(
        raw_mean, 1e-9
    ):  # within a tenth of the raw mean: six asks cannot tell that from zero
        breakeven = (
            "no break-even to compute: on these questions the wiki answers cost about the same"
        )
    elif saving > 0:
        lo, hi = min(savings), max(savings)
        breakeven = (
            f"about {build_usd / saving:,.0f} questions at these {n} questions' mean saving; the wiki was "
            f"cheaper on {cheaper} of {n}, and per question the difference ran from "
            f"{'a loss of ' if lo < 0 else ''}\\${abs(lo):.3f} to {'a loss of ' if hi < 0 else ''}\\${abs(hi):.3f}"
        )
    else:
        breakeven = f"never, on these questions: the wiki answers cost more on average (cheaper on {cheaper} of {n})"

    summary = {
        "build_usd": build_usd,
        "extract_usd": extract_usd,
        "resolve_usd": resolve_usd,
        "consolidate_usd": consolidate_usd,
        "workflow_and_runtime_usd": rest_usd,
        "per_question": battery,
        "wiki_mean_token_usd": wiki_mean,
        "raw_mean_token_usd": raw_mean,
        "wiki_mean_list_usd": totals["wiki"][1] / n,
        "raw_mean_list_usd": totals["raw"][1] / n,
        "breakeven": breakeven,
    }
    private_write(Path(records) / "economics.json", json.dumps(summary, indent=1, default=str))
    header = "tokens in / new tokens / reads / token price / list cost / largest read"
    display(
        Markdown(
            "\n".join(
                [
                    f"| question | with the wiki: {header} | raw documents: {header} |",
                    "|---|---|---|",
                    *rows,
                    f"| **mean of {n}, token price (list cost)** | **\\${wiki_mean:.3f}** "
                    f"(\\${totals['wiki'][1] / n:.3f}) | **\\${raw_mean:.3f}** (\\${totals['raw'][1] / n:.3f}) |",
                ]
            )
        )
    )
    roles = {
        "wiki questions": query_model,
        "raw-document questions": baseline_model,
        "extractors, resolver": build_model,
        "analyzers, organizer": consolidate_model,
        "lead agent": lead_model,
    }
    by_model = {}
    for role, model in roles.items():
        by_model.setdefault(model, []).append(role)
    if len(by_model) == 1:
        models_line = "All sessions ran on `" + query_model + "`."
    else:
        models_line = ". ".join("`" + model + "`: " + ", ".join(parts) for model, parts in by_model.items()) + "."
    wiki_label = raw_label = ""
    if baseline_model != query_model:  # name the model on each side when they differ
        wiki_label, raw_label = f" (`{query_model}`)", f" (`{baseline_model}`)"
    display(
        Markdown(
            rf"""
| what | cost (this run, as the platform metered it) |
|---|---|
| build the wiki (extraction \${extract_usd:.2f} + resolver \${resolve_usd:.2f} + consolidation \${consolidate_usd:.2f} + writing the workflow and session time \${rest_usd:.2f}) | **\${build_usd:.2f}** one-time |
| a question with the wiki{wiki_label}, mean of the {n} above, from tokens at list prices | **\${wiki_mean:.3f}** |
| the same {n} questions against the raw documents{raw_label}, mean, from tokens at list prices | **\${raw_mean:.3f}** |
| on cost alone, the build breaks even after | **{breakeven}** |

*{models_line} Thinking was at the platform's default setting. When the break-even line gives a number of questions, it is the build's list cost divided by the questions' mean saving at token prices, since whole-cent list costs are too coarse for answers that cost a few cents. "New tokens" are the session's cache writes: the prompt and tools on the first request, then whatever each read or search returned; with the output they carry most of the price, and every later request reads them again at the cached rate. List costs are whole cents per session; per-thread list costs in the build row are rounded separately and leave out session running time, so the last part of that row is the session's total minus the others. Six questions are a sample, not a benchmark: the collapsed answers above, and the full transcripts in the records, say whether the cheaper answer was also the right one.*"""
        )
    )
    # The break-even chart, from the same three figures: the build's list cost and the two mean prices per answer.
    display(SVG(breakeven_chart(build_usd, wiki_mean, raw_mean)))
    return summary


def breakeven_chart(build_usd, wiki_usd_per_answer, raw_usd_per_answer, *, max_questions=None):
    """The "What it costs" chart, as an SVG string for IPython.display.SVG: total cost by questions asked, the raw
    documents from zero against the wiki from its one-time build cost, with the break-even (build_usd divided by the
    saving per answer) marked where the lines cross. max_questions sets the x-range; None sizes it to the crossing."""
    accent, quiet, ink, sub, faint, grid = "#C6613F", "#9C9A92", "#262624", "#5E5D59", "#87867F", "#E8E6DC"
    saving = raw_usd_per_answer - wiki_usd_per_answer
    about_same = abs(saving) < 0.1 * max(raw_usd_per_answer, 1e-9)  # the band economics() calls "about the same"
    crossing = build_usd / saving if saving > 0 and not about_same else None  # questions at which the totals are equal

    def tidy_step(span, most):  # the smallest 1-2-5 step that divides span into at most "most" intervals
        step = 10.0 ** -4
        while True:
            for m in (1, 2, 5):
                if span / (m * step) <= most:
                    return m * step
            step *= 10

    if max_questions is None:  # about twice the crossing, rounded up to a tidy number; 600 when there is no crossing
        want = 2.2 * crossing if crossing else 600  # no crossing, or one at zero: 600
        unit = tidy_step(want, 12)
        max_questions = max(10, int(-(-want // unit) * unit))
    x_max = max_questions
    y_max = 1.06 * max(raw_usd_per_answer * x_max, build_usd + wiki_usd_per_answer * x_max, 0.01)
    y_tick, x_tick = tidy_step(y_max / 1.06, 5.5), tidy_step(x_max, 7)

    def cents(usd):  # a per-answer price as the text says it: 7¢, 0.4¢, 0.05¢
        c = usd * 100
        return f"{c:.0f}¢" if c >= 0.95 else f"{c:.1f}¢" if c >= 0.095 else f"{c:.2f}¢"

    def money(usd):  # axis dollars: whole dollars, or cents when the ticks are below a dollar
        return f"${usd:,.0f}" if y_tick >= 1 else f"${usd:,.2f}"

    W, H, L, R, T, B = 900, 500, 70, 30, 92, 78  # canvas, then the plot's left, right, top and bottom margins, in px
    pw, ph = W - L - R, H - T - B

    def X(q):
        return L + pw * q / x_max

    def Y(usd):
        return T + ph * (1 - usd / y_max)

    def el(tag, body=None, **attrs):  # one SVG element; attribute names use _ for -
        a = "".join(f' {k.rstrip("_").replace("_", "-")}="{v}"' for k, v in attrs.items())
        return f"<{tag}{a}/>" if body is None else f"<{tag}{a}>{html.escape(str(body), quote=False)}</{tag}>"

    title, lead = "When the wiki pays for its build", "Total cost by number of questions asked: "
    if crossing is not None and crossing <= x_max:
        subtitle = lead + f"break-even at about {crossing:,.0f}"
    elif crossing is not None:
        subtitle = lead + f"no break-even within {x_max:,} questions"
    elif about_same:
        subtitle = lead + "here the answers cost about the same, so there is no break-even"
    else:
        subtitle = lead + "here the wiki's answers cost more, so the lines do not cross"
    caption = (f"This run: the build cost ${build_usd:,.2f} once; an answer then cost ${wiki_usd_per_answer:.4f} from "
               f"the wiki and ${raw_usd_per_answer:.4f} from the raw documents (means, token prices).")
    font = "Inter, -apple-system, 'Segoe UI', Helvetica, Arial, sans-serif"
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" '
           f'font-family="{font}">', el("title", title), el("desc", f"{subtitle}. {caption}"),
           el("rect", width=W, height=H, fill="white"),
           el("text", title, x=L - 46, y=30, font_size=21, font_weight=700, fill=ink),
           el("text", subtitle, x=L - 46, y=56, font_size=15, fill=ink)]
    k = 0
    while k * y_tick <= y_max:  # light dollar gridlines, labelled at the left; the zero line a little darker
        y = round(Y(k * y_tick), 1)
        out.append(el("line", x1=L, x2=L + pw, y1=y, y2=y, stroke=grid if k else faint, stroke_width=1 if k else 1.2))
        out.append(el("text", money(k * y_tick), x=L - 8, y=y + 4, font_size=12.5, fill=faint, text_anchor="end"))
        k += 1
    k = 0
    while k * x_tick <= x_max:  # x ticks
        out.append(el("text", f"{k * x_tick:,.0f}", x=round(X(k * x_tick), 1), y=T + ph + 20, font_size=12.5,
                      fill=faint, text_anchor="middle"))
        k += 1
    out.append(el("text", "Questions asked", x=L + pw / 2, y=T + ph + 42, font_size=13, fill=sub, text_anchor="middle"))
    if crossing is not None and crossing <= x_max:  # the crossing: a dashed line named at its top, and a dot
        xc = round(X(crossing), 1)
        out.append(el("line", x1=xc, x2=xc, y1=T, y2=T + ph, stroke=ink, stroke_width=1.2, stroke_dasharray="5 4"))
        out.append(el("text", f"about {crossing:,.0f} questions", x=xc + 8, y=T + 16, font_size=14, fill=ink))
        out.append(el("circle", cx=xc, cy=round(Y(raw_usd_per_answer * crossing), 1), r=4, fill=ink))
    raw_end, wiki_end = raw_usd_per_answer * x_max, build_usd + wiki_usd_per_answer * x_max
    for y0, y1, colour in ((0, raw_end, quiet), (build_usd, wiki_end, accent)):  # the two cost lines
        out.append(el("line", x1=X(0), y1=round(Y(y0), 1), x2=X(x_max), y2=round(Y(y1), 1), stroke=colour,
                      stroke_width=3, stroke_linecap="round"))
    # each line named above its right end, in its own colour; when the ends are close, the lower line's name goes below
    y_raw, y_wiki = Y(raw_end) - 12, Y(wiki_end) - 12
    if abs(y_raw - y_wiki) < 22:
        y_raw, y_wiki = (y_raw, y_wiki + 36) if y_wiki >= y_raw else (y_raw + 36, y_wiki)
    out.append(el("text", f"Raw documents: {cents(raw_usd_per_answer)} each", x=X(x_max) - 6, y=round(y_raw, 1),
                  font_size=14, fill=sub, text_anchor="end"))
    out.append(el("text", f"Wiki: ${build_usd:,.0f} build, then {cents(wiki_usd_per_answer)} each", x=X(x_max) - 6,
                  y=round(y_wiki, 1), font_size=14, font_weight=700, fill=accent, text_anchor="end"))
    out.append(el("text", caption, x=L - 46, y=H - 14, font_size=12, fill=faint))
    return "\n".join(out) + "\n</svg>"


def save_settings(records, **settings):
    """Write settings.json in the records folder: the models, agents, environment, store, budget and limits the
    run used, as passed (agents and the environment as their API objects)."""
    out = dict(settings)
    if "agents" in out:
        out["agents"] = {role: a.model_dump(mode="json") for role, a in out["agents"].items()}
    if "environment" in out:
        out["environment"] = out["environment"].model_dump(mode="json")
    private_write(Path(records) / "settings.json", json.dumps(out, indent=1, default=str))


def add_example_documents(docs):
    """The worked example's two synthetic companions, added to the corpus folder: the Word analyst note with a
    [SOURCE: ...] line (python-docx reads it; the markdown copy stands in if the .docx is missing), and the
    vendor CSV as it is. Both are marked synthetic in their own text."""
    docs = Path(docs)
    note = Path("example_data/analyst_note.docx")  # written by make_analyst_docx.py
    note_md = normalize_docx(note) if note.exists() else Path("example_data/analyst_note_synthetic.md").read_text()
    header = "[SOURCE: synthetic demo document (marked) | analyst flash note | as-of: 2024-05-14]"
    (docs / "analyst_note.txt").write_text(header + "\n\n" + note_md)
    csv = Path("example_data/data_provider_extract.csv")
    (docs / "data_provider_extract.csv.txt").write_text(csv.read_text())


def check_build(p, agents, batches, records, run_name=None, phases=None, wave_size=None):
    """The checks for the build pass: what ran, from the platform's records (show_checks), which documents no
    extractor reported filing, and the agent's reprint of its workflow against the records (its table is shown;
    print p.workflow to read the script itself). Returns the run."""
    expected = [
        Expected("extractor", p.input_paths, p.tasks.get("extractor", ""), "BATCH_DIR"),
        Expected("resolver", [], p.tasks.get("resolver", "")),
        Expected("analyzer", p.input_paths, p.tasks.get("analyzer", ""), "INPUT_PATH"),
        Expected("organizer"),
    ]
    counts = {"batches_extracted": "extractor", "batches_analyzed": "analyzer"}
    the_run, _ = show_checks(p, agents, expected, run_name, phases, counts, records)
    if the_run:
        filed = set((p.report or {}).get("documents_filed") or [])
        missing = [n for b in batches for n, _ in b if n not in filed and Path(n).stem not in filed]
        print("Documents no extractor reported filing:", missing or "none")
        show_reprint_checks(p, agents, expected, the_run, wave_size, print_script=False)
    return the_run


def release(client, created, records, wikis, keep_wikis=True):
    """The notebook's last step: archive or delete everything still listed in created (clean_up), keeping the
    stores in wikis ({store id: what it is}) unless keep_wikis is False, save created.json, and print what was
    kept (with the call that deletes it later) or deleted, and where the records are."""
    clean_up(client, created, keep=wikis if keep_wikis else {})
    created.save()
    for sid, what in wikis.items():
        if sid not in created["stores"]:
            print(f"Deleted {what} ({sid}).")
        elif keep_wikis:
            print(f"Kept {what}: {sid}. To delete it later: client.beta.memory_stores.delete({sid!r})")
    print(f"Records in {display_path(records)}")

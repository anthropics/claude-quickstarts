"""make keys: the demo signs and grows a copy of policy/ in state/demo, never policy/ itself."""

from __future__ import annotations

import filecmp
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

from conftest import ROOT


def _agentpolicy_bin(tmp: Path) -> Path:
    exe = tmp / "bin" / "agentpolicy"
    exe.parent.mkdir()
    exe.write_text(f"#!/bin/sh\nPYTHONPATH={ROOT / 'src'} exec {sys.executable} -m agentpolicy.cli \"$@\"\n")
    exe.chmod(exe.stat().st_mode | stat.S_IXUSR)
    return exe


def _repo(tmp: Path) -> Path:
    repo = tmp / "repo"
    shutil.copytree(ROOT / "policy", repo / "policy", ignore=shutil.ignore_patterns("*.sig"))
    shutil.copy(ROOT / "agentpolicy.yaml", repo / "agentpolicy.yaml")
    (repo / "scripts").mkdir()
    shutil.copy(ROOT / "scripts" / "demo-keys.sh", repo / "scripts" / "demo-keys.sh")
    return repo


def _run(repo: Path, exe: Path, *args: str, **env: str) -> subprocess.CompletedProcess:
    full = {"PATH": "/usr/bin:/bin", "AGENTPOLICY": str(exe), **env}
    return subprocess.run([*args], capture_output=True, text=True, env=full, cwd=repo)


def test_demo_keys_leave_the_tracked_policy_tree_untouched(tmp_path):
    exe, repo = _agentpolicy_bin(tmp_path), _repo(tmp_path)
    before = tmp_path / "before"
    shutil.copytree(repo / "policy", before)

    r = _run(repo, exe, "bash", "scripts/demo-keys.sh")
    assert r.returncode == 0, r.stderr
    cmp = filecmp.dircmp(before, repo / "policy")
    assert not (cmp.diff_files or cmp.left_only or cmp.right_only)
    assert not list((repo / "policy").rglob("*.sig"))

    demo = repo / "state" / "demo"
    assert (demo / "policy" / "profiles" / "hello" / "ceiling.yaml.sig").exists()
    v = _run(repo, exe, str(exe), "ceiling", "verify", "--profile", "hello",
             AGENTPOLICY_CONFIG=str(demo / "agentpolicy.yaml"))
    assert v.returncode == 0 and "signed by policy-owner@example.com" in v.stdout, v.stderr

    # A second run keeps the trusted key once and the grants the demo grew.
    grown = demo / "policy" / "profiles" / "hello" / "policy.yaml"
    grown.write_text(grown.read_text() + "# grown\n")
    r = _run(repo, exe, "bash", "scripts/demo-keys.sh")
    assert r.returncode == 0, r.stderr
    assert (demo / "policy" / "signers.yaml").read_text().count("public_key:") == 1
    assert grown.read_text().endswith("# grown\n")


def test_pubkey_prints_the_entry_keygen_printed(tmp_path):
    exe = _agentpolicy_bin(tmp_path)
    key = tmp_path / "k.key"
    made = _run(tmp_path, exe, str(exe), "ceiling", "keygen", "--key", str(key), "--identity", "a@b")
    again = _run(tmp_path, exe, str(exe), "ceiling", "pubkey", "--key", str(key), "--identity", "a@b")
    assert made.returncode == 0 and again.returncode == 0, made.stderr + again.stderr
    assert made.stdout.splitlines()[-2:] == again.stdout.splitlines()
    assert os.path.getsize(key) > 0

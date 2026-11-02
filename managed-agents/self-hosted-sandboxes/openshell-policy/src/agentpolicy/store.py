"""Where policy lives: the base, each profile's signed ceiling and grants, and the ledger.

    policy/base.yaml                       every sandbox's floor (template)
    policy/profiles/<p>/ceiling.yaml       the most a profile may hold (person-owned, signed)
    policy/profiles/<p>/ceiling.yaml.sig   signature over base.yaml + ceiling.yaml
    policy/signers.yaml                    the public keys trusted to sign ceilings
    policy/profiles/<p>/policy.yaml        the profile's starting grants (agentpolicy-owned)
    state/ledger.jsonl                     every decision, grant, promotion and shrink
    state/environments.yaml                which profile each Managed Agents environment runs under (operator-owned)
"""

from __future__ import annotations

import datetime as dt
import fcntl
import hashlib
import json
import os
import stat
import re
import tempfile
from pathlib import Path
from typing import Any, Iterator

import yaml

from . import policyfile, signing
from .config import Settings
from .policyfile import ENVIRONMENT_RE, Bindings, PolicyError

SIGNATURE_NAMESPACE = "agentpolicy-ceiling"
PROFILE_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")

ENVIRONMENTS_HEADER = """\
# Which policy profile each Managed Agents environment's sessions run under. The
# dispatcher reads this for every session it serves; nothing a session or an
# agent carries can choose a profile. The operator owns this file: write it
# with `agentpolicy environment set`, and keep it writable by its owner only.
"""

REVOKED_HEADER = """\
# Destinations taken away from this profile, one host:port a line. Promote
# skips a grant that reaches one, and a proposal that reaches one waits for a
# person. Shrink adds what it removes. Delete a line to give one back.
"""

GRANTS_HEADER = """\
# The starting grants for the "{profile}" profile: network rules every new
# session of this profile gets on top of policy/base.yaml.
#
# agentpolicy writes this file. `agentpolicy promote` adds grants the reviewer
# approved and the agent then used; `agentpolicy shrink` removes grants the
# agent stopped using. Each write is proved to stay inside ceiling.yaml, and
# each shrink is also proved to grant nothing the previous version did not.
# The history of every change is in state/ledger.jsonl.
"""


class CeilingError(PolicyError):
    """A ceiling is missing, unsigned, or changed since it was signed."""


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def check_profile(profile: str) -> str:
    if not PROFILE_RE.match(profile):
        raise PolicyError(f"invalid profile name {profile!r}: use lowercase letters, digits and dashes")
    return profile


def check_environment(environment_id: str) -> str:
    if not ENVIRONMENT_RE.match(environment_id):
        raise PolicyError(f"invalid environment id {environment_id!r}")
    return environment_id


class Store:
    def __init__(self, settings: Settings) -> None:
        self.s = settings

    # ---- profiles -------------------------------------------------------

    def profiles(self) -> list[str]:
        root = self.s.policy_dir / "profiles"
        if not root.is_dir():
            return []
        return sorted(p.name for p in root.iterdir() if (p / "ceiling.yaml").exists())

    def _paths(self, profile: str) -> tuple[Path, Path, Path]:
        d = self.s.profile_dir(check_profile(profile))
        return d / "ceiling.yaml", d / "ceiling.yaml.sig", d / "policy.yaml"

    def base(self, bindings: Bindings) -> dict[str, Any]:
        return policyfile.load_template(self.s.base_path, bindings)

    def grants(self, profile: str, bindings: Bindings) -> dict[str, Any]:
        _, _, grants_path = self._paths(profile)
        if not grants_path.exists():
            return {"network_policies": {}}
        return policyfile.load_template(grants_path, bindings)

    def grants_template(self, profile: str) -> dict[str, Any]:
        """The grants file as stored, placeholders and all."""
        _, _, grants_path = self._paths(profile)
        if not grants_path.exists():
            return {"network_policies": {}}
        return policyfile.parse(grants_path.read_text(), str(grants_path))

    def starting_policy(self, profile: str, bindings: Bindings) -> dict[str, Any]:
        """The policy a new sandbox for this profile is created with."""
        return policyfile.compose(self.base(bindings), self.grants(profile, bindings))

    def ceiling(self, profile: str, bindings: Bindings, verify: bool | None = None) -> dict[str, Any]:
        """The full boundary: base plus the profile's ceiling rules."""
        ceiling_path, _, _ = self._paths(profile)
        if not ceiling_path.exists():
            raise CeilingError(f"profile {profile!r} has no ceiling at {ceiling_path}")
        if verify if verify is not None else self.s.require_signed_ceiling:
            self.verify_ceiling(profile)
        envelope = policyfile.load_template(ceiling_path, bindings)
        return policyfile.compose(self.base(bindings), envelope)

    def write_grants(self, profile: str, grants: dict[str, Any]) -> None:
        """Replaces a profile's grants file atomically."""
        _, _, grants_path = self._paths(profile)
        _atomic_write(grants_path, self.grants_text(profile, grants))

    def grants_text(self, profile: str, grants: dict[str, Any]) -> str:
        """A grants file's text. It is a template; quote nothing the renderer must still see."""
        body = {"network_policies": grants.get("network_policies") or {}}
        return GRANTS_HEADER.format(profile=profile) + policyfile.dump(body)

    # ---- revoked destinations ----------------------------------------------

    def revoked(self, profile: str) -> frozenset[str]:
        """The host:port destinations taken away from the profile (revoked.txt).

        The ledger keeps every grant ever approved, so without this list the
        next promote would bring back whatever shrink or a person removed.
        """
        path = self.s.profile_dir(profile) / "revoked.txt"
        lines = path.read_text().splitlines() if path.exists() else []
        found = frozenset(line.split("#")[0].strip().lower() for line in lines) - {""}
        for d in found:
            if not re.fullmatch(r"\S+:\d+", d):  # a line that can match nothing would revoke nothing, silently
                raise PolicyError(f"{path}: {d!r} is not a host:port")
        return found

    def revoked_text(self, profile: str, add: list[str]) -> str:
        """revoked.txt with more destinations at its end."""
        path = self.s.profile_dir(profile) / "revoked.txt"
        old = path.read_text() if path.exists() else REVOKED_HEADER
        return old + ("" if old.endswith("\n") else "\n") + "".join(f"{d}\n" for d in add)

    def write_revoked(self, profile: str, add: list[str]) -> None:
        _atomic_write(self.s.profile_dir(profile) / "revoked.txt", self.revoked_text(profile, add))

    # ---- environments ------------------------------------------------------

    def environments(self) -> dict[str, str]:
        """The operator's environment-to-profile map: the settings', then the file's."""
        path = self.s.environments_path
        mapped: dict[str, str] = {}
        if path.exists():
            if path.stat().st_mode & (stat.S_IWGRP | stat.S_IWOTH):
                raise PolicyError(f"{path} is writable by its group or by others; refusing to read profiles from it")
            data = yaml.safe_load(path.read_text()) or {}
            mapped.update({str(k): str(v) for k, v in (data.get("environments") or {}).items()})
        mapped.update(self.s.environments)
        return mapped

    def profile_for_environment(self, environment_id: str) -> str:
        """The profile a session from this environment runs under, or PolicyError."""
        profile = self.environments().get(check_environment(environment_id))
        if not profile:
            raise PolicyError(
                f"environment {environment_id} is not mapped to a profile; "
                f"the operator maps it with `agentpolicy environment set {environment_id} <profile>`"
            )
        return check_profile(profile)

    def set_environment(self, environment_id: str, profile: str) -> None:
        check_environment(environment_id)
        if profile not in self.profiles():
            raise PolicyError(f"no profile {profile!r} under {self.s.policy_dir / 'profiles'}")
        if environment_id in self.s.environments:
            raise PolicyError(f"{environment_id} is mapped in the settings file, which wins; change it there")
        path = self.s.environments_path
        if path.exists() and path.stat().st_mode & (stat.S_IWGRP | stat.S_IWOTH):
            raise PolicyError(f"{path} is writable by its group or by others; check its entries, fix its mode, then retry")
        data = yaml.safe_load(path.read_text()) if path.exists() else None
        mapped = dict((data or {}).get("environments") or {})
        mapped[environment_id] = profile
        _atomic_write(path, ENVIRONMENTS_HEADER + yaml.safe_dump({"environments": mapped}, sort_keys=True))
        path.chmod(0o644)

    # ---- ceiling signatures ----------------------------------------------

    def signing_payload(self, profile: str) -> bytes:
        """What a ceiling signature covers.

        - The base and the ceiling, by digest. Signing the base too means a
          change to base.yaml invalidates every profile's signature, so no one
          can widen every sandbox by editing the one file the ceilings are
          composed on.
        - The API address rendered into both. Proofs render the same
          address on each side, so they cannot catch a changed address; the
          signature does.
        """
        ceiling_path, _, _ = self._paths(profile)
        base_sum = hashlib.sha256(self.s.base_path.read_bytes()).hexdigest()
        ceiling_sum = hashlib.sha256(ceiling_path.read_bytes()).hexdigest()
        return (
            f"{SIGNATURE_NAMESPACE}-v2\nprofile {profile}\nbase {base_sum}\nceiling {ceiling_sum}\n"
            f"api {self.s.sandbox_base_url}\n"
        ).encode()

    def sign_ceiling(self, profile: str, key_path: Path, identity: str) -> Path:
        _, sig_path, _ = self._paths(profile)
        key = signing.load_private_key(key_path)
        sig = {
            "identity": identity,
            "public_key": signing.public_key_text(key),
            "signature": signing.sign(key, self.signing_payload(profile)),
        }
        sig_path.write_text(json.dumps(sig, indent=2) + "\n")
        return sig_path

    def verify_ceiling(self, profile: str) -> str:
        """Returns the identity that signed the ceiling, or raises CeilingError."""
        _, sig_path, _ = self._paths(profile)
        if not sig_path.exists():
            raise CeilingError(f"profile {profile!r}: ceiling is not signed ({sig_path} missing)")
        self._check_signers_file()
        signers = signing.load_signers(self.s.signers_file)
        try:
            sig = json.loads(sig_path.read_text())
            identity = sig["identity"]
            public = sig["public_key"]
            value = sig["signature"]
        except (ValueError, KeyError) as err:
            raise CeilingError(f"profile {profile!r}: malformed signature file") from err
        if signers.get(identity) != public:
            raise CeilingError(f"profile {profile!r}: signed by {identity!r}, who is not a trusted signer")
        if not signing.verify(public, self.signing_payload(profile), value):
            raise CeilingError(
                f"profile {profile!r}: ceiling, base or API address changed since {identity!r} signed it"
            )
        return identity

    def _check_signers_file(self) -> None:
        """Refuses a trust root that the wrong people could have edited.

        The signers file decides who may widen a ceiling. If the account that
        runs grow, promote and shrink could edit it, that account could trust
        its own key. With ``protect_signers`` on, this
        account must be unable to change the file or put another in its place:
        it may own or write neither the file nor any directory above it, which
        is how sshd checks authorized_keys. Root can write anything, so it fails.
        """
        path = self.s.signers_file
        if path is None or not path.exists():
            raise CeilingError(f"no signers file at {path}")
        if path.stat().st_mode & (stat.S_IWGRP | stat.S_IWOTH):
            raise CeilingError(f"{path} is writable by its group or by others; trust no signer it lists")
        for p in (path, *path.parents) if self.s.protect_signers else ():
            if p.stat().st_uid == os.geteuid() or os.access(p, os.W_OK):
                raise CeilingError(f"this account owns or can write {p}, so it could change {path}; "
                                   "with protect_signers on it must not be able to")

    # ---- ledger -----------------------------------------------------------

    def record(self, kind: str, **fields: Any) -> dict[str, Any]:
        """Appends one entry. Writers on the same host take turns on a lock."""
        entry = {"ts": now(), "kind": kind, **fields}
        self.s.state_dir.mkdir(parents=True, exist_ok=True)
        line = (json.dumps(entry, sort_keys=True) + "\n").encode()
        fd = os.open(self.s.ledger_path, os.O_RDWR | os.O_APPEND | os.O_CREAT, 0o640)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            size = os.fstat(fd).st_size
            # A writer killed mid-line leaves no newline; end its line first so
            # this entry stays on a line of its own.
            if size and os.pread(fd, 1, size - 1) != b"\n":
                line = b"\n" + line
            os.write(fd, line)
            os.fsync(fd)  # a stop that was reported must survive a crash
        finally:
            os.close(fd)
        return entry

    def ledger(self, kind: str | None = None, profile: str | None = None) -> Iterator[dict[str, Any]]:
        if not self.s.ledger_path.exists():
            return
        with open(self.s.ledger_path, encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    # A writer killed mid-line leaves a torn entry; skip it.
                    continue
                if not isinstance(entry, dict):
                    continue
                if kind and entry.get("kind") != kind:
                    continue
                if profile and entry.get("profile") != profile:
                    continue
                yield entry


def _atomic_write(path: Path, text: str) -> None:
    """Replaces a file, keeping its mode: mkstemp's 0600 would lock another account's dispatcher out."""
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o644
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w") as fh:
            fh.write(text)
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        os.unlink(tmp)
        raise

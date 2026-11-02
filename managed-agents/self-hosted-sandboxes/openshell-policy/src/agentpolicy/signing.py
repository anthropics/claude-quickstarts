"""Ed25519 signatures for ceilings.

A ceiling is the one file in this design that a person, not a process, must
own. Signing it lets every component that reads it (the dispatcher, the
reviewer, promote, shrink) refuse a ceiling that changed after the person
approved it, or that someone without a trusted key wrote.

The trusted keys live in ``policy/signers.yaml``::

    signers:
      - identity: alice@example.com
        public_key: <base64 of the 32-byte Ed25519 public key>
"""

from __future__ import annotations

import base64
import os
from pathlib import Path

import yaml
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey


def generate(path: Path) -> Ed25519PrivateKey:
    """Writes a new private key, readable only by its owner."""
    key = Ed25519PrivateKey.generate()
    pem = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as fh:
        fh.write(pem)
    return key


def load_private_key(path: Path) -> Ed25519PrivateKey:
    key = serialization.load_pem_private_key(path.read_bytes(), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError(f"{path} is not an Ed25519 private key")
    return key


def public_key_text(key: Ed25519PrivateKey) -> str:
    raw = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return base64.b64encode(raw).decode()


def sign(key: Ed25519PrivateKey, payload: bytes) -> str:
    return base64.b64encode(key.sign(payload)).decode()


def verify(public_key_b64: str, payload: bytes, signature_b64: str) -> bool:
    try:
        pub = Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key_b64))
        pub.verify(base64.b64decode(signature_b64), payload)
        return True
    except (InvalidSignature, ValueError):
        return False


def load_signers(path: Path | None) -> dict[str, str]:
    """Maps each trusted identity to its public key."""
    if path is None or not path.exists():
        return {}
    data = yaml.safe_load(path.read_text()) or {}
    out: dict[str, str] = {}
    for entry in data.get("signers") or []:
        out[str(entry["identity"])] = str(entry["public_key"])
    return out

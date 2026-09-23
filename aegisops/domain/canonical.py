"""Canonical JSON and hashing shared by scenario fingerprints and the audit event chain."""

from __future__ import annotations

import hashlib
import json


def canonical_json(value: object) -> str:
    """Serialise JSON-compatible data with sorted keys and no insignificant whitespace."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_hex(text: str) -> str:
    """Return the lowercase hex SHA-256 of UTF-8 ``text``."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

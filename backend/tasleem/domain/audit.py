"""R6: per-case hash chain. Any edit, deletion or reordering of a stored event breaks verification."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .model import to_utc

GENESIS = "0" * 64


def canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def event_hash(
    prev_hash: str, case_id: str, seq: int, type_: str, actor_id: str, actor_type: str,
    occurred_at: datetime, payload: dict[str, Any],
) -> str:
    material = "|".join([prev_hash, case_id, str(seq), type_, actor_id, actor_type,
                         to_utc(occurred_at).isoformat(), canonical(payload)])
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class StoredEvent:
    case_id: str
    seq: int
    type: str
    actor_id: str
    actor_type: str
    occurred_at: datetime
    payload: dict[str, Any]
    prev_hash: str
    hash: str


@dataclass(frozen=True)
class Verification:
    ok: bool
    checked: int
    broken_at_seq: int | None = None
    problem: str | None = None


def verify(events: Iterable[StoredEvent]) -> Verification:
    prev = GENESIS
    expected_seq = 1
    n = 0
    for e in events:
        n += 1
        if e.seq != expected_seq:
            return Verification(False, n, e.seq, f"sequence gap: expected {expected_seq}")
        if e.prev_hash != prev:
            return Verification(False, n, e.seq, "previous-hash link broken")
        h = event_hash(e.prev_hash, e.case_id, e.seq, e.type, e.actor_id, e.actor_type, e.occurred_at, e.payload)
        if h != e.hash:
            return Verification(False, n, e.seq, "event content does not match its hash")
        prev = e.hash
        expected_seq += 1
    return Verification(True, n)

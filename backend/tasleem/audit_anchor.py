"""Audit anchoring (TSL-173): one root hash over every case's audit chain, as of a moment.

Each case's chain is already tamper-evident (R6). But someone with database access could rewrite a whole chain
and recompute it. Publishing a daily root *outside* the database (a log line shipped off the server, an email to
the programme, an immutable blob) closes that gap: any rewrite of history before the anchor changes the root.

    python -m tasleem.audit_anchor                 # root now, printed as one JSON line for the log
    python -m tasleem.audit_anchor --as-of 2026-11-19T00:00:00Z
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .infra.db import CaseEventRow


def anchor(session: Session, as_of: datetime | None = None) -> dict:
    """Root = SHA-256 over 'case_id:seq:hash' of each case's last event recorded at or before `as_of`, sorted."""
    as_of = as_of or datetime.now(UTC)
    last = (select(CaseEventRow.case_id, func.max(CaseEventRow.seq).label("seq"))
            .where(CaseEventRow.recorded_at <= as_of).group_by(CaseEventRow.case_id).subquery())
    rows = session.execute(
        select(CaseEventRow.case_id, CaseEventRow.seq, CaseEventRow.hash)
        .join(last, (CaseEventRow.case_id == last.c.case_id) & (CaseEventRow.seq == last.c.seq))
        .order_by(CaseEventRow.case_id)).all()
    h = hashlib.sha256()
    for case_id, seq, digest in rows:
        h.update(f"{case_id}:{seq}:{digest}\n".encode())
    return {"kind": "tasleem.audit_anchor", "as_of": as_of.isoformat(), "cases": len(rows), "root": h.hexdigest()}


def main() -> None:
    from .api.context import AppContext
    from .config import Settings

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--as-of", type=lambda s: datetime.fromisoformat(s.replace("Z", "+00:00")))
    a = ap.parse_args()
    ctx = AppContext.build(Settings())
    with ctx.sessions() as s:
        print(json.dumps(anchor(s, a.as_of)), flush=True)


if __name__ == "__main__":
    main()

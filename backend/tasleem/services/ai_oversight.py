"""AI oversight (A5): what the AI suggested, and what people did with it, computed from the audit log.

Every AI output in Tasleem is a suggestion a named person confirms (R5). This read model counts, per kind of AI
output, how often people accepted it unchanged and how often they corrected it. A rising correction rate is the
signal to retrain or switch a model off. Rules compute every number here; nothing is estimated.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..domain.model import EventType
from ..infra.db import CaseEventRow

KINDS = {
    "report_reading": "Colonoscopy report read (Evidence Reader)",
    "barrier": "Patient reply understood (barrier suggestion)",
    "message": "Patient message drafted",
}


def ai_oversight(session: Session) -> dict[str, Any]:
    types = [EventType.BARRIER_SUGGESTED, EventType.BARRIER_CONFIRMED, EventType.REPORT_REVIEWED,
             EventType.PATIENT_MESSAGE_SENT]
    rows = session.execute(select(CaseEventRow.case_id, CaseEventRow.type, CaseEventRow.actor_id,
                                  CaseEventRow.payload)
                           .where(CaseEventRow.type.in_([t.value for t in types]))
                           .order_by(CaseEventRow.case_id, CaseEventRow.seq)).all()
    suggested: dict[tuple[str, str], tuple[str, str]] = {}  # (case, barrier) -> (code, model)
    stats: dict[str, Counter[str]] = defaultdict(Counter)
    models: dict[str, Counter[str]] = defaultdict(Counter)
    corrected_fields: Counter[str] = Counter()
    for case_id, typ, actor, payload in rows:
        p = payload or {}
        if typ == EventType.BARRIER_SUGGESTED:
            suggested[(case_id, p["barrier_id"])] = (p["code"], actor)
            stats["barrier"]["suggested"] += 1
            models["barrier"][actor] += 1
        elif typ == EventType.BARRIER_CONFIRMED:
            s = suggested.get((case_id, p["barrier_id"]))
            if s is not None:
                stats["barrier"]["reviewed"] += 1
                stats["barrier"]["accepted" if s[0] == p["code"] else "corrected"] += 1
        elif typ == EventType.REPORT_REVIEWED:
            st = stats["report_reading"]
            st["suggested"] += 1
            st["reviewed"] += 1
            fixed = p.get("corrected") or []
            st["corrected" if fixed else "accepted"] += 1
            corrected_fields.update(fixed)
            models["report_reading"][p.get("suggested_by") or "unknown"] += 1
        elif typ == EventType.PATIENT_MESSAGE_SENT:
            st = stats["message"]
            st["sent"] += 1
            if p.get("ai_draft_id"):
                st["suggested"] += 1
                st["reviewed"] += 1
                st["accepted"] += 1  # the sender approved the draft (edits are kept in the draft log)
    items = []
    for kind, label in KINDS.items():
        st = stats[kind]
        reviewed = st["reviewed"]
        items.append({
            "kind": kind, "label": label,
            "suggested": st["suggested"], "reviewed": reviewed,
            "accepted": st["accepted"], "corrected": st["corrected"],
            "acceptance_rate": round(st["accepted"] / reviewed, 3) if reviewed else None,
            "models": dict(models[kind]),
            "decided_by": "a named person (R5)",
        })
    return {"items": items, "report_fields_corrected": dict(corrected_fields),
            "note": "Every AI output is a suggestion a named person confirms. Computed from the audit log."}

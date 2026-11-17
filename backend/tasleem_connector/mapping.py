"""HL7 v2 -> FHIR R4 / referral-status mapping. Pure functions; every assumption is named.

ASSUMPTIONS to confirm against Malaffi's interface specifications before a pilot:
- PID-3 (first repetition, component 1) carries the identifier Tasleem uses for the patient.
- REF RF1-1 uses HL7 table 0283 (A accepted, P pending, R rejected, E expired) plus a local "C" for
  completed. REF is *administrative status*: it is sent as a referral-status message and never as
  clinical evidence, except an explicit rejection, which is the receiving service's decision.
- SIU SCH-11 component 4 (or AIS-4) is the appointment start.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .hl7 import HL7Error, Message, Segment, ts

LOINC_SYSTEMS = {"LN", "LOINC", "http://loinc.org"}
REPORT_CODES = {"18746-8", "11526-1"}  # colonoscopy study report, pathology report
POSITIVE_TEXT = {"POS", "POSITIVE", "DETECTED", "REACTIVE"}
REF_STATUS = {"P": "SENT", "A": "ACCEPTED", "E": "CANCELLED", "C": "COMPLETED"}


@dataclass
class Forward:
    """What to send to case-core: `kind` is 'fhir' or 'referral-status'."""

    kind: str
    body: dict[str, Any]
    message_id: str


def _patient(msg: Message) -> str:
    pid = msg.first("PID")
    if pid is None or not pid.get(3):
        raise HL7Error("PID-3 patient identifier is required")
    return pid.get(3)


def _iso(seg: Segment, n: int, fallback: Message) -> str:
    t = ts(seg.get(n)) or ts(fallback.msh.get(7))
    if t is None:
        raise HL7Error("no event time (field or MSH-7)")
    return t.isoformat()


def _loinc(seg: Segment, n: int) -> dict[str, Any]:
    c = seg.components(n)
    code, text, system = (c + ["", "", ""])[:3]
    sys = "http://loinc.org" if system.upper() in LOINC_SYSTEMS or not system else f"urn:hl7v2:{system}"
    return {"coding": [{"system": sys, "code": code}], "text": text or None}


def oru(msg: Message) -> list[Forward]:
    """ORU^R01: each final OBX becomes an Observation, or the OBR becomes a DiagnosticReport when it is a
    report the pathways track (colonoscopy or pathology)."""
    pid = _patient(msg)
    ctrl = msg.control_id
    out: list[dict[str, Any]] = []
    for obr in msg.all("OBR"):
        if obr.get(4) in REPORT_CODES and obr.get(25) in ("F", "C"):
            out.append({"resourceType": "DiagnosticReport", "id": f"{ctrl}-obr{obr.get(1) or '1'}",
                        "status": "final" if obr.get(25) == "F" else "corrected",
                        "subject": {"reference": f"Patient/{pid}"}, "code": _loinc(obr, 4),
                        "issued": _iso(obr, 22, msg)})
    for obx in msg.all("OBX"):
        status = obx.get(11)
        if status not in ("F", "C"):
            continue  # preliminary results never drive a case
        code = obx.get(3)
        if code in REPORT_CODES:
            continue
        r: dict[str, Any] = {"resourceType": "Observation", "id": f"{ctrl}-obx{obx.get(1) or len(out) + 1}",
                             "status": "final" if status == "F" else "corrected",
                             "subject": {"reference": f"Patient/{pid}"}, "code": _loinc(obx, 3),
                             "effectiveDateTime": _iso(obx, 14, msg)}
        flags = [f for f in obx.fields[8].split(obx.enc[1]) if f] if len(obx.fields) > 8 else []
        value = obx.get(5)
        if obx.get(2) in ("NM", "SN") and value:
            try:
                r["valueQuantity"] = {"value": float(value), "unit": obx.get(6) or None}
            except ValueError as exc:
                raise HL7Error(f"OBX-5 is not a number: {value[:20]!r}") from exc
        elif value.upper() in POSITIVE_TEXT:
            flags.append("POS")
        if flags:
            r["interpretation"] = [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/"
                                                          "v3-ObservationInterpretation", "code": f}]}
                                   for f in dict.fromkeys(flags)]
        out.append(r)
    if not out:
        return []
    bundle = {"resourceType": "Bundle", "type": "collection", "entry": [{"resource": r} for r in out]}
    return [Forward("fhir", bundle, ctrl)]


def ref(msg: Message, trigger: str) -> list[Forward]:
    """REF^I12/I13/I14 -> referral status; RF1-1 'R' -> FHIR Task rejected (with the reason)."""
    pid = _patient(msg)
    rf1 = msg.first("RF1")
    if rf1 is None:
        raise HL7Error("RF1 segment is required")
    referral_id = rf1.get(6) or rf1.get(11)
    if not referral_id:
        raise HL7Error("RF1-6 originating referral identifier is required")
    when = _iso(rf1, 7, msg)
    code = "CANCEL" if trigger == "I14" else rf1.get(1)
    if code == "R":
        reason = rf1.get(10, 2) or rf1.get(10) or "unspecified"
        task = {"resourceType": "Task", "id": f"ref-{referral_id}", "status": "rejected", "intent": "order",
                "for": {"reference": f"Patient/{pid}"}, "statusReason": {"text": reason},
                "meta": {"lastUpdated": when, "versionId": msg.control_id}}
        return [Forward("fhir", task, msg.control_id)]
    status = "CANCELLED" if code == "CANCEL" else REF_STATUS.get(code)
    if status is None:
        raise HL7Error(f"unsupported RF1-1 referral status {code!r}")
    service = (rf1.get(3, 2) or rf1.get(3) or "").lower() or None
    return [Forward("referral-status", {"message_id": msg.control_id, "referral_id": referral_id,
                                        "patient_id": pid, "status": status, "occurred_at": when,
                                        "service": service}, msg.control_id)]


SIU_STATUS = {"S12": "booked", "S13": "booked", "S14": "booked", "S15": "cancelled", "S26": "noshow"}


def siu(msg: Message, trigger: str) -> list[Forward]:
    pid = _patient(msg)
    sch = msg.first("SCH")
    if sch is None:
        raise HL7Error("SCH segment is required")
    appt_id = sch.get(1) or sch.get(2)
    if not appt_id:
        raise HL7Error("SCH-1 or SCH-2 appointment id is required")
    status = SIU_STATUS.get(trigger)
    if sch.get(25).lower() in ("complete", "completed"):
        status = "fulfilled"
    if status is None:
        raise HL7Error(f"unsupported SIU trigger {trigger}")
    start = ts(sch.get(11, 4))
    ais = msg.first("AIS")
    if start is None and ais is not None:
        start = ts(ais.get(4))
    updated = ts(msg.msh.get(7)) or start
    r: dict[str, Any] = {"resourceType": "Appointment", "id": appt_id, "status": status,
                         "meta": {"versionId": msg.control_id},
                         "participant": [{"actor": {"reference": f"Patient/{pid}"}, "status": "accepted"}]}
    if updated is not None:
        r["meta"]["lastUpdated"] = updated.isoformat()
    if start is not None:
        r["start"] = start.isoformat()
    elif status == "booked":
        raise HL7Error("a booking needs a start time (SCH-11.4 or AIS-4)")
    return [Forward("fhir", r, msg.control_id)]


def to_core(msg: Message) -> list[Forward]:
    kind, trigger = msg.type
    if kind == "ORU" and trigger == "R01":
        return oru(msg)
    if kind == "REF" and trigger in ("I12", "I13", "I14"):
        return ref(msg, trigger)
    if kind == "SIU" and trigger in SIU_STATUS:
        return siu(msg, trigger)
    raise HL7Error(f"unsupported message type {kind}^{trigger}")

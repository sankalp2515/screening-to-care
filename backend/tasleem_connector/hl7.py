"""Minimal, strict HL7 v2.x ER7 parser: segments, fields, repetitions, components and escapes.

Enough for ORU^R01, REF^I12-I14 and SIU^S12-S26. It never evaluates content and bounds message size and
segment count, so malformed or hostile input fails with a clear error instead of a crash.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

MAX_BYTES = 1_000_000
MAX_SEGMENTS = 2_000
UAE = timezone(timedelta(hours=4))  # HL7 times without an offset are read as Gulf Standard Time
_TS = re.compile(r"^(\d{4})(\d{2})(\d{2})(\d{2})?(\d{2})?(\d{2})?(?:\.\d+)?([+-]\d{4})?$")


class HL7Error(ValueError):
    pass


@dataclass
class Segment:
    name: str
    fields: list[str]  # fields[n] is field n (for MSH, fields[1] is the field separator)
    enc: str = "^~\\&"

    def get(self, n: int, comp: int = 1, rep: int = 1) -> str:
        """Field n, repetition rep, component comp (all 1-based). Empty string if absent."""
        if n >= len(self.fields):
            return ""
        value = self.fields[n]
        if self.name == "MSH" and n in (1, 2):
            return value
        reps = value.split(self.enc[1])
        if rep > len(reps):
            return ""
        comps = reps[rep - 1].split(self.enc[0])
        return unescape(comps[comp - 1], self.enc) if comp <= len(comps) else ""

    def components(self, n: int, rep: int = 1) -> list[str]:
        if n >= len(self.fields):
            return []
        reps = self.fields[n].split(self.enc[1])
        return [unescape(c, self.enc) for c in reps[rep - 1].split(self.enc[0])] if rep <= len(reps) else []


@dataclass
class Message:
    segments: list[Segment] = field(default_factory=list)

    def first(self, name: str) -> Segment | None:
        return next((s for s in self.segments if s.name == name), None)

    def all(self, name: str) -> list[Segment]:
        return [s for s in self.segments if s.name == name]

    @property
    def msh(self) -> Segment:
        m = self.first("MSH")
        if m is None:  # pragma: no cover - parse() guarantees MSH
            raise HL7Error("no MSH segment")
        return m

    @property
    def type(self) -> tuple[str, str]:
        return self.msh.get(9, 1), self.msh.get(9, 2)

    @property
    def control_id(self) -> str:
        return self.msh.get(10)


def unescape(v: str, enc: str) -> str:
    if "\\" not in v:
        return v
    comp, rep, esc, sub = enc[0], enc[1], enc[2], enc[3] if len(enc) > 3 else "&"
    return (v.replace(f"{esc}F{esc}", "|").replace(f"{esc}S{esc}", comp).replace(f"{esc}R{esc}", rep)
            .replace(f"{esc}T{esc}", sub).replace(f"{esc}E{esc}", esc))


def parse(raw: str | bytes) -> Message:
    if isinstance(raw, bytes):
        if len(raw) > MAX_BYTES:
            raise HL7Error("message too large")
        raw = raw.decode("utf-8", errors="strict")
    if len(raw) > MAX_BYTES:
        raise HL7Error("message too large")
    raw = raw.strip("\x0b\x1c\r\n ")  # tolerate MLLP framing characters
    lines = [ln for ln in re.split(r"\r\n|\r|\n", raw) if ln.strip()]
    if not lines or not lines[0].startswith("MSH") or len(lines[0]) < 8:
        raise HL7Error("message must start with an MSH segment")
    if len(lines) > MAX_SEGMENTS:
        raise HL7Error("too many segments")
    fs = lines[0][3]
    enc = lines[0][4:8]
    if fs.isalnum() or len(set(enc)) != len(enc):
        raise HL7Error("invalid MSH encoding characters")
    msg = Message()
    for ln in lines:
        parts = ln.split(fs)
        name = parts[0]
        if not re.fullmatch(r"[A-Z][A-Z0-9]{2}", name):
            raise HL7Error(f"invalid segment name {name[:10]!r}")
        if name == "MSH":
            fields = ["MSH", fs, *parts[1:]]  # MSH-1 is the separator itself
        else:
            fields = parts
        msg.segments.append(Segment(name, fields, enc))
    if not msg.control_id:
        raise HL7Error("MSH-10 message control id is required")
    if not msg.type[0]:
        raise HL7Error("MSH-9 message type is required")
    return msg


def ts(value: str) -> datetime | None:
    """HL7 DTM (YYYY[MM[DD[HH[MM[SS]]]]][+/-ZZZZ]) to an aware datetime."""
    if not value:
        return None
    m = _TS.match(value.strip())
    if not m:
        raise HL7Error(f"bad HL7 timestamp {value[:20]!r}")
    y, mo, d, h, mi, s, off = m.groups()
    tz = UAE
    if off:
        sign = 1 if off[0] == "+" else -1
        tz = timezone(sign * timedelta(hours=int(off[1:3]), minutes=int(off[3:5])))
    try:
        return datetime(int(y), int(mo), int(d), int(h or 0), int(mi or 0), int(s or 0), tzinfo=tz)
    except ValueError as exc:
        raise HL7Error(f"bad HL7 timestamp {value[:20]!r}") from exc


def ack(msg: Message | None, code: str, text: str, now: datetime) -> str:
    """HL7 ACK. code: AA accepted, AE error (sender may fix or retry), AR rejected (not processable)."""
    when = now.astimezone(UAE).strftime("%Y%m%d%H%M%S+0400")
    if msg is not None:
        sender_app, sender_fac = msg.msh.get(3), msg.msh.get(4)
        trigger, ctrl, version = msg.type[1], msg.control_id, msg.msh.get(12) or "2.5.1"
    else:
        sender_app = sender_fac = trigger = ctrl = ""
        version = "2.5.1"
    safe = re.sub(r"[|^~\\&\r\n]", " ", text)[:80]
    return (f"MSH|^~\\&|TASLEEM|TASLEEM|{sender_app}|{sender_fac}|{when}||ACK^{trigger}^ACK|ACK{ctrl}|P|{version}\r"
            f"MSA|{code}|{ctrl}|{safe}\r")

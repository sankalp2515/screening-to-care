"""Evidence Reader, deterministic part: read a free-text colonoscopy report into six findings.

A report arriving is not the same as the loop being closed. Real reports say "incomplete to the hepatic flexure",
"inadequate preparation, BBPS 1-1-0" or "histology awaited". This module reads those sentences with plain
patterns and quotes each one, so a clinician can check the reading against the report in seconds.

It never decides anything. Its output is a suggestion; only findings a clinician confirms reach the rules
(``engine.review_report``), exactly like an AI suggestion (R5). The agent service may offer a model reading
instead; it must quote the report verbatim or it falls back to this one.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass

READER_ID = "keyword-reader-v1"

FIELDS = ("completed", "prep_adequate", "polyps_removed", "pathology_pending", "next_step", "follow_up")

FIELD_LABELS = {
    "completed": "Procedure complete (caecum reached)",
    "prep_adequate": "Bowel preparation adequate",
    "polyps_removed": "Polyps removed",
    "pathology_pending": "Pathology pending",
    "next_step": "Recommended next step",
    "follow_up": "Follow-up interval",
}


@dataclass(frozen=True)
class Finding:
    field: str
    value: bool | int | str | None
    quote: str | None  # the sentence of the report this value comes from, verbatim

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


_WORDS = {"no": 0, "one": 1, "a": 1, "an": 1, "single": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
          "several": 2, "multiple": 2}

_SENT = re.compile(r"[^.;\n。]+[.;\n。]?")


def sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENT.findall(text or "") if s.strip(" .;\n")]


def _first(sents: list[str], *patterns: str) -> tuple[str, re.Match[str]] | None:
    for pat in patterns:
        rx = re.compile(pat, re.I)
        for s in sents:
            m = rx.search(s)
            if m:
                return s, m
    return None


# ---- the six readers -----------------------------------------------------------------------------------------
_INCOMPLETE = (
    r"\bincomplete\b",
    r"\b(unable|failed|could not|not possible) to (reach|advance|intubate|pass)",
    r"\b(caecum|cecum|caecal|cecal)\b[^.]{0,30}\bnot\b[^.]{0,15}\b(reached|intubated|visuali[sz]ed)",
    r"\bnot\b[^.]{0,20}\b(caecum|cecum)\b",
    r"\b(terminated|stopped|abandoned)\b",
    r"غير مكتمل",
    r"لم يتم الوصول",
)
_COMPLETE = (
    r"\b(caecum|cecum|caecal|cecal|terminal ileum|ileocaecal|appendiceal orifice)\b[^.]{0,40}\b(reached|intubated|visuali[sz]ed|identified|seen)",
    r"\b(reached|intubated|to) (the )?(caecum|cecum|terminal ileum)",
    r"\bcomplete (colonoscopy|examination|procedure)",
    r"\bcaecal intubation\b",
    r"تم الوصول إلى الأعور",
    r"منظار كامل",
)


def _completed(sents: list[str]) -> Finding:
    hit = _first(sents, *_INCOMPLETE)
    if hit:
        return Finding("completed", False, hit[0])
    hit = _first(sents, *_COMPLETE)
    if hit:
        return Finding("completed", True, hit[0])
    return Finding("completed", None, None)


_BBPS = re.compile(
    r"(?:bbps|boston(?: bowel preparation)?(?: scale| score)?)\D{0,20}?"
    r"(?:(\d{1,2})\s*\(\s*(\d)\s*[-/,]\s*(\d)\s*[-/,]\s*(\d)\s*\)|(\d)\s*[-/,]\s*(\d)\s*[-/,]\s*(\d)|(\d{1,2})\b)",
    re.I,
)
_PREP_BAD = (r"\b(poor|inadequate|suboptimal|fair|unsatisfactory|insufficient)\b[^.]{0,25}\b(prep|preparation|bowel prep|cleansing)",
             r"\b(prep|preparation|cleansing)\b[^.]{0,25}\b(poor|inadequate|suboptimal|unsatisfactory|insufficient)",
             r"تحضير (ضعيف|غير كاف)")
_PREP_GOOD = (r"\b(good|excellent|adequate|satisfactory)\b[^.]{0,25}\b(prep|preparation|bowel prep|cleansing)",
              r"\b(prep|preparation|cleansing)\b[^.]{0,25}\b(good|excellent|adequate|satisfactory)",
              r"تحضير (جيد|ممتاز)")


def _prep(sents: list[str]) -> Finding:
    for s in sents:
        m = _BBPS.search(s)
        if not m:
            continue
        parts = [m.group(i) for i in (2, 3, 4)] if m.group(2) else [m.group(i) for i in (5, 6, 7)]
        if parts[0] is not None:
            seg = [int(x) for x in parts]
            # Adequate = every segment scores 2 or more (total 6 or more).
            return Finding("prep_adequate", min(seg) >= 2, s)
        total = m.group(8) or m.group(1)
        if total is not None and int(total) <= 9:
            return Finding("prep_adequate", int(total) >= 6, s)
    hit = _first(sents, *_PREP_BAD)
    if hit:
        return Finding("prep_adequate", False, hit[0])
    hit = _first(sents, *_PREP_GOOD)
    if hit:
        return Finding("prep_adequate", True, hit[0])
    return Finding("prep_adequate", None, None)


_POLYP_N = re.compile(
    r"\b(\d+|no|one|a|an|single|two|three|four|five|six|several|multiple)\b\s+(?:\w+\s+){0,3}?polyps?\b", re.I)


def _polyps(sents: list[str]) -> Finding:
    for s in sents:
        low = s.lower()
        if re.search(r"\bno (?:\w+ ){0,2}polyps?\b|\bno polyp|لا توجد زوائد", low):
            return Finding("polyps_removed", 0, s)
        m = _POLYP_N.search(s)
        if m and re.search(r"remov|resect|polypectomy|excis|snare|retrieved|استئصال", low):
            w = m.group(1).lower()
            n = int(w) if w.isdigit() else _WORDS.get(w, 1)
            return Finding("polyps_removed", n, s)
    hit = _first(sents, r"\bpolypectomy\b", r"استئصال (الزوائد|زائدة)")
    if hit:
        return Finding("polyps_removed", 1, hit[0])
    return Finding("polyps_removed", None, None)


_PATH_PENDING = (r"\b(histology|histopathology|pathology|biopsy|biopsies|specimens?)\b[^.]{0,40}\b(pending|awaited|to follow|sent|submitted|outstanding)",
                 r"\b(await|awaiting|pending)\b[^.]{0,20}\b(histology|histopathology|pathology|biopsy)",
                 r"(نتيجة|نتائج) (الخزعة|الأنسجة) (قيد الانتظار|لاحقا)")
_PATH_DONE = (r"\b(histology|histopathology|pathology)\b[^.]{0,15}(:|shows?|showed|confirms?|confirmed|revealed|reports?)",
              r"\b(tubular|tubulovillous|villous|serrated|hyperplastic) (adenoma|polyp)",
              r"\badenocarcinoma\b", r"\bno dysplasia\b")


def _pathology(sents: list[str], polyps: Finding) -> Finding:
    hit = _first(sents, *_PATH_PENDING)
    if hit:
        return Finding("pathology_pending", True, hit[0])
    hit = _first(sents, *_PATH_DONE)
    if hit:
        return Finding("pathology_pending", False, hit[0])
    if polyps.value == 0:
        return Finding("pathology_pending", False, polyps.quote)
    return Finding("pathology_pending", None, None)


_NEXT = (r"\b(recommend\w*|plan|advised?|suggest\w*)\b",
         r"\b(repeat|rebook|re-book|refer\w*|surveillance|follow[- ]?up|ct colonography|routine screening|next screening|screening colonoscopy|return to)\b",
         r"(يوصى|ننصح|إعادة)")


def _next_step(sents: list[str]) -> Finding:
    hit = _first(sents, *_NEXT)
    if hit:
        return Finding("next_step", hit[0].rstrip(" ."), hit[0])
    return Finding("next_step", None, None)


_INTERVAL = re.compile(
    r"\b(?:in|after|within)?\s*(\d{1,2}|one|two|three|five|ten|six)\s*[- ]?\s*(weeks?|months?|years?)\b", re.I)
_AR_INTERVAL = re.compile(r"(?:بعد|خلال)\s*(\d{1,2}|ثلاثة|ستة|خمس|عشر)\s*(أشهر|شهور|سنوات|أسابيع)")
_AR_NUM = {"ثلاثة": "3", "ستة": "6", "خمس": "5", "عشر": "10"}
_AR_UNIT = {"أشهر": "months", "شهور": "months", "سنوات": "years", "أسابيع": "weeks"}


def _follow_up(sents: list[str]) -> Finding:
    for s in sents:
        if not re.search(r"repeat|surveillance|follow|recall|colonoscopy|screening|rebook|إعادة|متابعة|منظار", s, re.I):
            continue
        m = _INTERVAL.search(s)
        if m:
            n, unit = m.group(1).lower(), m.group(2).lower()
            n = str(_WORDS.get(n, {"ten": 10}.get(n, n))) if not n.isdigit() else n
            unit = unit if unit.endswith("s") or n == "1" else unit + "s"
            return Finding("follow_up", f"{n} {unit}", s)
        m = _AR_INTERVAL.search(s)
        if m:
            return Finding("follow_up", f"{_AR_NUM.get(m.group(1), m.group(1))} {_AR_UNIT[m.group(2)]}", s)
    return Finding("follow_up", None, None)


def read_report(text: str) -> dict[str, Finding]:
    """Read a report. Every field is present; a field the report does not mention has value None."""
    sents = sentences(text)
    polyps = _polyps(sents)
    out = {
        "completed": _completed(sents),
        "prep_adequate": _prep(sents),
        "polyps_removed": polyps,
        "pathology_pending": _pathology(sents, polyps),
        "next_step": _next_step(sents),
        "follow_up": _follow_up(sents),
    }
    return out


def reading_dict(text: str) -> dict[str, dict[str, object]]:
    return {k: v.as_dict() for k, v in read_report(text).items()}


def quotes_are_verbatim(text: str, reading: dict[str, dict[str, object]]) -> bool:
    """Guard for model readings: every quote must appear in the report exactly (whitespace-normalised)."""
    norm = " ".join((text or "").split())
    for f in reading.values():
        q = f.get("quote")
        if q and " ".join(str(q).split()) not in norm:
            return False
    return True

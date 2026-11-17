"""Patient-message policy: what a care-team message to a patient may and may not contain.

IFHAS clause 4.9.2.3: abnormal findings are discussed with the person present. A message may invite,
remind, explain logistics or ask what got in the way. It must never carry a result value, a diagnosis
word or a link. This is a deterministic check, so the same text always gets the same answer, and it is
the single authority: the AI agent calls it through the API before showing a draft, and the engine runs
it again before anything is sent.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

MAX_CHARS = 600

# Numbers that look like a measurement or result: "9.0", "162", "7 %", "120/80". Times like "9:30",
# dates like "21 Nov" and short counts like "2 days" are allowed so logistics messages still work.
_VALUE = re.compile(r"(\d+[.,]\d+)|(\d+\s*/\s*\d+)|(\d+\s*(%|mg|mmol|ng|µg|ug|mm\s*hg|mmhg|g/dl|iu)\b)"
                    r"|(\b\d{3,}\b(?!\s*(?:am|pm)))", re.IGNORECASE)
_LINK = re.compile(r"(https?://|www\.|\b[a-z0-9-]+\.(com|net|org|ae|io|ly)\b)", re.IGNORECASE)
# Words that disclose or interpret a result. Kept short and explicit so it can be reviewed by a clinician.
_RESULT_TERMS_EN = ("cancer", "malignan", "tumour", "tumor", "carcinoma", "polyp", "positive", "negative",
                    "abnormal", "normal result", "diagnos", "biopsy result", "your result is", "your results are",
                    "diabetes", "diabetic", "hypertension", "high blood pressure", "lesion", "metasta")
_RESULT_TERMS_AR = ("سرطان", "ورم", "خبيث", "إيجابي", "ايجابي", "سلبي", "غير طبيعي", "تشخيص", "سكري",
                    "ضغط الدم المرتفع", "زوائد")
# Advice the care team must give in person, not by text.
_ADVICE_TERMS = ("stop taking", "increase your dose", "you are fine", "nothing to worry", "no need to come",
                 "you don't need", "you do not need", "لا داعي للقلق", "لا تحتاج")


@dataclass(frozen=True)
class Violation:
    code: str
    detail: str


def check_patient_text(text: str) -> list[Violation]:
    """Return every rule the text breaks. Empty list = safe to send."""
    t = (text or "").strip()
    out: list[Violation] = []
    if not t:
        return [Violation("EMPTY", "The message is empty.")]
    if len(t) > MAX_CHARS:
        out.append(Violation("TOO_LONG", f"Keep patient messages under {MAX_CHARS} characters."))
    low = t.lower()
    m = _VALUE.search(t)
    if m:
        out.append(Violation("RESULT_VALUE", f"Looks like a result value: '{m.group(0).strip()}'."))
    for term in _RESULT_TERMS_EN + _RESULT_TERMS_AR:
        if term in low:
            out.append(Violation("RESULT_DISCLOSURE", f"Discloses or interprets a result: '{term}'."))
            break
    for term in _ADVICE_TERMS:
        if term in low:
            out.append(Violation("CLINICAL_ADVICE", f"Clinical reassurance or advice by text: '{term}'."))
            break
    if _LINK.search(t):
        out.append(Violation("LINK", "Links are not allowed; patients open Sahatna directly."))
    return out

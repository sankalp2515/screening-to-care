"""Barrier suggestion and distress detection.

Both are *suggestions or routing signals*. Neither decides anything clinical (R5):
- The classifier proposes a barrier code; a navigator or clinician confirms it.
- The distress detector is deliberately high-recall: any match routes the message to a clinician now.
  Every free-text reply is shown to a human regardless of what these functions return.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Protocol

from .model import BarrierCode


@dataclass(frozen=True)
class Suggestion:
    code: BarrierCode
    confidence: float
    model: str


class BarrierClassifier(Protocol):
    name: str

    def classify(self, text: str) -> Suggestion | None: ...


_ARABIC_DIACRITICS = re.compile(r"[ً-ْٰـ]")


def normalize(text: str) -> str:
    t = unicodedata.normalize("NFKC", text).lower()
    t = _ARABIC_DIACRITICS.sub("", t)
    # unify common Arabic letter variants
    return t.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا").replace("ى", "ي").replace("ة", "ه")


def _has_latin(term: str) -> bool:
    return bool(re.search(r"[a-z]", term))


_AR_PREFIX = r"(?:[وفبلك])?(?:ال)?"
_AR_SUFFIX = r"(?:ها|نا|هم|كم|ي|ه|ك)?"


def _matches(text_norm: str, term: str) -> bool:
    """Whole-word match. Arabic terms allow common attached prefixes (و ف ب ل ك ال) and pronoun suffixes."""
    term_n = normalize(term)
    if _has_latin(term_n):
        return re.search(rf"(?<![a-z]){re.escape(term_n)}(?![a-z])", text_norm) is not None
    pattern = rf"(?<!\w){_AR_PREFIX}{re.escape(term_n)}{_AR_SUFFIX}(?!\w)"
    return re.search(pattern, text_norm) is not None


# English and Gulf/MSA Arabic cue phrases. Extend via tests in tests/test_barriers.py.
BARRIER_LEXICON: dict[BarrierCode, list[str]] = {
    BarrierCode.FEAR: ["scared", "afraid", "fear", "worried", "nervous", "anxious", "frightened", "terrified",
                       "خايف", "خائف", "خوف", "قلق", "اخاف", "خايفه"],
    BarrierCode.PREP_UNCLEAR: ["prep", "preparation", "laxative", "bowel prep", "what to eat", "fasting",
                               "don't understand", "dont understand", "confused", "instructions",
                               "تحضير", "ملين", "صيام", "ما فهمت", "لا افهم", "التعليمات"],
    BarrierCode.NO_ESCORT: ["no one to", "nobody to", "alone", "escort", "accompany", "take me home",
                            "drive me home", "pick me up", "وحدي", "مرافق", "يوصلني", "احد يوصلني"],
    BarrierCode.TRANSPORT: ["transport", "taxi", "bus", "no car", "too far", "distance", "parking",
                            "مواصلات", "سياره", "بعيد", "تاكسي"],
    BarrierCode.COST_OR_INSURANCE: ["cost", "pay", "expensive", "insurance", "not covered", "money", "afford",
                                    "تكلفه", "تامين", "غالي", "فلوس", "مو مغطي"],
    BarrierCode.TIME_OR_WORK: ["work", "shift", "busy", "no time", "leave", "boss", "travel", "travelling",
                               "manager", "day off",
                               "دوام", "شغل", "مشغول", "ما عندي وقت", "اجازه", "مسافر"],
    BarrierCode.LANGUAGE: ["language", "translator", "interpreter", "english", "arabic", "urdu", "hindi",
                           "tagalog", "لغه", "مترجم"],
    BarrierCode.FEMALE_CLINICIAN: ["female doctor", "woman doctor", "lady doctor", "female endoscopist",
                                   "male doctor", "embarrassed", "embarrassing", "embarrassment",
                                   "طبيبة", "دكتورة", "احراج", "محرج", "استحي", "طبيب رجل"],
    BarrierCode.WANTS_CALLBACK: ["call me", "callback", "call back", "phone me", "talk to someone",
                                 "speak to", "اتصل", "كلمني", "اتصلوا"],
    BarrierCode.DONE_ELSEWHERE: ["already done", "already did", "did it at", "did it in", "another hospital",
                                 "other hospital", "other clinic", "abroad", "back home", "سويته",
                                 "مستشفى ثاني", "مستشفي ثاني", "سويت الفحص"],
}

# High-recall red flags and acute distress. Any match routes to a clinician immediately.
DISTRESS_LEXICON: list[str] = [
    # red-flag symptoms
    "bleeding", "blood", "black stool", "severe pain", "a lot of pain", "fainted", "fainting", "dizzy",
    "chest pain", "vomiting", "weight loss",
    # acute distress
    "terrified", "panic", "panicking", "can't cope", "cant cope", "hopeless", "can't sleep", "cant sleep",
    "crying", "very scared", "so scared", "want to die", "suicide", "suicidal", "kill myself",
    # Arabic
    "نزيف", "دم", "الم شديد", "اغمي", "دوخه", "ترجيع", "مرعوب", "منهار", "ما اقدر انام", "ابكي", "يائس",
]


# Pain is a red flag only when the patient says it is severe or worsening: "pain" near an intensifier.
# (Plain "pain", e.g. worry about pain from the procedure, is a barrier, not distress.)
_SEVERE = (r"unbearable|excruciating|terrible|horrible|worst|severe|intense|getting worse|worse and worse|"
           r"can'?t (?:stand|bear|take)|really bad|so bad|very bad")
_PAIN_SEVERITY_EN = re.compile(
    rf"(?:\b(?:pain|ache|aching|cramps?)\b(?:\W+\w+){{0,4}}?\W+(?:{_SEVERE})\b)|"
    rf"(?:\b(?:{_SEVERE})\b(?:\W+\w+){{0,3}}?\W+(?:pain|ache|aching|cramps?)\b)")
_PAIN_SEVERITY_AR = re.compile(r"(?:الم|وجع|الالم|الوجع)\s+(?:\S+\s+){0,2}?(?:شديد|قوي|ما يتحمل|ما يحتمل|"
                               r"لا يحتمل|لا يطاق|ما ينطاق|يزيد)")


class KeywordBarrierClassifier:
    """Deterministic, offline, explainable baseline. Any LLM classifier must beat it on the benchmark."""

    name = "keyword-v1"

    def classify(self, text: str) -> Suggestion | None:
        t = normalize(text)
        scores: dict[BarrierCode, int] = {}
        for code, terms in BARRIER_LEXICON.items():
            hits = sum(1 for term in terms if _matches(t, term))
            if hits:
                scores[code] = hits
        if not scores:
            return None
        ranked = sorted(scores.items(), key=lambda kv: (-kv[1], list(BarrierCode).index(kv[0])))
        best, best_hits = ranked[0]
        runner_up = ranked[1][1] if len(ranked) > 1 else 0
        confidence = 0.9 if runner_up == 0 else round(best_hits / (best_hits + runner_up), 2)
        return Suggestion(code=best, confidence=confidence, model=self.name)


# A symptom the patient explicitly denies ("no bleeding", "without blood", "ما في نزيف") is not a red flag.
# Deliberately narrow: "not bleeding much" or "no more bleeding?" still flag, because a missed red flag costs
# far more than a clinician clearing a false one.
_DENIAL_EN = ("no", "without")
_DENIAL_AR = ("ما في", "مافي", "بدون", "لا يوجد", "ما فيه", "مافيه")


def _denied(t: str, term: str) -> bool:
    """True when every occurrence of `term` in `t` is directly preceded by a denial word."""
    term_n = normalize(term)
    if _has_latin(term_n):
        occ = list(re.finditer(rf"(?<![a-z]){re.escape(term_n)}(?![a-z])", t))
        return bool(occ) and all(re.search(rf"(?:^|\W)(?:{'|'.join(_DENIAL_EN)})\s+$", t[:m.start()]) for m in occ)
    occ = list(re.finditer(re.escape(term_n), t))
    denials = [normalize(d) for d in _DENIAL_AR]
    return bool(occ) and all(any(t[:m.start()].rstrip().endswith(d) for d in denials) for m in occ)


def detect_distress(text: str) -> list[str]:
    t = normalize(text)
    hits = [term for term in DISTRESS_LEXICON if _matches(t, term) and not _denied(t, term)]
    if _PAIN_SEVERITY_EN.search(t) or _PAIN_SEVERITY_AR.search(t) or _matches(t, "unbearable"):
        hits.append("pain:severe")
    return hits

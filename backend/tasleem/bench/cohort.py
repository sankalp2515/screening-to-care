"""Synthetic FIT-positive cohort with known ground truth and injected failures.

Every patient gets one scenario. The scenario decides where the real care journey stops and what the
referral system (Malaffi REF status) says meanwhile. Ground truth is written down before any arm runs,
so no arm can influence its own score.

Timings use jitter inside the pathway deadlines for steps that happen. "Stopped at" is the time of the
last real care event (or the missed appointment, the rejection, the patient's message): latency is
measured from there for every arm, so no arm's own deadlines define the truth.

Scenario weights are design choices that make every failure type well represented. They are NOT
prevalence estimates. Results are reported per scenario, so conclusions do not depend on the mix.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from ..domain.model import AdminStatus
from ..seed import appt, comm, discussed, fit, procedure, ref, referral, report, task
from ..services.fhir import PURPOSE_INVITE, PURPOSE_OUTCOME

BASE = datetime(2026, 5, 1, 7, 0, tzinfo=UTC)  # fixed, so the same seed gives the same cohort
HORIZON_DAYS = 110

CLEAN = {"CLEAN_COMPLETE", "CLEAN_IN_PROGRESS"}

# scenario -> (weight, stall reasons that count as the right explanation in Tasleem)
SCENARIOS: dict[str, tuple[int, set[str]]] = {
    "CLEAN_COMPLETE": (34, set()),
    "CLEAN_IN_PROGRESS": (8, set()),
    "NEVER_INVITED": (5, {"STEP_OVERDUE"}),
    "NOT_DISCUSSED": (5, {"STEP_OVERDUE"}),
    "NOT_REFERRED": (5, {"STEP_OVERDUE"}),
    "REFERRAL_REJECTED": (6, {"REFERRAL_REJECTED"}),
    "NOT_BOOKED": (6, {"STEP_OVERDUE"}),
    "NO_SHOW": (10, {"BOOKED_NOT_ATTENDED"}),
    "NO_PROCEDURE": (5, {"CONSULT_NO_PROCEDURE"}),
    "FALSE_DONE": (8, {"CLOSED_WITHOUT_EVIDENCE", "CONSULT_NO_PROCEDURE"}),
    "REPORT_NOT_COMMUNICATED": (5, {"REPORT_NOT_COMMUNICATED"}),
    "DISTRESS": (3, {"DISTRESS"}),
}

# Patient replies after a missed appointment: (text, true barrier). Some are deliberately phrased
# without the classifier's cue words, so the barrier score is not flattering by construction.
BARRIER_TEXTS: list[tuple[str, str]] = [
    ("I was too scared of the sedation", "FEAR"),
    ("انا خايفة من التخدير", "FEAR"),
    ("Honestly the whole thing makes me nervous", "FEAR"),
    ("I did not understand the bowel prep instructions", "PREP_UNCLEAR"),
    ("ما فهمت التحضير قبل المنظار", "PREP_UNCLEAR"),
    ("Which drink do I take the night before? Nobody explained", "PREP_UNCLEAR"),
    ("No one can drive me home after", "NO_ESCORT"),
    ("ما في احد يوصلني البيت", "NO_ESCORT"),
    ("My husband travels and I have nobody to come with me", "NO_ESCORT"),
    ("The centre is too far and I have no car", "TRANSPORT"),
    ("المكان بعيد وما عندي سيارة", "TRANSPORT"),
    ("My insurance said it is not covered", "COST_OR_INSURANCE"),
    ("التامين ما يغطي", "COST_OR_INSURANCE"),
    ("I could not get leave from work", "TIME_OR_WORK"),
    ("عندي دوام الصبح", "TIME_OR_WORK"),
    ("Please call me, I have questions", "WANTS_CALLBACK"),
    ("ابي احد يتصل فيني", "WANTS_CALLBACK"),
    ("I already had it done at another hospital", "DONE_ELSEWHERE"),
    ("I need someone who speaks Urdu", "LANGUAGE"),
    ("I forgot", "OTHER"),
]

# Messages that must reach a clinician quickly. Some avoid the lexicon on purpose.
DISTRESS_TEXTS: list[str] = [
    "I saw blood in the toilet this morning",
    "There is black stool since yesterday and I feel dizzy",
    "I am terrified and can't sleep",
    "شفت دم مع البراز",
    "عندي نزيف من امس",
    "انا مرعوب وما اقدر انام",
    "I have severe pain in my belly",
    "My stomach hurts so much I can barely stand",  # no lexicon cue: expected miss for keyword-v1
]


@dataclass
class Delivery:
    at: datetime            # when the message reaches the system (may be late or repeated)
    kind: str               # fhir | ref | patient_text
    pid: str
    payload: Any
    key: str                # stable id of the underlying message (duplicates share it)


@dataclass
class Truth:
    pid: str
    scenario: str
    stopped_at: datetime | None          # None for clean cases
    truly_complete: bool                 # report received and outcome communicated by the horizon
    expected_reasons: set[str]
    has_fp: bool
    language: str
    distress_at: datetime | None = None
    distress_text: str | None = None
    barrier_text: str | None = None
    barrier_label: str | None = None
    appointment_at: datetime | None = None


@dataclass
class Cohort:
    seed: int
    base: datetime
    horizon: datetime
    patients: list[dict[str, Any]]
    deliveries: list[Delivery]
    truths: dict[str, Truth]
    config: dict[str, Any] = field(default_factory=dict)


def _u(rng: random.Random, lo: float, hi: float) -> timedelta:
    return timedelta(days=rng.uniform(lo, hi))


def _clean_times(rng: random.Random, start: datetime) -> dict[str, datetime]:
    """Step times inside every pathway deadline (invite ≤3 d, discuss ≤7, refer ≤3, accept ≤5, book ≤7,
    report ≤10, communicate <7 after report)."""
    t: dict[str, datetime] = {"FIT": start}
    t["INVITE"] = t["FIT"] + _u(rng, 0.2, 2.0)
    t["DISCUSS"] = t["INVITE"] + _u(rng, 1.0, 5.0)
    t["REFER"] = t["DISCUSS"] + _u(rng, 0.1, 2.0)
    t["ACCEPT"] = t["REFER"] + _u(rng, 0.5, 3.5)
    t["BOOK"] = t["ACCEPT"] + _u(rng, 0.5, 5.0)
    t["APPT"] = t["BOOK"] + _u(rng, 4.0, 20.0)
    t["REPORT"] = t["APPT"] + _u(rng, 1.0, 7.0)
    t["OUTCOME"] = t["REPORT"] + _u(rng, 0.5, 5.0)
    return t


ORDER = ["FIT", "INVITE", "DISCUSS", "REFER", "ACCEPT", "BOOK", "ATTEND", "PROC", "REPORT", "OUTCOME"]


def _messages(pid: str, t: dict[str, datetime], upto: str) -> list[tuple[datetime, str, Any, str]]:
    """Messages for each step up to and including `upto`: (time, kind, payload, key)."""
    m: dict[str, list[tuple[datetime, str, Any, str]]] = {
        "FIT": [(t["FIT"], "fhir", fit(pid, f"obs-{pid}", t["FIT"]), f"obs-{pid}")],
        "INVITE": [(t["INVITE"], "fhir", comm(pid, f"inv-{pid}", t["INVITE"], PURPOSE_INVITE), f"inv-{pid}")],
        "DISCUSS": [(t["DISCUSS"], "fhir", discussed(pid, f"enc-{pid}", t["DISCUSS"]), f"enc-{pid}")],
        "REFER": [(t["REFER"], "fhir", referral(pid, f"sr-{pid}", t["REFER"]), f"sr-{pid}"),
                  (t["REFER"], "ref", ref(pid, 1, t["REFER"], AdminStatus.SENT), f"ref1-{pid}")],
        "ACCEPT": [(t["ACCEPT"], "fhir", task(pid, f"task-{pid}", t["ACCEPT"], "accepted"), f"task-{pid}"),
                   (t["ACCEPT"], "ref", ref(pid, 2, t["ACCEPT"], AdminStatus.ACCEPTED), f"ref2-{pid}")],
        "BOOK": [(t["BOOK"], "fhir", appt(pid, f"ap-{pid}", t["BOOK"], "booked", t["APPT"]), f"ap1-{pid}"),
                 (t["BOOK"], "ref", ref(pid, 3, t["BOOK"], AdminStatus.SCHEDULED), f"ref3-{pid}")],
        "ATTEND": [(t["APPT"], "fhir", appt(pid, f"ap-{pid}", t["APPT"], "fulfilled", t["APPT"], version=2),
                    f"ap2-{pid}")],
        "PROC": [(t["APPT"], "fhir", procedure(pid, f"pr-{pid}", t["APPT"]), f"pr-{pid}")],
        "REPORT": [(t["REPORT"], "fhir", report(pid, f"dr-{pid}", t["REPORT"]), f"dr-{pid}"),
                   (t["REPORT"], "ref", ref(pid, 4, t["REPORT"], AdminStatus.COMPLETED), f"ref4-{pid}")],
        "OUTCOME": [(t["OUTCOME"], "fhir", comm(pid, f"out-{pid}", t["OUTCOME"], PURPOSE_OUTCOME), f"out-{pid}")],
    }
    out: list[tuple[datetime, str, Any, str]] = []
    for step in ORDER:
        out += m[step]
        if step == upto:
            break
    return out


def generate(n: int = 1000, seed: int = 2026, dup_rate: float = 0.10, late_rate: float = 0.05,
             late_max_hours: float = 36.0, no_fp_rate: float = 0.03,
             weights: dict[str, float] | None = None) -> Cohort:
    """`weights` overrides the design mix (scenario -> weight); missing scenarios get weight 0."""
    rng = random.Random(seed)
    horizon = BASE + timedelta(days=HORIZON_DAYS)
    names = list(SCENARIOS)
    if weights is not None:
        unknown = set(weights) - set(names)
        if unknown:
            raise ValueError(f"unknown scenarios: {sorted(unknown)}")
    weights_l = [SCENARIOS[s][0] for s in names] if weights is None else [weights.get(s, 0) for s in names]
    patients: list[dict[str, Any]] = []
    raw: list[tuple[datetime, str, str, Any, str]] = []  # (event time, kind, pid, payload, key)
    truths: dict[str, Truth] = {}

    for i in range(n):
        pid = f"p-b{i:05d}"
        scenario = rng.choices(names, weights_l)[0]
        lang = rng.choice(["en", "ar"])
        has_fp = rng.random() >= no_fp_rate
        patients.append({"id": pid, "display_name": f"Bench {i}", "preferred_language": lang,
                         "insurance_network": rng.choice(["thiqa", "daman-enhanced", "basic"]),
                         "family_physician_id": rng.choice(["dr-fatima", "dr-salma"]) if has_fp else None,
                         "birth_year": rng.randint(1956, 1981)})
        start = BASE + _u(rng, 0, 50 if scenario not in CLEAN else 55)
        t = _clean_times(rng, start)
        truth = Truth(pid=pid, scenario=scenario, stopped_at=None, truly_complete=False,
                      expected_reasons=SCENARIOS[scenario][1], has_fp=has_fp, language=lang)
        msgs: list[tuple[datetime, str, Any, str]]

        if scenario in ("CLEAN_COMPLETE", "DISTRESS"):
            msgs = _messages(pid, t, "OUTCOME")
            truth.truly_complete = True
            truth.appointment_at = t["APPT"]
            if scenario == "DISTRESS":
                at = t["BOOK"] + (t["APPT"] - t["BOOK"]) * rng.uniform(0.2, 0.8)
                truth.distress_at, truth.distress_text = at, rng.choice(DISTRESS_TEXTS)
                truth.stopped_at = at
                msgs.append((at, "patient_text", truth.distress_text, f"txt-{pid}"))
        elif scenario == "CLEAN_IN_PROGRESS":
            start = horizon - _u(rng, 18, 24)
            t = _clean_times(rng, start)
            t["APPT"] = horizon + _u(rng, 2, 10)
            msgs = _messages(pid, t, "BOOK")
            truth.appointment_at = t["APPT"]
        elif scenario == "NEVER_INVITED":
            msgs, truth.stopped_at = _messages(pid, t, "FIT"), t["FIT"]
        elif scenario == "NOT_DISCUSSED":
            msgs, truth.stopped_at = _messages(pid, t, "INVITE"), t["INVITE"]
        elif scenario == "NOT_REFERRED":
            msgs, truth.stopped_at = _messages(pid, t, "DISCUSS"), t["DISCUSS"]
        elif scenario == "REFERRAL_REJECTED":
            msgs = _messages(pid, t, "REFER")
            at = t["REFER"] + _u(rng, 1, 4)
            msgs += [(at, "fhir", task(pid, f"task-{pid}", at, "rejected", "Incomplete referral"), f"task-{pid}"),
                     (at, "ref", ref(pid, 2, at, AdminStatus.CANCELLED), f"ref2-{pid}")]
            truth.stopped_at = at
        elif scenario == "NOT_BOOKED":
            msgs, truth.stopped_at = _messages(pid, t, "ACCEPT"), t["ACCEPT"]
        elif scenario == "NO_SHOW":
            msgs = _messages(pid, t, "BOOK")
            truth.stopped_at = truth.appointment_at = t["APPT"]
            if rng.random() < 0.5:  # half get an explicit no-show record; half are silent
                msgs.append((t["APPT"], "fhir", appt(pid, f"ap-{pid}", t["APPT"], "noshow", t["APPT"], version=2),
                             f"ap2-{pid}"))
            if rng.random() < 0.6:  # the patient replies with a reason
                text, label = rng.choice(BARRIER_TEXTS)
                at = t["APPT"] + _u(rng, 0.5, 3)
                truth.barrier_text, truth.barrier_label = text, label
                msgs.append((at, "patient_text", text, f"txt-{pid}"))
        elif scenario == "NO_PROCEDURE":
            msgs, truth.stopped_at = _messages(pid, t, "ATTEND"), t["APPT"]
        elif scenario == "FALSE_DONE":
            msgs = _messages(pid, t, "ATTEND")
            at = t["APPT"] + _u(rng, 0, 3)
            msgs.append((at, "ref", ref(pid, 4, at, AdminStatus.COMPLETED), f"ref4-{pid}"))
            truth.stopped_at = t["APPT"]
        elif scenario == "REPORT_NOT_COMMUNICATED":
            msgs, truth.stopped_at = _messages(pid, t, "REPORT"), t["REPORT"]
        else:  # pragma: no cover
            raise ValueError(scenario)

        truths[pid] = truth
        raw += [(at, kind, pid, payload, key) for at, kind, payload, key in msgs]

    # Delivery noise, identical for every arm: late arrival and repeated delivery.
    deliveries: list[Delivery] = []
    for at, kind, pid, payload, key in raw:
        arrive = at
        if kind != "patient_text" and rng.random() < late_rate:
            arrive = at + timedelta(hours=rng.uniform(1, late_max_hours))
        deliveries.append(Delivery(arrive, kind, pid, payload, key))
        if kind != "patient_text" and rng.random() < dup_rate:
            deliveries.append(Delivery(arrive + timedelta(hours=rng.uniform(0.1, 48)), kind, pid, payload, key))
    deliveries = [d for d in deliveries if d.at <= horizon]
    deliveries.sort(key=lambda d: (d.at, d.key))
    return Cohort(seed=seed, base=BASE, horizon=horizon, patients=patients, deliveries=deliveries, truths=truths,
                  config={"n": n, "dup_rate": dup_rate, "late_rate": late_rate, "late_max_hours": late_max_hours,
                          "no_fp_rate": no_fp_rate, "horizon_days": HORIZON_DAYS,
                          "weights": dict(zip(names, weights_l, strict=True))})

# ruff: noqa: E501  (markdown report text)
"""Three-arm benchmark: python -m tasleem.bench [--n 1000] [--seeds 2026,2027,2028]

Writes docs/evidence/benchmark.md, benchmark_cases.csv (seed 1) and benchmark.png.
"""

from __future__ import annotations

import argparse
import csv
import time
from pathlib import Path

from .arms import run_reminders, run_status_only, run_tasleem
from .cohort import SCENARIOS, generate
from .score import per_case, summarize

EVIDENCE = Path(__file__).resolve().parents[3] / "docs" / "evidence"
LABELS = {
    "NEVER_INVITED": "Never invited to discuss result",
    "NOT_DISCUSSED": "Invited, result never discussed",
    "NOT_REFERRED": "Discussed, never referred",
    "REFERRAL_REJECTED": "Referral rejected by GI centre",
    "NOT_BOOKED": "Accepted, never booked",
    "NO_SHOW": "Booked, did not attend",
    "NO_PROCEDURE": "Seen, colonoscopy never done",
    "FALSE_DONE": "Status says completed, no colonoscopy or report",
    "REPORT_NOT_COMMUNICATED": "Report back, patient never told",
    "DISTRESS": "Red-flag or distress message (must reach a clinician in 24 h)",
}


def run_seed(n: int, seed: int) -> tuple[dict, list[dict], dict]:
    c = generate(n=n, seed=seed)
    out, rows_all, timing = {}, [], {}
    for fn in (run_reminders, run_status_only, run_tasleem):
        t0 = time.perf_counter()
        r = fn(c)
        timing[r.name] = round(time.perf_counter() - t0, 1)
        rows = per_case(c, r)
        out[r.name] = summarize(c, r, rows)
        rows_all += rows
    return out, rows_all, {"timing_s": timing, "deliveries": len(c.deliveries), "config": c.config}


def _fmt(v, suffix=""):
    return "—" if v is None else f"{v}{suffix}"


def _range(vals: list) -> str:
    vals = [v for v in vals if v is not None]
    if not vals:
        return "—"
    lo, hi = min(vals), max(vals)
    return f"{lo}" if lo == hi else f"{lo}–{hi}"


def chart(s: dict, path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    arms = list(s)
    scen = list(LABELS)
    names = [LABELS[k].split(" (")[0] for k in scen]
    colors = {"A": "#9aa5b1", "B": "#e0a43a", "C": "#1f6f8b"}
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6.4), dpi=160, sharey=True)
    h = 0.27
    for i, a in enumerate(arms):
        ys = [j + (i - 1) * h for j in range(len(scen))]
        ax1.barh(ys, [s[a]["by_scenario"][k]["detected_pct"] or 0 for k in scen], h, color=colors[a[0]], label=a)
        days = [s[a]["by_scenario"][k]["median_days"] for k in scen]
        ax2.barh(ys, [d or 0 for d in days], h, color=colors[a[0]])
        for y, d in zip(ys, days, strict=True):
            if a[0] != "A" and d is None:
                ax2.text(0.4, y, "never", va="center", fontsize=7, color=colors[a[0]])
    ax1.set_yticks(range(len(scen)))
    ax1.set_yticklabels(names, fontsize=9)
    ax1.invert_yaxis()
    ax1.set_xlim(0, 105)
    ax1.set_xlabel("Failures flagged to a named person (%)")
    ax2.set_xlabel("Median days from care stopping to the alert (shorter is better)")
    for ax in (ax1, ax2):
        ax.spines[["top", "right"]].set_visible(False)
    fig.suptitle("Same synthetic cohort, three ways of following up a positive FIT", y=0.985, fontsize=13)
    fig.legend(*ax1.get_legend_handles_labels(), loc="upper center", bbox_to_anchor=(0.5, 0.93), ncol=3,
               frameon=False, fontsize=10)
    fig.tight_layout(rect=(0, 0, 1, 0.88))
    fig.savefig(path)
    plt.close(fig)


def report(results: list[dict], meta: list[dict], n: int, seeds: list[int]) -> str:
    s = results[0]
    arms = list(s)
    A, B, C = arms

    def row(label: str, key, fmt=lambda v: _fmt(v)) -> str:
        cells = []
        for a in arms:
            v = key(s[a])
            rng = _range([key(r[a]) for r in results]) if len(results) > 1 else None
            cells.append(fmt(v) + (f" ({rng})" if rng and rng not in ("—", str(v)) else ""))
        return f"| {label} | " + " | ".join(cells) + " |"

    pct = lambda v: _fmt(v, "%")  # noqa: E731
    lines = [
        "# Three-arm benchmark",
        "",
        f"Run: `python -m tasleem.bench --n {n} --seeds {','.join(map(str, seeds))}`. "
        f"Synthetic cohort of {n:,} people with a positive FIT per seed, {meta[0]['deliveries']:,} delivered messages "
        f"(seed {seeds[0]}). Numbers are seed {seeds[0]}; brackets give the range across all {len(seeds)} seeds.",
        "",
        "**What it measures:** when care stops, does a named person find out, how fast, and is \"done\" really done.",
        "**What it does not measure:** whether patients then get care. That needs a clinical pilot.",
        "",
        "## Arms (same messages, same timing, same noise)",
        "| Arm | What it sees | What it does |",
        "|---|---|---|",
        "| A Reminders only | Appointment bookings | Reminds the patient 2 days before. Raises no staff alerts (status quo) |",
        "| B Malaffi status only | FIT results and referral statuses (SENT, ACCEPTED, SCHEDULED, COMPLETED, CANCELLED) | "
        "Daily rules, deliberately generous: no referral 14 days after FIT; referral cancelled; status unchanged 30 days. "
        "COMPLETED = done |",
        "| C Tasleem | The same feed plus clinical evidence (encounters, appointments, procedures, reports, communications) "
        "and patient replies | The real engine, real ingest path, daily scheduler |",
        "",
        "## Headline",
        f"| Measure | {A} | {B} | {C} |",
        "|---|---|---|---|",
        row("Failures flagged to a named person", lambda x: x["detected_pct"], pct),
        row("Median days from care stopping to alert", lambda x: x["median_days"]),
        row("90th percentile days to alert", lambda x: x["p90_days"]),
        row("Counted as done", lambda x: x["counted_done"]),
        row("…of which care was not complete (false done)", lambda x: x["false_done"]),
        row("Clean journeys that got a false alert", lambda x: x["false_alert_pct"], pct),
        row("Staff alerts per 100 patients", lambda x: x["alerts_per_100"]),
        row("Distress messages reaching a clinician within 24 h",
            lambda x: x["by_scenario"]["DISTRESS"]["detected_pct"], pct),
        "",
        f"Truly complete journeys (report received and patient told): {s[C]['truly_complete']}.",
        "",
        "Distress: the cohort draws from 8 messages; 7 contain a cue word and 1 (\"My stomach hurts so much I can "
        "barely stand\") deliberately does not. Every miss in the distress row is that message. Cue-bearing messages "
        "reached a clinician the same day in every case. The keyword detector is frozen for this run; the fix belongs "
        "in a new version tested on new, unseen messages, not in tuning to this set.",
        "",
        "## By failure type (detected %, median days to alert)",
        f"| Failure (n, seed {seeds[0]}) | {A} | {B} | {C} | Tasleem gave the right reason |",
        "|---|---|---|---|---|",
    ]
    for k, label in LABELS.items():
        cells = []
        for a in arms:
            b = s[a]["by_scenario"][k]
            cells.append(f"{_fmt(b['detected_pct'], '%')}, {_fmt(b['median_days'])} d")
        lines.append(f"| {label} ({s[C]['by_scenario'][k]['n']}) | " + " | ".join(cells)
                     + f" | {_fmt(s[C]['by_scenario'][k]['right_reason_pct'], '%')} |")
    bar = s[C].get("barrier", {})
    lines += [
        "",
        "## Tasleem-only checks",
        "| Check | Result |",
        "|---|---|",
        f"| Barrier suggestion for patient replies after a missed appointment (n = {bar.get('n')}) | "
        f"{bar.get('correct')} right, {bar.get('wrong')} wrong, {bar.get('abstained')} no suggestion. "
        "Every reply is shown to a human, who confirms the code (R5) |",
        f"| Patients with no family physician still given a named owner | {s[C].get('no_fp_owned')} of {s[C].get('no_fp_total')} |",
        f"| Open cases without an owner (R1) | {s[C]['open_without_owner']} |",
        f"| Messages that crashed ingest | {s[C]['ingest_errors']} |",
        "",
        "![Detection by failure type](benchmark.png)",
        "",
        "## How the cohort is built (tasleem/bench/cohort.py)",
        "- One scenario per person, drawn with fixed weights so every failure type is well represented. "
        "**The weights are not prevalence estimates**; read the per-failure table, not only the headline.",
        "- Steps that happen are timed with random delays inside the pathway deadlines.",
        f"- Delivery noise for every arm: {int(meta[0]['config']['dup_rate'] * 100)}% of messages delivered twice, "
        f"{int(meta[0]['config']['late_rate'] * 100)}% delivered up to {int(meta[0]['config']['late_max_hours'])} h late. "
        f"{int(meta[0]['config']['no_fp_rate'] * 100)}% of people have no family physician.",
        "- Ground truth is written before any arm runs. Latency is measured from the moment care actually stopped "
        "(the last real event, missed appointment, rejection or message), not from any arm's own deadline.",
        "- Half the no-shows have an explicit no-show record; half are silent. 60% of no-shows send a free-text reason "
        "(some deliberately without the classifier's cue words). One distress text has no cue words by design.",
        "",
        "## Limits, stated plainly",
        "- Synthetic data, written by the team. It shows the logic catches what it is designed to catch; it cannot show "
        "real-world prevalence or effect on outcomes.",
        "- Arm B's rules are our reconstruction of a sensible status-only monitor. A real deployment might use other "
        "thresholds; we picked generous ones.",
        "- Tasleem's deadlines are placeholders until the screening programme's clinical lead sets them, and its "
        "detection delay depends on them.",
        "- Tasleem sees more data than B. That is the point being tested: verified clinical evidence versus "
        "administrative status.",
        "",
        "Runtime (seed 1): " + ", ".join(f"{k} {v} s" for k, v in meta[0]["timing_s"].items()) + ".",
        "Per-case results for seed 1: [benchmark_cases.csv](benchmark_cases.csv).",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--seeds", default="2026,2027,2028")
    ap.add_argument("--out", default=str(EVIDENCE))
    a = ap.parse_args(argv)
    seeds = [int(x) for x in a.seeds.split(",")]
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    results, metas = [], []
    for i, seed in enumerate(seeds):
        s, rows, meta = run_seed(a.n, seed)
        results.append(s)
        metas.append(meta)
        print(seed, {k: (v["detected_pct"], v["false_alert_pct"], v["false_done"]) for k, v in s.items()},
              meta["timing_s"], flush=True)
        if i == 0:
            with (out / "benchmark_cases.csv").open("w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=list(rows[0]))
                w.writeheader()
                w.writerows(rows)
            chart(s, out / "benchmark.png")
    (out / "benchmark.md").write_text(report(results, metas, a.n, seeds), encoding="utf-8")
    assert set(SCENARIOS) >= set(LABELS)


if __name__ == "__main__":
    main()

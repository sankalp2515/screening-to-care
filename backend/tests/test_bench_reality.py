"""Real-world-fit analysis (tasleem.bench.reality): the calibrated cohort, the tightened baselines, and the
safety invariants that must hold on any mix."""

import pytest

from tasleem.bench.arms import run_status_only
from tasleem.bench.cohort import SCENARIOS, generate
from tasleem.bench.reality import CALIBRATED, CARE_FAILURES, report, run_seed


def test_calibrated_mix_matches_the_published_failure_share():
    assert set(CALIBRATED) == set(SCENARIOS)
    assert sum(CALIBRATED.values()) == 1000
    # Martin et al. 2017: 42.3% had no colonoscopy within a year.
    assert sum(CALIBRATED[k] for k in CARE_FAILURES) == 423


def test_weights_override_and_reject_unknown_scenarios():
    c = generate(n=200, seed=7, weights={"CLEAN_COMPLETE": 1, "NO_SHOW": 1})
    assert {t.scenario for t in c.truths.values()} <= {"CLEAN_COMPLETE", "NO_SHOW"}
    with pytest.raises(ValueError):
        generate(n=10, seed=7, weights={"NOT_A_SCENARIO": 1})


def test_default_cohort_is_unchanged_by_the_weights_parameter():
    a, b = generate(n=150, seed=11), generate(n=150, seed=11, weights={k: v[0] for k, v in SCENARIOS.items()})
    assert [t.scenario for t in a.truths.values()] == [t.scenario for t in b.truths.values()]


def test_tighter_repeating_baseline_alerts_more_but_still_misses_false_done():
    c = generate(n=300, seed=5, weights=CALIBRATED)
    generous = run_status_only(c)
    tight = run_status_only(c, 3, 7, "tight", repeat=True)
    count = lambda r: sum(len(v) for v in r.alerts.values())  # noqa: E731
    assert count(tight) > count(generous)
    false_done = [p for p, t in c.truths.items() if t.scenario == "FALSE_DONE"]
    assert false_done and all(tight.believed_done[p] for p in false_done)  # status says COMPLETED: blind


def test_tasleem_keeps_its_invariants_on_the_realistic_mix():
    res = run_seed(80, 3)
    c = res["arms"]["C"]
    assert c["false_done"] == 0          # R3: nothing counted done without evidence
    assert c["open_without_owner"] == 0  # R1
    assert c["false_alert_pct"] == 0.0
    md = report([res], 80, [3])
    assert "Real-world fit" in md and "Assumption" in md


def test_distress_without_a_family_physician_still_reaches_a_clinician():
    """Found by the real-world-fit run: with no family physician, a distress message went to the programme
    coordinator, who is not a clinician and cannot resolve it. It must go to a named clinician."""
    from tasleem.bench.arms import run_tasleem

    c = generate(n=4, seed=21, weights={"DISTRESS": 1}, no_fp_rate=1.0)
    r = run_tasleem(c)
    for pid, t in c.truths.items():
        if t.distress_text and "barely stand" in t.distress_text:
            continue  # the deliberate no-cue message: a known keyword miss, tracked in the benchmark
        alerts = [a for a in r.alerts[pid] if a.reason == "DISTRESS"]
        assert alerts and alerts[0].to_id.startswith("dr-"), (pid, alerts)
        assert pid in r.distress_to_clinician

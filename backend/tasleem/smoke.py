# ruff: noqa: E501
"""End-to-end smoke test against a running deployment (Postgres or SQLite), over plain HTTP.

    python -m tasleem.smoke --base http://localhost:8000 [--key INTEGRATION_KEY]
    python -m tasleem.smoke --stack            # also the notifier, agent and HL7 connector (docker compose)

Walks the real user workflow: a judge-style demo of the false-done failure, the people who must act, the
messages that go out, the safety rules refusing unsafe actions, a concurrent-write race, and the audit chain.
Exits non-zero on the first failed check. Demo mode must be on (it uses guest personas and scenarios).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from typing import Any


class Client:
    def __init__(self, base: str, key: str | None) -> None:
        self.base = base.rstrip("/")
        self.key = key

    def call(self, method: str, path: str, who: str | None = None, body: Any = None,
             extra: dict[str, str] | None = None, raw: str | None = None) -> tuple[int, Any]:
        headers = {"Content-Type": "application/json", **(extra or {})}
        if who:
            headers["X-Demo-User"] = who
        if self.key:
            headers["X-Integration-Key"] = self.key
        data = raw.encode() if raw is not None else (json.dumps(body).encode() if body is not None else None)
        if raw is not None:
            headers["Content-Type"] = "application/hl7-v2"
        req = urllib.request.Request(self.base + path, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status, _decode(r.read())
        except urllib.error.HTTPError as e:
            return e.code, _decode(e.read())


def _decode(b: bytes) -> Any:
    try:
        return json.loads(b or b"null")
    except ValueError:
        return b.decode("utf-8", "replace")


CHECKS: list[tuple[str, bool]] = []


def check(name: str, ok: bool, detail: Any = "") -> None:
    CHECKS.append((name, ok))
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  -> {detail}"), flush=True)
    if not ok:
        sys.exit(1)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8000")
    ap.add_argument("--key", default=None)
    ap.add_argument("--stack", action="store_true", help="also check notifier :8010, agent :8020, connector :8030")
    ap.add_argument("--notifier", default="http://localhost:8010")
    ap.add_argument("--agent", default="http://localhost:8020")
    ap.add_argument("--connector", default="http://localhost:8030")
    ap.add_argument("--ops-key", default="local-ops-key")
    a = ap.parse_args(argv)
    c = Client(a.base, a.key)
    t0 = time.perf_counter()

    s, b = c.call("GET", "/readyz")
    check("database ready", s == 200, b)

    # 1. Live failure: Malaffi says COMPLETED, no colonoscopy.
    s, fd = c.call("POST", "/v1/demo/scenarios/false-done", body={})
    check("false-done scenario runs", s == 200, fd)
    case = fd["case"]
    cid = case["id"]
    check("stall flagged on evidence, not status", [x["reason"] for x in case["stalls"]] == ["CLOSED_WITHOUT_EVIDENCE"], case["stalls"])
    check("case has a named owner (R1)", bool(case["owner"]["id"]), case["owner"])
    check("owner told by EMR inbox task", any(n["channel"] == "emr_inbox" and n["recipient"] == case["owner"]["id"] for n in case["notifications"]), case["notifications"])

    # 2. The owner's inbox shows it, with the reason.
    s, work = c.call("GET", "/v1/me/work", who=case["owner"]["id"])
    esc = next(x for x in work["sections"] if x["kind"] == "escalated")
    check("owner's inbox lists the stalled case", any(i["id"] == cid for i in esc["items"]), esc)

    # 3. Safety: cannot close as completed without the report (R3), navigator cannot sign (R5).
    s, d = c.call("GET", f"/v1/cases/{cid}", who=case["owner"]["id"])
    hint = {x["outcome"]: x for x in d["actions"]["close"]}["COMPLETED_WITH_REPORT"]
    check("UI hint says closure blocked", hint["allowed"] is False and hint["code"] == "R3_EVIDENCE_REQUIRED", hint)
    s, r = c.call("POST", f"/v1/cases/{cid}/close", who=case["owner"]["id"], body={"outcome": "COMPLETED_WITH_REPORT"})
    check("engine refuses the same closure", s == 409 and r["error"]["code"] == "R3_EVIDENCE_REQUIRED", r)

    # 4. Org scoping: another clinic's physician cannot see it.
    s, r = c.call("GET", f"/v1/cases/{cid}", who="dr-salma")
    check("other clinic gets 404 (no existence leak)", s == 404, r)

    # 5. Evidence arrives; stall clears; closure now allowed and succeeds.
    s, ra = c.call("POST", "/v1/demo/scenarios/report-arrives", body={"case_id": cid})
    check("report clears the stall", all(x["reason"] != "CLOSED_WITHOUT_EVIDENCE" for x in ra["case"]["stalls"]), ra["case"]["stalls"])

    # 6. Concurrency: 8 simultaneous contact logs on one case all land, versions stay consistent.
    def log(_: int) -> int:
        return c.call("POST", f"/v1/cases/{cid}/contact-attempts", who="nav-aisha", body={"channel": "phone", "result": "reached"})[0]
    with ThreadPoolExecutor(8) as pool:
        codes = list(pool.map(log, range(8)))
    s, d = c.call("GET", f"/v1/cases/{cid}", who=case["owner"]["id"])
    ok = sum(1 for x in codes if x == 200)
    check("concurrent writes: none lost, conflicts reported as 409", d["contact_attempts"] == ok and all(x in (200, 409) for x in codes), codes)

    # 7. Distress reaches a clinician immediately and blocks closure.
    s, ds = c.call("POST", "/v1/demo/scenarios/distress-message", body={})
    dcase = ds["case"]
    check("distress routed to a clinician now", bool(dcase["distress"]) and dcase["next_step"]["reason"] == "DISTRESS", dcase["next_step"])
    check("urgent EMR alert queued", any(n["template"] == "distress_alert" and n["urgent"] for n in dcase["notifications"]), dcase["notifications"])

    # 8. Second disease by configuration.
    s, bp = c.call("POST", "/v1/demo/scenarios/raised-blood-pressure", body={})
    check("hypertension pathway opens a case", bp["case"]["pathway"]["id"] == "hypertension-screening", bp["case"]["pathway"])

    # 9. Outbox delivery: pull, ack, gone. (In the full stack the notifier owns the outbox: see below.)
    if not a.stack:
        s, ob = c.call("GET", "/v1/integration/outbox?limit=50")
        check("integration worker can pull the outbox", s == 200 and ob["items"], ob)
        ids = [m["id"] for m in ob["items"][:10]]
        s, ack = c.call("POST", "/v1/integration/outbox/ack", body={"ids": ids})
        check("acknowledged messages are not redelivered", ack["acknowledged"] == len(ids), ack)
    else:
        stack_checks(a, c, cid)

    # 10. Audit chain intact on every touched case.
    for x in (cid, dcase["id"], bp["case"]["id"]):
        s, au = c.call("GET", f"/v1/cases/{x}/audit", who="coord-sara")
        check(f"audit chain verifies ({x})", au["verification"]["ok"] is True, au["verification"])

    # 11. Programme view.
    s, m = c.call("GET", "/v1/program/metrics", who="coord-sara")
    check("metrics count false-done and owners", m["open_cases_without_owner"] == 0 and m["false_done"]["count"] >= 1, m)

    print(f"\n{len(CHECKS)} checks passed in {time.perf_counter() - t0:.1f} s against {a.base}")


def stack_checks(a: argparse.Namespace, c: Client, false_done_id: str) -> None:
    """The satellite services, each reached over HTTP exactly as in production."""
    n, ag, hl = Client(a.notifier, None), Client(a.agent, None), Client(a.connector, None)
    ops = {"X-Ops-Key": a.ops_key}
    for name, cl in (("notifier", n), ("agent", ag), ("connector", hl)):
        s, b = cl.call("GET", "/healthz")
        check(f"{name} is up", s == 200, b)

    # HL7 v2 from a lab: positive FIT for a demo patient, sent twice (idempotent), through the connector.
    s, sc = c.call("POST", "/v1/demo/scenarios/new-positive-fit", body={})
    pid = sc["patient_id"]
    ctrl = f"SMOKE-{int(time.time())}"
    msg = "\r".join([f"MSH|^~\\&|LAB|SKMC|MALAFFI|DOH|20261117090000||ORU^R01|{ctrl}|P|2.5.1", f"PID|1||{pid}",
                     "OBX|1|ST|29771-3^FIT^LN||Positive|||A|||F|||20261117090000"])
    s1, ack1 = hl.call("POST", "/v1/hl7", raw=msg)
    s2, ack2 = hl.call("POST", "/v1/hl7", raw=msg)
    check("connector accepts HL7 ORU and ACKs AA (twice, idempotent)", s1 == s2 == 200 and "MSA|AA" in ack1
          and "MSA|AA" in ack2, (s1, ack1, s2, ack2))
    s, bad = hl.call("POST", "/v1/hl7", raw="not hl7")
    check("connector rejects garbage with AR", s == 422 and "MSA|AR" in bad, bad)

    # Channels: an unreachable patient comes back as a navigator call task.
    s, un = c.call("POST", "/v1/demo/scenarios/unreachable-patient", body={})
    # Routine patient messages wait out quiet hours (21:00-08:00 Abu Dhabi). Run the cycle at the next
    # 10:00 local using the notifier's demo time travel, so the check works at any hour.
    from datetime import UTC, datetime, timedelta

    day = datetime.now(UTC).replace(hour=6, minute=0, second=0, microsecond=0)
    if day <= datetime.now(UTC):
        day += timedelta(days=1)
    cycle = {"now": day.isoformat()}
    s, run = n.call("POST", "/v1/run-once", body=cycle, extra=ops)
    check("notifier runs a delivery cycle", s == 200, run)
    d: dict = {}
    for _ in range(10):  # the notifier's own loop may take the messages first; give it a moment
        s, d = c.call("GET", f"/v1/cases/{un['case_id']}", who="nav-aisha")
        if (d.get("next_step") or {}).get("reason") == "PATIENT_NOT_REACHED":
            break
        n.call("POST", "/v1/run-once", body=cycle, extra=ops)
        time.sleep(1)
    check("patient unreachable by Sahatna and SMS -> navigator call task",
          (d.get("next_step") or {}).get("reason") == "PATIENT_NOT_REACHED", d.get("next_step"))
    s, trail = n.call("GET", f"/v1/notifications?case_id={false_done_id}", extra=ops)
    check("stall alert delivered to the owner's EMR inbox", s == 200 and any(
        x["recipient_id"] == "dr-fatima" and any(dl["channel"] == "emr_task" for dl in x["deliveries"])
        for x in trail["items"]), trail)
    s, pol = n.call("GET", "/v1/policy")
    check("channel policy published per kind of user", {r["recipient"] for r in pol["recipients"]} >= {
        "patient", "family_physician", "navigator", "program_coordinator"}, pol)

    # Agent: grounded brief, org scoping, and a draft that a person sends.
    s, asst = ag.call("GET", f"/v1/cases/{false_done_id}/assist", who="dr-fatima")
    check("agent brief is grounded; the decision stays with the rules", s == 200 and any(
        f["id"] == "gap" for f in asst["sense"]) and asst["decide"]["next_step"]["provenance"] == "computed", asst)
    s, other = ag.call("GET", f"/v1/cases/{false_done_id}/assist", who="dr-salma")
    check("agent respects org scoping (404 for another clinic)", s == 404, other)
    s, mc = c.call("POST", "/v1/demo/scenarios/missed-colonoscopy", body={})
    s, dr = ag.call("POST", f"/v1/cases/{mc['case_id']}/outreach-draft", who="nav-aisha", body={})
    check("agent drafts a policy-checked patient message", s == 200 and bool(dr.get("draft")), dr)
    s, sent = c.call("POST", dr["send_with"]["path"], who="nav-aisha", body=dr["send_with"]["body"])
    check("a person sends the draft; the event records the draft id", s == 200 and any(
        e["type"] == "PATIENT_MESSAGE_SENT" and e["payload"]["ai_draft_id"] == dr["draft_id"]
        for e in sent["timeline"]), sent)
    s, ref = c.call("POST", f"/v1/cases/{mc['case_id']}/patient-messages", who="nav-aisha",
                    body={"text": "Your result is positive", "language": "en"})
    check("message policy refuses result disclosure", s == 409 and ref["error"]["code"] == "IFHAS_MESSAGE_POLICY", ref)


if __name__ == "__main__":
    main()

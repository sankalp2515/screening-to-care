"""Record a complete, self-consistent demo bundle from a running Tasleem stack (synthetic data only).

    python -m tasleem.demo_bundle --out ../frontend/demo/demo-bundle.json

The frontend's demo mode replays this file, so reviewers can click through the real product behaviour
with no backend deployed. Every response is what the real services returned; nothing is hand-written.
Relative times in the UI must be computed against `meta.generated_at` (the bundle's clock), not today.

The script resets the demo data before and after recording.
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

CORE, NOTIF, AGENT, CONN = (f"http://localhost:{p}" for p in (8000, 8010, 8020, 8030))
OPS = {"X-Ops-Key": "local-ops-key"}


class Recorder:
    def __init__(self) -> None:
        self.commands: list[dict[str, Any]] = []

    def call(self, base: str, method: str, path: str, who: str | None = None, body: Any = None,
             extra: dict[str, str] | None = None, raw: str | None = None, pause: float = 0.05) -> tuple[int, Any]:
        h = {"Content-Type": "application/hl7-v2" if raw is not None else "application/json", **(extra or {})}
        if who:
            h["X-Demo-User"] = who
        data = raw.encode() if raw is not None else (json.dumps(body).encode() if body is not None else None)
        req = urllib.request.Request(base + path, data=data, headers=h, method=method)
        for attempt in range(5):
            try:
                with urllib.request.urlopen(req, timeout=30) as r:
                    status, b = r.status, r.read()
                break
            except urllib.error.HTTPError as e:
                if e.code == 429 and attempt < 4:
                    time.sleep(float(e.headers.get("Retry-After", "1")) + 0.2)
                    continue
                status, b = e.code, e.read()
                break
        time.sleep(pause)
        try:
            return status, json.loads(b)
        except ValueError:
            return status, b.decode()

    def get(self, base: str, path: str, who: str | None = None, **kw: Any) -> Any:
        return self.call(base, "GET", path, who, **kw)[1]

    def command(self, label: str, service: str, method: str, path: str, who: str | None, body: Any = None,
                case_id: str | None = None, **kw: Any) -> Any:
        base = {"core": CORE, "agent": AGENT, "notifier": NOTIF, "connector": CONN}[service]
        status, resp = self.call(base, method, path, who, body, **kw)
        self.commands.append({"label": label, "service": service, "method": method, "path": path, "persona": who,
                              "case_id": case_id, "body": body, "status": status, "response": resp})
        print(f"  {status} {label}")
        return resp


def next_0600_utc() -> str:
    day = datetime.now(UTC).replace(hour=6, minute=0, second=0, microsecond=0)
    return (day if day > datetime.now(UTC) else day + timedelta(days=1)).isoformat()


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="../frontend/demo/demo-bundle.json")
    args = ap.parse_args(argv)
    r = Recorder()
    r.call(CORE, "POST", "/v1/admin/reset-demo")
    generated_at = datetime.now(UTC).isoformat()

    people = r.get(CORE, "/v1/directory/people")
    staff = [p["id"] for p in people["staff"]]
    patients = [p["id"] for p in people["patients"]]
    print("snapshot: personas")
    me = {pid: r.get(CORE, "/v1/me", pid) for pid in staff + patients}
    work = {pid: r.get(CORE, "/v1/me/work", pid) for pid in staff}
    lists = {pid: r.get(CORE, "/v1/cases?status=all&limit=200", pid) for pid in staff}
    patient_cases = {pid: {lang: r.get(CORE, f"/v1/me/cases?lang={lang}", pid) for lang in ("en", "ar")}
                     for pid in patients}
    prep: dict[str, Any] = {}
    for pid, by_lang in patient_cases.items():
        for item in by_lang["en"].get("items", []):
            status, body = r.call(CORE, "GET", f"/v1/me/cases/{item['case_id']}/prep-check", pid)
            if status == 200:
                prep[item["case_id"]] = {"persona": pid, "response": body}

    print("snapshot: cases")
    all_cases = lists["coord-sara"]["items"]
    cases: dict[str, Any] = {}
    for c in all_cases:
        cid = c["id"]
        viewers = [pid for pid in staff if any(i["id"] == cid for i in lists[pid]["items"])]
        cases[cid] = {
            "detail_by_persona": {pid: r.get(CORE, f"/v1/cases/{cid}", pid) for pid in viewers},
            "audit": r.get(CORE, f"/v1/cases/{cid}/audit", "coord-sara"),
            "referral_options": r.get(CORE, f"/v1/cases/{cid}/referral-options", "coord-sara"),
            "trail": r.get(NOTIF, f"/v1/notifications?case_id={cid}", extra=OPS),
            "assist_by_persona": {},
        }
        owner = c["owner"]["id"]
        for pid in dict.fromkeys([owner, "coord-sara", "nav-aisha"]):
            if pid in viewers:
                cases[cid]["assist_by_persona"][pid] = r.get(AGENT, f"/v1/cases/{cid}/assist", pid, pause=0.6)

    print("snapshot: programme")
    month = f"{datetime.now(UTC):%Y-%m}"
    programme = {
        "metrics": r.get(CORE, "/v1/program/metrics", "coord-sara"),
        "metrics_by_filter": {
            f"org={o}": r.get(CORE, f"/v1/program/metrics?org={o}", "coord-sara") for o in ("org-ghaf", "org-samar")
        } | {f"language={lang}": r.get(CORE, f"/v1/program/metrics?language={lang}", "coord-sara")
             for lang in ("ar", "en")},
        "usage": r.get(CORE, f"/v1/program/usage?month={month}", "coord-sara"),
        "channels": r.get(NOTIF, "/v1/policy"),
    }
    scenarios_list = r.get(CORE, "/v1/demo/scenarios")

    print("commands on seeded cases")
    by_patient = {c["patient"]["id"]: c for c in all_cases}

    def detail(pid_patient: str, who: str) -> dict[str, Any]:
        return r.get(CORE, f"/v1/cases/{by_patient[pid_patient]['id']}", who)

    r.command("policy check ok", "core", "POST", "/v1/policy/patient-message-check", "nav-aisha",
              {"text": "Please call the clinic to rebook your appointment."})
    r.command("policy check blocks a result", "core", "POST", "/v1/policy/patient-message-check", "nav-aisha",
              {"text": "Your FIT result was 9.2 and positive."})

    raj = by_patient["p-rajesh"]["id"]
    r.command("close without evidence is refused (R3)", "core", "POST", f"/v1/cases/{raj}/close", "dr-fatima",
              {"outcome": "COMPLETED_WITH_REPORT"}, case_id=raj)
    r.command("log contact attempt", "core", "POST", f"/v1/cases/{raj}/contact-attempts", "dr-fatima",
              {"channel": "phone", "result": "no_answer"}, case_id=raj)
    r.command("request e-consult", "core", "POST", f"/v1/cases/{raj}/consults", "dr-fatima",
              {"to": "dr-omar", "question": "Referral shows completed but no report. Was the colonoscopy done?"},
              case_id=raj)
    after = detail("p-rajesh", "dr-omar")
    open_consult = next((c for c in after.get("consults", []) if not c.get("answer")), None)
    if open_consult:
        r.command("specialist answers e-consult", "core", "POST",
                  f"/v1/cases/{raj}/consults/{open_consult['id']}/answer", "dr-omar",
                  {"answer": "Not done here. The booking was cancelled by the patient; please re-refer."}, case_id=raj)

    nou = by_patient["p-noura"]["id"]
    noura = detail("p-noura", "nav-aisha")
    for b in noura.get("barriers", []):
        if not b.get("confirmed_code"):
            r.command("navigator confirms barrier", "core", "POST", f"/v1/cases/{nou}/barriers/{b['id']}/confirm",
                      "nav-aisha", {"code": b.get("suggested_code") or "FEAR"}, case_id=nou)
            break
    draft = r.command("assistant drafts outreach", "agent", "POST", f"/v1/cases/{nou}/outreach-draft", "nav-aisha",
                      {}, case_id=nou)
    if isinstance(draft, dict) and draft.get("send_with"):
        r.command("navigator sends the draft", "core", "POST", draft["send_with"]["path"], "nav-aisha",
                  draft["send_with"]["body"], case_id=nou)
    r.command("message with a result is refused", "core", "POST", f"/v1/cases/{nou}/patient-messages", "nav-aisha",
              {"text": "Your result is positive", "language": "en"}, case_id=nou)

    sun = by_patient["p-sunita"]["id"]
    sunita = detail("p-sunita", "dr-salma")
    for d in sunita.get("distress", []):
        if not d.get("resolved"):
            r.command("non-clinician cannot clear distress", "core", "POST",
                      f"/v1/cases/{sun}/distress/{d['id']}/resolve", "coord-sara",
                      {"note": "Called"}, case_id=sun)
            r.command("clinician records distress response", "core", "POST",
                      f"/v1/cases/{sun}/distress/{d['id']}/resolve", "dr-salma",
                      {"note": "Called the patient the same hour; bleeding assessed; urgent slot booked."}, case_id=sun)
            break
    r.command("distress patient draft is withheld", "agent", "POST", f"/v1/cases/{sun}/outreach-draft", "dr-salma",
              {}, case_id=sun)

    if "p-fatma" in by_patient:
        fat = by_patient["p-fatma"]["id"]
        r.command("receiver accepts handoff", "core", "POST", f"/v1/cases/{fat}/handoff/accept", "dr-salma", {},
                  case_id=fat)

    if "p-leila" in by_patient:
        lei = by_patient["p-leila"]["id"]
        leila = detail("p-leila", "dr-salma")
        for opt in leila.get("actions", {}).get("close", []):
            if opt.get("allowed"):
                body: dict[str, Any] = {"outcome": opt["outcome"]}
                if "evidence_ref" in opt.get("requires", []):
                    body["evidence_ref"] = next((s["evidence_ref"] for s in reversed(leila.get("stages", []))
                                                 if s.get("evidence_ref")), "DiagnosticReport/demo")
                if "reason" in opt.get("requires", []):
                    body["reason"] = "Report reviewed and discussed with the patient."
                r.command("close with evidence", "core", "POST", f"/v1/cases/{lei}/close", "dr-salma", body,
                          case_id=lei)
                break

    for pid in ("p-noura",):
        items = patient_cases[pid]["en"].get("items", [])
        if items:
            ccid = items[0]["case_id"]
            r.command("patient gives consent", "core", "POST", f"/v1/me/cases/{ccid}/consent", pid, {}, case_id=ccid)
            r.command("patient reports a barrier", "core", "POST", f"/v1/cases/{ccid}/barriers", pid,
                      {"codes": ["TRANSPORT"], "text": "I have no car that early in the morning."}, case_id=ccid)
    for ccid, p in prep.items():
        qs = p["response"].get("questions", [])
        answers = {q["id"]: q["options"][0]["id"] for q in qs if q.get("options")}
        r.command("patient answers preparation check", "core", "POST", f"/v1/me/cases/{ccid}/prep-check",
                  p["persona"], {"answers": answers}, case_id=ccid)
        break

    print("scenarios")
    runs: dict[str, Any] = {}
    last_false_done = None
    for s in scenarios_list["items"]:
        sid = s["id"]
        body: dict[str, Any] = {}
        if sid == "report-arrives":
            if not last_false_done:
                continue
            body = {"case_id": last_false_done}
        status, resp = r.call(CORE, "POST", f"/v1/demo/scenarios/{sid}", body=body)
        if status != 200 or not isinstance(resp, dict):
            runs[sid] = {"status": status, "response": resp}
            continue
        cid = resp.get("case_id")
        if sid == "false-done":
            last_false_done = cid
        owner = (resp.get("case") or {}).get("owner", {}).get("id")
        run: dict[str, Any] = {"status": status, "request": body, "response": resp}
        if cid and owner:
            run["case_as_owner"] = r.get(CORE, f"/v1/cases/{cid}", owner)
            run["owner_work_after"] = r.get(CORE, "/v1/me/work", owner)
            run["assist_as_owner"] = r.get(AGENT, f"/v1/cases/{cid}/assist", owner, pause=0.6)
        if sid == "unreachable-patient" and cid:
            run["notifier_run_once"] = r.get(NOTIF, "/v1/run-once", extra=OPS) if False else \
                r.call(NOTIF, "POST", "/v1/run-once", body={"now": next_0600_utc()}, extra=OPS)[1]
            run["case_after_notifier"] = r.get(CORE, f"/v1/cases/{cid}", "nav-aisha")
            run["trail_after_notifier"] = r.get(NOTIF, f"/v1/notifications?case_id={cid}", extra=OPS)
            run["navigator_work_after"] = r.get(CORE, "/v1/me/work", "nav-aisha")
        if sid == "new-positive-fit" and resp.get("patient_id"):
            hl7 = "\r".join(["MSH|^~\\&|LAB|SKMC|MALAFFI|DOH|20261117090000||ORU^R01|LAB-DEMO-0002|P|2.5.1",
                             f"PID|1||{resp['patient_id']}",
                             "OBX|1|ST|29771-3^FIT^LN||Positive|||A|||F|||20261117090000"])
            run["hl7_message"] = hl7.replace("\r", "\n")
            run["hl7_ack"] = r.call(CONN, "POST", "/v1/hl7", raw=hl7)[1].replace("\r", "\n")
            run["hl7_ack_garbage"] = r.call(CONN, "POST", "/v1/hl7", raw="not an hl7 message")[1].replace("\r", "\n")
        runs[sid] = run
        print(f"  {status} scenario {sid}")

    bundle = {
        "meta": {
            "generated_at": generated_at,
            "note": "Synthetic data only. Recorded from the real Tasleem services; nothing is hand-written.",
            "how_to_use": "Demo mode replays these responses. Compute relative times against generated_at.",
            "services": {"core": "8000", "notifier": "8010", "agent": "8020", "connector": "8030"},
        },
        "directory": people,
        "me": me,
        "work": work,
        "case_lists": lists,
        "cases": cases,
        "patient_cases": patient_cases,
        "prep_checks": prep,
        "programme": programme,
        "scenarios": {"list": scenarios_list, "runs": runs},
        "commands": r.commands,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(bundle, ensure_ascii=False, default=str), encoding="utf-8")
    r.call(CORE, "POST", "/v1/admin/reset-demo")
    print(f"wrote {out} ({out.stat().st_size // 1024} KB): {len(cases)} cases, {len(r.commands)} commands, "
          f"{len(runs)} scenario runs; demo reset")


if __name__ == "__main__":
    main()

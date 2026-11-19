// Tests for the demo replayer: the frontend must never show a rule outcome the backend would not.
/* eslint-disable @typescript-eslint/no-explicit-any */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { beforeEach, describe, expect, it } from "vitest";
import { bundle, demoRequest, demoSession, falseDoneCase, installBundle, messagePolicy, rememberFalseDone, resetDemo } from "../lib/demo";

const RAW = JSON.parse(readFileSync(resolve(__dirname, "../../demo/demo-bundle.json"), "utf-8"));
const RAJESH = "case_767b1946ee9e";
const SUNITA = "case_643f99b63ca1";
const NOURA = "case_02f77758731b";

beforeEach(() => installBundle(RAW));

describe("message policy (IFHAS: no results or advice by message)", () => {
  it("passes a plain invitation", () => {
    expect(messagePolicy("Please call the clinic to rebook your appointment.").ok).toBe(true);
  });
  it("blocks a result word", () => {
    const r = messagePolicy("Your result is positive");
    expect(r.ok).toBe(false);
    expect(r.violations.map((v) => v.code)).toContain("RESULT_DISCLOSURE");
  });
  it("blocks a result value, matching the recorded server answer", () => {
    const recorded = RAW.commands.find((c: any) => c.label === "policy check blocks a result");
    expect(messagePolicy(recorded.body.text)).toEqual(recorded.response);
  });
  it("blocks Arabic result words, advice and links", () => {
    expect(messagePolicy("الفحص إيجابي").violations[0].code).toBe("RESULT_DISCLOSURE");
    expect(messagePolicy("There is nothing to worry about").violations[0].code).toBe("CLINICAL_ADVICE");
    expect(messagePolicy("Your blood pressure was 150/95").violations[0].code).toBe("RESULT_VALUE");
    expect(messagePolicy("Your visit is at 9:30 on 21 Nov").ok).toBe(true);
    expect(messagePolicy("See www.example.org").violations[0].code).toBe("LINK");
    expect(messagePolicy("   ").violations[0].code).toBe("EMPTY");
  });
});

describe("R3: a case closes only on evidence or a signed decision", () => {
  it("refuses Rajesh's close as completed-with-report", () => {
    const r = demoRequest("core", "POST", `/v1/cases/${RAJESH}/close`, { outcome: "COMPLETED_WITH_REPORT" }, "dr-fatima");
    expect(r.status).toBe(409);
    expect(r.data.error.code).toBe("R3_EVIDENCE_REQUIRED");
  });
  it("refuses an allowed outcome when its required evidence is missing", () => {
    const r = demoRequest("core", "POST", `/v1/cases/${RAJESH}/close`, { outcome: "COMPLETED_ELSEWHERE" }, "dr-fatima");
    expect(r.status).toBe(422);
  });
  it("refuses unreachable without three contact attempts", () => {
    const r = demoRequest("core", "POST", `/v1/cases/${RAJESH}/close`, { outcome: "UNREACHABLE" }, "dr-fatima");
    expect(r.status).toBe(409);
    expect(r.data.error.code).toBe("R3_CONTACT_ATTEMPTS");
  });
  it("only a clinician clears a distress flag", () => {
    const path = `/v1/cases/${SUNITA}/distress/dis_12aad4fbe543/resolve`;
    const coord = demoRequest("core", "POST", path, { note: "Called" }, "coord-sara");
    expect(coord.status).toBe(409);
    expect(coord.data.error.code).toBe("R3_SIGNATURE_REQUIRED");
    const doc = demoRequest("core", "POST", path, { note: "Called the patient." }, "dr-salma");
    expect(doc.status).toBe(200);
    const after = demoRequest("core", "GET", `/v1/cases/${SUNITA}`, undefined, "dr-salma");
    expect(after.data.distress.every((d: any) => d.resolved)).toBe(true);
  });
});

describe("patient messages", () => {
  it("refuses a message with a result even where a send was recorded", () => {
    const r = demoRequest("core", "POST", `/v1/cases/${NOURA}/patient-messages`, { text: "Your result is positive", language: "en" }, "nav-aisha");
    expect(r.status).toBe(409);
    expect(r.data.error.code).toBe("IFHAS_MESSAGE_POLICY");
  });
});

describe("access and ownership", () => {
  it("hides a case outside the clinic", () => {
    expect(demoRequest("core", "GET", `/v1/cases/${RAJESH}`, undefined, "dr-lina").status).toBe(404);
  });
  it("R1: every listed open case has a named owner", () => {
    for (const [p, list] of Object.entries<any>(bundle().case_lists)) {
      for (const row of list.items.filter((r: any) => r.status === "open")) expect(row.owner?.id, `${p} ${row.id}`).toBeTruthy();
    }
  });
  it("filters the case list by stalled", () => {
    const r = demoRequest("core", "GET", "/v1/cases?stalled=true", undefined, "coord-sara");
    expect(r.data.items.length).toBeGreaterThan(0);
    expect(r.data.items.every((x: any) => x.stalls.length > 0)).toBe(true);
  });
});

describe("live simulator", () => {
  it("report-arrives needs the false-done case first, then clears the stall on evidence", () => {
    expect(demoRequest("core", "POST", "/v1/demo/scenarios/report-arrives", {}, "dr-fatima").status).toBe(409);
    const fd = demoRequest("core", "POST", "/v1/demo/scenarios/false-done", {}, "dr-fatima");
    expect(fd.status).toBe(200);
    expect(demoSession().falseDoneRun).toBe(true);
    const list = demoRequest("core", "GET", "/v1/cases", undefined, "dr-fatima").data.items;
    expect(list[0].id).toBe(fd.data.case_id);
    expect(list[0].stalls.map((s: any) => s.reason)).toContain("CLOSED_WITHOUT_EVIDENCE");
    expect(demoRequest("core", "POST", "/v1/demo/scenarios/report-arrives", {}, "dr-fatima").status).toBe(200);
    const c = demoRequest("core", "GET", `/v1/cases/${fd.data.case_id}`, undefined, "dr-fatima").data;
    expect(c.stalls.length).toBe(0);
  });
  it("the notifier does nothing until a patient is unreachable, then asks Aisha to call", () => {
    expect(demoRequest("notifier", "POST", "/v1/run-once", {}, "dr-fatima").data.pulled).toBe(0);
    const u = demoRequest("core", "POST", "/v1/demo/scenarios/unreachable-patient", {}, "dr-fatima");
    expect(demoRequest("notifier", "POST", "/v1/run-once", {}, "dr-fatima").data.pulled).toBe(1);
    const c = demoRequest("core", "GET", `/v1/cases/${u.data.case_id}`, undefined, "nav-aisha").data;
    expect(c.next_step.reason).toBe("PATIENT_NOT_REACHED");
    const trail = demoRequest("notifier", "GET", `/v1/notifications?case_id=${u.data.case_id}`, undefined, "nav-aisha").data;
    expect(trail.items.some((i: any) => i.status === "exhausted")).toBe(true);
  });
  it("HL7: accepts a lab result and rejects garbage", () => {
    const msg = RAW.scenarios.runs["new-positive-fit"].hl7_message;
    expect(demoRequest("connector", "POST", "/v1/hl7", msg, "dr-fatima").data).toContain("MSA|AA");
    expect(demoRequest("connector", "POST", "/v1/hl7", "not an hl7 message", "dr-fatima").data).toContain("MSA|AR");
  });
});

describe("patient companion", () => {
  it("a wrong preparation answer leads to a call, never to 'wrong'", () => {
    const path = `/v1/me/cases/${RAJESH}/prep-check`;
    const wrong = demoRequest("core", "POST", path, { answers: { diet: "day_before", home: "drive", unfinished: "call" } }, "p-rajesh");
    expect(wrong.data.follow_up_needed).toBe(true);
    expect(wrong.data.message).toMatch(/call you/);
    expect(wrong.data.message.toLowerCase()).not.toContain("wrong");
    const right = demoRequest("core", "POST", path, { answers: { diet: "day_before", home: "adult", unfinished: "call" } }, "p-rajesh");
    expect(right.data.all_correct).toBe(true);
  });
  it("another patient's prep check is not visible", () => {
    expect(demoRequest("core", "GET", `/v1/me/cases/${RAJESH}/prep-check`, undefined, "p-noura").status).toBe(404);
  });
  it("patient case messages carry no clinical values", () => {
    for (const pc of Object.values<any>(RAW.patient_cases)) {
      for (const lang of ["en", "ar"]) for (const it of pc[lang].items) {
        const codes = messagePolicy(it.message).violations.map((v) => v.code);
        expect(codes, it.message).not.toContain("RESULT_VALUE");
        expect(codes, it.message).not.toContain("LINK");
      }
    }
  });
  it("consent is recorded", () => {
    demoRequest("core", "POST", `/v1/me/cases/${NOURA}/consent`, {}, "p-noura");
    const items = demoRequest("core", "GET", "/v1/me/cases?lang=ar", undefined, "p-noura").data.items;
    expect(items[0].consent_given).toBe(true);
  });
});

describe("demo honesty", () => {
  it("an unrecorded action says so instead of pretending", () => {
    const r = demoRequest("core", "POST", `/v1/cases/${RAJESH}/handoff`, { to: "dr-hessa", reason: "test" }, "dr-fatima");
    expect(r.status).toBe(501);
    expect(r.data.error.code).toBe("DEMO_NOT_RECORDED");
  });
  it("reset restores the recorded starting point", () => {
    demoRequest("core", "POST", "/v1/demo/scenarios/false-done", {}, "dr-fatima");
    resetDemo();
    expect(bundle().case_lists["dr-fatima"].items.length).toBe(RAW.case_lists["dr-fatima"].items.length);
    expect(demoSession().falseDoneRun).toBe(false);
  });
});

describe("live-mode helpers and the landing page's numbers", () => {
  it("finds a patient's case id for the guided tour", async () => {
    const { caseIdForPatient } = await import("../lib/api");
    expect(await caseIdForPatient("p-rajesh", "dr-fatima")).toBe(RAJESH);
    expect(await caseIdForPatient("p-nobody", "dr-fatima")).toBeNull();
  });
  it("every landing-page number is filled in and traceable to evidence", async () => {
    const { BENCH, REAL } = await import("../lib/landing-facts");
    for (const [k, v] of Object.entries({ ...BENCH, ...REAL })) expect(v, k).not.toMatch(/^—$|^$/);
    const doc = readFileSync(resolve(__dirname, "../../../docs/evidence/REAL_WORLD_FIT.md"), "utf-8");
    for (const v of [REAL.medianDaysTasleem, REAL.medianDaysStatus, REAL.veryTightDays, REAL.alertsPer100, REAL.veryTightFalseAlertPct]) expect(doc).toContain(v);
  });
});

describe("simulator: report-arrives names the false-done case (live API needs its id)", () => {
  it("remembers the case this browser created and forgets it on reset", () => {
    expect(falseDoneCase()).toBeNull();
    rememberFalseDone("case_abc123");
    expect(falseDoneCase()).toBe("case_abc123");
    expect(demoSession().falseDoneRun).toBe(true);
    resetDemo();
    expect(falseDoneCase()).toBeNull();
    expect(demoSession().falseDoneRun).toBe(false);
  });
});

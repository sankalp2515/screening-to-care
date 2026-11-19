// Demo replayer: answers API requests from the recorded synthetic bundle.
// Every answer is a real recorded response, or a deterministic rule taken from the server
// (the message policy, the prep-check answer key, the R3 close checks the server already returned).
/* eslint-disable @typescript-eslint/no-explicit-any */
import type { Case, CaseRow, Service } from "./types";

export interface Reply { status: number; data: any; text?: boolean }

let original: any = null;
let state: any = null;
const session = { falseDoneRun: false, unreachableRun: false };

export async function loadBundle(url = "/demo-bundle.json"): Promise<any> {
  if (state) return state;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Could not load the demo data (${res.status})`);
  original = await res.json();
  state = structuredClone(original);
  return state;
}

/** For tests: install a bundle directly. */
export function installBundle(bundle: any) {
  original = bundle;
  state = structuredClone(bundle);
  session.falseDoneRun = false;
  session.unreachableRun = false;
}

/** The false-done case this browser created, so "GI centre sends the report" can name it (the live API needs its id). */
const FD_KEY = "tasleem.falseDoneCase";
export function rememberFalseDone(caseId?: string) {
  session.falseDoneRun = true;
  try { if (caseId) sessionStorage.setItem(FD_KEY, caseId); } catch { /* private mode: the session flag still works */ }
}
export function falseDoneCase(): string | null {
  try { return sessionStorage.getItem(FD_KEY); } catch { return null; }
}

export function resetDemo() {
  try { sessionStorage.removeItem(FD_KEY); } catch { /* ignore */ }
  if (!original) return;
  state = structuredClone(original);
  session.falseDoneRun = false;
  session.unreachableRun = false;
}

export function bundle(): any { return state; }
export function demoNow(): Date { return state ? new Date(state.meta.generated_at) : new Date(); }
export function demoSession() { return { ...session }; }

const notFound = (message = "Not found"): Reply => ({ status: 404, data: { error: { code: "NOT_FOUND", message } } });
const ok = (data: any): Reply => ({ status: 200, data });

// ---- Local message policy: an exact port of backend/tasleem/domain/messaging.py (the server stays the
// authority in live mode; the demo must give the same answer for the same text).
const VALUE = /(\d+[.,]\d+)|(\d+\s*\/\s*\d+)|(\d+\s*(%|mg|mmol|ng|µg|ug|mm\s*hg|mmhg|g\/dl|iu)\b)|(\b\d{3,}\b(?!\s*(?:am|pm)))/i;
const LINK = /(https?:\/\/|www\.|\b[a-z0-9-]+\.(com|net|org|ae|io|ly)\b)/i;
const RESULT_TERMS_EN = ["cancer", "malignan", "tumour", "tumor", "carcinoma", "polyp", "positive", "negative",
  "abnormal", "normal result", "diagnos", "biopsy result", "your result is", "your results are",
  "diabetes", "diabetic", "hypertension", "high blood pressure", "lesion", "metasta"];
const RESULT_TERMS_AR = ["سرطان", "ورم", "خبيث", "إيجابي", "ايجابي", "سلبي", "غير طبيعي", "تشخيص", "سكري", "ضغط الدم المرتفع", "زوائد"];
const ADVICE_TERMS = ["stop taking", "increase your dose", "you are fine", "nothing to worry", "no need to come",
  "you don't need", "you do not need", "لا داعي للقلق", "لا تحتاج"];
export function messagePolicy(text: string): { ok: boolean; violations: { code: string; detail: string }[] } {
  const t = (text ?? "").trim();
  if (!t) return { ok: false, violations: [{ code: "EMPTY", detail: "The message is empty." }] };
  const v: { code: string; detail: string }[] = [];
  if (t.length > 600) v.push({ code: "TOO_LONG", detail: "Keep patient messages under 600 characters." });
  const low = t.toLowerCase();
  const m = t.match(VALUE);
  if (m) v.push({ code: "RESULT_VALUE", detail: `Looks like a result value: '${m[0].trim()}'.` });
  const term = [...RESULT_TERMS_EN, ...RESULT_TERMS_AR].find((w) => low.includes(w));
  if (term) v.push({ code: "RESULT_DISCLOSURE", detail: `Discloses or interprets a result: '${term}'.` });
  const adv = ADVICE_TERMS.find((w) => low.includes(w));
  if (adv) v.push({ code: "CLINICAL_ADVICE", detail: `Clinical reassurance or advice by text: '${adv}'.` });
  if (LINK.test(t)) v.push({ code: "LINK", detail: "Links are not allowed; patients open Sahatna directly." });
  return { ok: v.length === 0, violations: v };
}

// ---- Prep check answer key, from backend pathways (a wrong answer means a person calls).
const PREP_KEY: Record<string, string> = { diet: "day_before", home: "adult", unfinished: "call" };
const PREP_REPLY = {
  followUp: { en: "Thank you. A member of the care team will call you to go through the preparation together.", ar: "شكراً لك. سيتصل بك أحد أعضاء فريق الرعاية لمراجعة التحضير معك." },
  ready: { en: "Thank you. You are ready for the preparation.", ar: "شكراً لك. أنت جاهز للتحضير." },
};
const DISTRESS_WORDS = ["blood", "bleeding", "terrified", "chest pain", "دم", "نزيف"];

function rowFromCase(c: Case): CaseRow {
  return {
    id: c.id,
    patient: { id: c.patient.id, name: c.patient.name, language: c.patient.language },
    pathway: { id: c.pathway.id, name: c.pathway.name },
    status: c.status,
    priority: c.priority?.value,
    owner: c.owner,
    progress: c.progress,
    stalls: (c.stalls ?? []).map((s) => ({ reason: s.reason, label: s.label, level: s.level })),
    escalation_level: Math.max(0, ...(c.stalls ?? []).map((s) => s.level)),
    days_since_progress: c.days_since_progress,
    open_barriers: (c.barriers ?? []).filter((b) => b.status !== "resolved").length,
    distress_open: (c.distress ?? []).filter((d) => !d.resolved).length,
    outcome: c.outcome ? (c.outcome.outcome ?? c.outcome) : null,
  };
}

function isCase(x: any): x is Case { return x && typeof x === "object" && "id" in x && "timeline" in x && "actions" in x; }

function ensureCase(id: string) {
  state.cases[id] ??= { detail_by_persona: {}, audit: { verification: { ok: true, checked: 0, broken_at_seq: null, problem: null }, events: [] }, referral_options: { options: [] }, trail: { items: [] }, assist_by_persona: {} };
  return state.cases[id];
}

function applyCase(c: Case, persona: string) {
  const entry = ensureCase(c.id);
  entry.detail_by_persona[persona] = c;
  for (const p of Object.keys(entry.detail_by_persona)) entry.detail_by_persona[p] = { ...c, actions: entry.detail_by_persona[p].actions ?? c.actions };
  entry.detail_by_persona[persona] = c;
  const row = rowFromCase(c);
  for (const list of Object.values<any>(state.case_lists)) {
    list.items = list.items.map((r: CaseRow) => (r.id === c.id ? { ...r, ...row, why: r.why } : r));
  }
  for (const w of Object.values<any>(state.work)) {
    for (const s of w.sections) s.items = s.items.map((r: CaseRow) => (r.id === c.id ? { ...r, ...row, why: r.why } : r));
  }
}

function prependRow(staff: string, row: CaseRow) {
  state.case_lists[staff] ??= { items: [], next_offset: null };
  const list = state.case_lists[staff];
  list.items = [row, ...list.items.filter((r: CaseRow) => r.id !== row.id)];
}

function runScenario(sid: string): Reply {
  const run = state.scenarios.runs[sid];
  if (!run) return notFound("Unknown scenario");
  if (sid === "report-arrives" && !session.falseDoneRun) {
    return { status: 409, data: { error: { code: "SCENARIO_ORDER", message: "Run 'Malaffi says completed, colonoscopy never happened' first. This scenario sends the report for that case." } } };
  }
  const c: Case = run.case_as_owner;
  const owner = c.owner.id;
  const entry = ensureCase(c.id);
  entry.detail_by_persona[owner] = c;
  entry.detail_by_persona["coord-sara"] = c;
  if (run.assist_as_owner) entry.assist_by_persona[owner] = run.assist_as_owner;
  const row = rowFromCase(c);
  prependRow(owner, row);
  prependRow("coord-sara", row);
  if (run.owner_work_after) state.work[owner] = run.owner_work_after;
  if (sid === "false-done") session.falseDoneRun = true;
  if (sid === "unreachable-patient") session.unreachableRun = true;
  return ok(run.response);
}

function runNotifier(): Reply {
  if (!session.unreachableRun) return ok({ pulled: 0, dispatched: {}, digests: 0, reported_unreached: 0 });
  const run = state.scenarios.runs["unreachable-patient"];
  const c: Case = run.case_after_notifier;
  const entry = ensureCase(c.id);
  entry.detail_by_persona["nav-aisha"] = c;
  entry.detail_by_persona[c.owner.id] = c;
  entry.detail_by_persona["coord-sara"] = c;
  entry.trail = run.trail_after_notifier;
  state.work["nav-aisha"] = run.navigator_work_after;
  prependRow("nav-aisha", rowFromCase(c));
  return ok(run.notifier_run_once);
}

function patientItems(persona: string): any[] {
  const pc = state.patient_cases[persona];
  if (!pc) return [];
  return [...(pc.en?.items ?? []), ...(pc.ar?.items ?? [])];
}

function findCommand(method: string, path: string, persona: string) {
  return state.commands.find((c: any) => c.method === method && c.path === path && c.persona === persona)
    ?? state.commands.find((c: any) => c.method === method && c.path === path);
}

export function demoRequest(service: Service, method: string, rawPath: string, body: any, persona: string): Reply {
  if (!state) return { status: 503, data: { error: { code: "DEMO_LOADING", message: "The demo data is still loading." } } };
  const url = new URL(rawPath, "http://demo.local");
  const path = url.pathname;
  const q = url.searchParams;
  const P = persona;
  let m: RegExpMatchArray | null;

  if (method === "GET") {
    if (service === "core") {
      if (path === "/v1/directory/people") return ok(state.directory);
      if (path === "/v1/me") return state.me[P] ? ok(state.me[P]) : notFound("Unknown persona");
      if (path === "/v1/me/work") return state.work[P] ? ok(state.work[P]) : ok({ person: P, needs_action: 0, sections: [] });
      if (path === "/v1/cases") {
        let items: CaseRow[] = state.case_lists[P]?.items ?? [];
        const status = q.get("status") ?? "open";
        if (status !== "all") items = items.filter((r) => r.status === status);
        if (q.get("stalled") === "true") items = items.filter((r) => r.stalls.length > 0);
        if (q.get("pathway")) items = items.filter((r) => r.pathway.id === q.get("pathway"));
        if (q.get("owner")) items = items.filter((r) => r.owner.id === q.get("owner"));
        return ok({ items, next_offset: null });
      }
      if ((m = path.match(/^\/v1\/cases\/([^/]+)$/))) {
        const c = state.cases[m[1]]?.detail_by_persona?.[P];
        return c ? ok(c) : notFound("Not found, or outside your clinic");
      }
      if ((m = path.match(/^\/v1\/cases\/([^/]+)\/audit$/))) return state.cases[m[1]] ? ok(state.cases[m[1]].audit) : notFound();
      if ((m = path.match(/^\/v1\/cases\/([^/]+)\/referral-options$/))) return state.cases[m[1]] ? ok(state.cases[m[1]].referral_options) : notFound();
      if (path === "/v1/me/cases") {
        const lang = q.get("lang") === "ar" ? "ar" : "en";
        const pc = state.patient_cases[P];
        return pc ? ok(pc[lang]) : ok({ items: [] });
      }
      if ((m = path.match(/^\/v1\/me\/cases\/([^/]+)\/prep-check$/))) {
        const pc = state.prep_checks[m[1]];
        return pc && pc.persona === P ? ok(pc.response) : notFound("No preparation check for this step");
      }
      if (path === "/v1/program/metrics") {
        const org = q.get("org"), lang = q.get("language");
        if (org && !lang && state.programme.metrics_by_filter[`org=${org}`]) return ok(state.programme.metrics_by_filter[`org=${org}`]);
        if (lang && !org && state.programme.metrics_by_filter[`language=${lang}`]) return ok(state.programme.metrics_by_filter[`language=${lang}`]);
        return ok(state.programme.metrics);
      }
      if (path === "/v1/program/usage") return ok(state.programme.usage);
      if (path === "/v1/demo/scenarios") return ok(state.scenarios.list);
    }
    if (service === "agent" && (m = path.match(/^\/v1\/cases\/([^/]+)\/assist$/))) {
      const a = state.cases[m[1]]?.assist_by_persona ?? {};
      const hit = a[P] ?? Object.values(a)[0];
      return hit ? ok(hit) : notFound("No assistant summary for this case");
    }
    if (service === "notifier") {
      if (path === "/v1/notifications") {
        const id = q.get("case_id") ?? "";
        return ok(state.cases[id]?.trail ?? { items: [] });
      }
      if (path === "/v1/policy") return ok(state.programme.channels);
    }
    return notFound();
  }

  // ---- POST
  if (service === "core" && (m = path.match(/^\/v1\/demo\/scenarios\/([^/]+)$/))) return runScenario(m[1]);
  if (service === "notifier" && path === "/v1/run-once") return runNotifier();
  if (service === "connector" && path === "/v1/hl7") {
    const run = state.scenarios.runs["new-positive-fit"];
    const text = String(body ?? "");
    if (text.includes("MSH|") && text.includes("ORU^R01")) { runScenario("new-positive-fit"); return { status: 200, data: run.hl7_ack, text: true }; }
    return { status: 200, data: run.hl7_ack_garbage, text: true };
  }
  if (path === "/v1/policy/patient-message-check") return ok(messagePolicy(body?.text ?? ""));

  if ((m = path.match(/^\/v1\/me\/cases\/([^/]+)\/prep-check$/))) {
    const pc = state.prep_checks[m[1]];
    if (!pc || pc.persona !== P) return notFound("No preparation check for this step");
    const answers = body?.answers ?? {};
    const wrong = Object.keys(PREP_KEY).filter((k) => answers[k] !== PREP_KEY[k]);
    const lang = pc.response.language === "ar" ? "ar" : "en";
    return ok({ all_correct: wrong.length === 0, follow_up_needed: wrong.length > 0, message: wrong.length ? PREP_REPLY.followUp[lang] : PREP_REPLY.ready[lang] });
  }
  if ((m = path.match(/^\/v1\/me\/cases\/([^/]+)\/consent$/))) {
    const items = patientItems(P).filter((i) => i.case_id === m![1]);
    if (!items.length) return notFound();
    items.forEach((i) => (i.consent_given = true));
    return ok(items[0]);
  }
  if ((m = path.match(/^\/v1\/cases\/([^/]+)\/barriers$/)) && state.me[P]?.actor_type === "patient") {
    const recorded = findCommand("POST", path, P);
    const text = String(body?.text ?? "");
    const distress = DISTRESS_WORDS.some((w) => text.toLowerCase().includes(w));
    patientItems(P).filter((i) => i.case_id === m![1]).forEach((i) => (i.open_requests = (i.open_requests ?? 0) + 1));
    return ok({ ...(recorded?.response ?? {}), routed_to_human: true, distress_flagged: distress });
  }

  const caseM = path.match(/^\/v1\/cases\/([^/]+)\/(.+)$/);
  if (caseM && caseM[2] === "patient-messages") {
    const pol = messagePolicy(body?.text ?? "");
    if (!pol.ok) return { status: 409, data: { error: { code: "IFHAS_MESSAGE_POLICY", message: pol.violations[0].detail, details: { violations: pol.violations } } } };
  }
  if (caseM && caseM[2] === "close") {
    const c: Case | undefined = state.cases[caseM[1]]?.detail_by_persona?.[P];
    const opt = c?.actions.close.find((o) => o.outcome === body?.outcome);
    if (opt && !opt.allowed) return { status: 409, data: { error: { code: opt.code, message: opt.message } } };
    if (opt) {
      const missing = opt.requires.filter((f) => !String(body?.[f] ?? "").trim());
      if (missing.length) return { status: 422, data: { error: { code: "R3_FIELDS_REQUIRED", message: `Required: ${missing.join(", ")}.` } } };
    }
  }

  const cmd = findCommand(method, path, P);
  if (cmd) {
    const res = structuredClone(cmd.response);
    if (cmd.status === 200) {
      if (isCase(res)) applyCase(res, P);
      else if (res && isCase(res.case)) applyCase(res.case, P);
    }
    return { status: cmd.status, data: res };
  }
  return {
    status: 501,
    data: { error: { code: "DEMO_NOT_RECORDED", message: `This action isn't part of the recorded demo. In the live product it calls ${method} ${path}.` } },
  };
}

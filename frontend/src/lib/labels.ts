import { knownPeople, now } from "./api";

export const EVENT_LABELS: Record<string, string> = {
  CASE_OPENED: "Case opened", STAGE_REACHED: "Step reached", ADMIN_STATUS_CHANGED: "Referral status changed",
  STALL_FLAGGED: "Stall detected", STALL_CLEARED: "Stall cleared on evidence", ESCALATED: "Escalated",
  HANDOFF_OFFERED: "Handoff offered", HANDOFF_ACCEPTED: "Handoff accepted", HANDOFF_REJECTED: "Handoff declined",
  BARRIER_REPORTED: "Patient reported a barrier", BARRIER_SUGGESTED: "AI suggested a barrier code",
  BARRIER_CONFIRMED: "Barrier confirmed", BARRIER_RESOLVED: "Barrier resolved", DISTRESS_FLAGGED: "Distress flagged",
  DISTRESS_RESOLVED: "Distress handled", CONTACT_ATTEMPTED: "Contact attempt", CONSULT_REQUESTED: "E-consult requested",
  CONSULT_ANSWERED: "E-consult answered", APPOINTMENT_MISSED: "Appointment missed", REFERRAL_REJECTED: "Referral rejected",
  WARNING_ADDED: "Data warning", PATIENT_MESSAGE_SENT: "Message sent to patient", DELIVERY_FAILED: "Message not delivered",
  CASE_CLOSED: "Case closed", CONSENT_GIVEN: "Patient gave consent", PRIORITY_SET: "Priority set by rule",
};

export const ROLE_LABELS: Record<string, string> = {
  family_physician: "Family physician", navigator: "Care navigator", clinic_lead: "Clinic lead",
  program_coordinator: "Programme coordinator", gi_specialist: "GI specialist", patient: "Patient",
};

export const OUTCOME_LABELS: Record<string, string> = {
  COMPLETED_WITH_REPORT: "Completed, report received", COMPLETED_ELSEWHERE: "Completed elsewhere",
  PLAN_CHANGED: "Clinical plan changed", INFORMED_REFUSAL: "Informed refusal", UNREACHABLE: "Patient unreachable",
};

export const STALL_LABELS: Record<string, string> = {
  STEP_OVERDUE: "Next step overdue", REFERRAL_REJECTED: "Referral rejected", REPORT_NOT_COMMUNICATED: "Report not shared with patient",
  CLOSED_WITHOUT_EVIDENCE: "Marked completed without a report", BOOKED_NOT_ATTENDED: "Booked, not attended",
  HANDOFF_NOT_ACCEPTED: "Handoff not accepted", NO_PATIENT_REPLY: "No reply from patient", PATIENT_NOT_REACHED: "Patient not reached",
};

export const BARRIER_LABELS: Record<string, string> = {
  FEAR: "Fear or worry", PREP_UNCLEAR: "Preparation unclear", NO_ESCORT: "No escort home", TRANSPORT: "Transport",
  COST_OR_INSURANCE: "Cost or insurance", TIME_OR_WORK: "Work or time", LANGUAGE: "Needs an interpreter", FEMALE_CLINICIAN: "Prefers a female doctor",
  WANTS_CALLBACK: "Wants a call", DONE_ELSEWHERE: "Done elsewhere", OTHER: "Something else",
};

export const ORG_LABELS: Record<string, string> = {
  "org-ghaf": "Ghaf health centre", "org-samar": "Samar clinic", "org-dana": "Dana GI centre",
  "org-falaj": "Falaj GI centre", "org-program": "Screening programme",
};

export const CHANNEL_LABELS: Record<string, string> = {
  sahatna: "Sahatna", sahatna_push: "Sahatna app", sms_nudge: "SMS nudge", emr_task: "EMR inbox", sms_page: "SMS page",
  worklist: "Worklist", emr_inbox: "EMR inbox", email: "Email", email_digest: "Email digest",
};

export const STAGE_SHORT: Record<string, string> = {
  PATIENT_INVITED: "Invited", RESULT_DISCUSSED: "Result", REFERRED: "Referred", REFERRAL_ACCEPTED: "Accepted",
  BOOKED: "Booked", ATTENDED: "Attended", PROCEDURE_DONE: "Procedure", REPORT_RECEIVED: "Report", OUTCOME_COMMUNICATED: "Closed",
};

export const label = (map: Record<string, string>, code: string | null | undefined) =>
  !code ? "" : map[code] ?? code.toLowerCase().replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());

/** "Dr. Fatima (family physician)" -> "Dr. Fatima". Also accepts a person id ("nav-aisha") and resolves it. */
export const shortName = (n: string | null | undefined): string => {
  const s = n ?? "";
  if (/^(dr|nav|coord|p)-[a-z]+$/.test(s)) {
    const d = knownPeople();
    const hit = [...(d?.staff ?? []), ...(d?.patients ?? [])].find((p: { id: string }) => p.id === s);
    if (hit) return hit.name.replace(/\s*\(.*\)\s*$/, "");
  }
  return s.replace(/\s*\(.*\)\s*$/, "");
};
export const initials = (n: string) => shortName(n).replace(/^Dr\.\s*/, "").split(/\s+/).map((w) => w[0]).join("").slice(0, 2).toUpperCase();

export function relTime(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso).getTime();
  const diff = (now().getTime() - d) / 1000;
  const abs = Math.abs(diff);
  const fmt = (n: number, u: string) => `${n} ${u}${n === 1 ? "" : "s"}`;
  let s: string;
  if (abs < 60) s = "just now";
  else if (abs < 3600) s = fmt(Math.round(abs / 60), "minute");
  else if (abs < 86400) s = fmt(Math.round(abs / 3600), "hour");
  else s = fmt(Math.round(abs / 86400), "day");
  if (s === "just now") return s;
  return diff >= 0 ? `${s} ago` : `in ${s}`;
}

export function exactTime(iso: string | null | undefined): string {
  if (!iso) return "";
  return new Date(iso).toLocaleString("en-GB", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit", timeZone: "Asia/Dubai" }) + " GST";
}

export function dateOnly(iso: string | null | undefined, lang = "en"): string {
  if (!iso) return "";
  return new Date(iso).toLocaleString(lang === "ar" ? "ar-AE" : "en-GB", { weekday: "long", day: "numeric", month: "long", hour: "numeric", minute: "2-digit", timeZone: "Asia/Dubai" });
}

/** A record reference as a person would say it ("Colonoscopy report"), the id kept for the title tooltip. */
const SOURCE_LABELS: Record<string, string> = {
  Communication: "Sahatna message", Encounter: "Clinic visit record", ServiceRequest: "Referral in Malaffi",
  Task: "GI centre response", Appointment: "Booking", Procedure: "Procedure record", DiagnosticReport: "Colonoscopy report",
  Observation: "Lab result", CarePlan: "Care plan", Patient: "Patient record",
};
export const sourceLabel = (ref: string | null | undefined): string => (ref ? SOURCE_LABELS[ref.split("/")[0]] ?? "Record" : "");

/** A model or reader id as a reviewer would read it. */
export const modelLabel = (m: string | null | undefined): string => {
  const s = m ?? "";
  if (/gpt-5-mini/.test(s)) return "GPT-5 mini (Azure OpenAI)";
  if (s === "keyword-reader-v1") return "Keyword reader";
  if (s === "keyword-v1") return "Keyword matcher";
  return s.replace(/^[a-z_]+:/, "");
};

/** "1 day", "3 days". */
export const plural = (n: number, one: string, many = `${one}s`): string => `${n} ${n === 1 ? one : many}`;

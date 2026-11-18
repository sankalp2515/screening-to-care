// Fields the UI reads. Shapes come from the recorded Tasleem responses (docs/lovable/demo/demo-bundle.json).
/* eslint-disable @typescript-eslint/no-explicit-any */

export type Service = "core" | "agent" | "notifier" | "connector";

export interface Person { id: string; name: string; role: string }
export interface Me extends Person { actor_type: string; org_id?: string; sees_all_cases?: boolean; language?: string }

export interface Progress {
  verified: { stage: string; step: number; of: number };
  reported: { admin_status: string | null; implied_stage: string | null; step: number; of: number };
  gap: boolean;
}

export interface StallChip { reason: string; label: string; level: number }

export interface CaseRow {
  id: string;
  patient: { id: string; name: string; language: string };
  pathway: { id: string; name: string };
  status: string;
  priority: string;
  owner: Person;
  progress: Progress;
  stalls: StallChip[];
  escalation_level: number;
  days_since_progress: number | null;
  open_barriers: number;
  distress_open: number;
  outcome: string | null;
  why?: { kind: string; refs: string[]; since: string | null };
}

export interface WorkSection { kind: string; label: string; count: number; items: CaseRow[] }
export interface Work { person: string; needs_action: number; sections: WorkSection[] }

export interface Stage { id: string; label: string; note: string | null; reached: boolean; reached_at: string | null; evidence_ref: string | null; provenance: string | null }
export interface Stall extends StallChip { stage: string; detail: string; flagged_at: string; last_escalated_at: string | null; escalated_to: Person | null; provenance: string }
export interface Barrier {
  id: string; reported_codes: string[]; text: string | null; reported_by: string; reported_at: string;
  suggested_code: string | null; suggested_confidence: number | null; suggested_model: string | null;
  confirmed_code: string | null; confirmed_by: string | null; assignee_role: string | null; action: string | null;
  due_at: string | null; status: string; resolution_note: string | null;
}
export interface Distress { id: string; barrier_id: string | null; matched: string[] | string; flagged_at: string; routed_to: string; resolved: boolean; resolved_by: string | null; note: string | null }
export interface Consult { id: string; to_id: string; asked_by: string; question: string; asked_at: string; due_at: string; answer: string | null; answered_at: string | null }
export interface Allowed { allowed: boolean; code?: string; message?: string }
export interface CloseOption extends Allowed { outcome: string; requires: string[] }
export interface TimelineEvent { seq: number; type: string; at: string; actor: string; provenance: string; payload: Record<string, any> }

export interface Case {
  id: string; status: string; version: number;
  patient: { id: string; name: string; language: string; insurance_network?: string; birth_year?: number };
  pathway: { id: string; name: string; version: number };
  priority: { value: string; provenance: string; rule?: string };
  owner: Person;
  pending_handoff: { to_id: string; reason: string; offered_by: string; offered_at: string } | null;
  progress: Progress;
  stages: Stage[];
  appointment_at: string | null; appointment_missed: boolean;
  stalls: Stall[]; barriers: Barrier[]; distress: Distress[]; consults: Consult[];
  contact_attempts: any[]; warnings: any[]; consent_at: string | null; outcome: any;
  days_since_progress: number | null;
  timeline: TimelineEvent[];
  next_step: { reason: string; who: string; text: string; provenance: string; person: { id: string; name: string } | null } | null;
  actions: {
    offer_handoff: Allowed; accept_handoff: Allowed; reject_handoff: Allowed; log_contact: Allowed;
    request_consult: Allowed; message_patient: Allowed; close: CloseOption[];
    barriers: Record<string, any>; distress: Record<string, Allowed>; consults: Record<string, Allowed>;
  };
  notifications: any[];
}

export interface Assist {
  case_id: string;
  sense: { id: string; text: string; cites: number[] }[];
  decide: { next_step: Case["next_step"]; note: string };
  act: {
    brief: { provenance: string; source: string; model: string; sentences: { text: string; cites: number[] }[]; draft_id: string };
    patient_message: PatientDraft;
  };
  hand_off: { to: { id: string; name: string } | null; note: string };
  llm?: any;
}
export interface PatientDraft {
  draft: { text: string; language: string; template: string } | null;
  why: string; provenance: string; source: string; draft_id: string | null; requires_approval: boolean;
  send_with: { method: string; path: string; body: { text: string; language: string; ai_draft_id: string } } | null;
}

export interface PatientCase {
  case_id: string; status: string; language: string; direction: "ltr" | "rtl"; message: string;
  appointment_at: string | null; consent_given: boolean; barrier_options: { code: string; label: string }[]; open_requests: number;
}
export interface PrepCheck { case_id: string; language: string; direction: "ltr" | "rtl"; questions: { id: string; text: string; options: { id: string; text: string }[] }[] }

export class ApiError extends Error {
  status: number; code: string; details?: any;
  constructor(status: number, code: string, message: string, details?: any) {
    super(message); this.status = status; this.code = code; this.details = details;
  }
}

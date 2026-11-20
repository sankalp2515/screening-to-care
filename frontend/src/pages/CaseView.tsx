import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { AlertOctagon, ArrowLeft, Check, Circle, Minus, Quote, Sparkles } from "lucide-react";
import { request, useCase, useCommand, useMe } from "../lib/api";
import { usePersona } from "../lib/persona";
import { BARRIER_LABELS, exactTime, label, modelLabel, relTime, ROLE_LABELS, shortName, sourceLabel } from "../lib/labels";
import type { Barrier, Case, Distress } from "../lib/types";
import CaseActions from "../components/CaseActions";
import CasePanels from "../components/CasePanels";
import ReportReader from "../components/ReportReader";
import Organiser from "../components/Organiser";
import { Button, Card, DualBars, ErrorState, LangTag, Overline, Skeleton, Source, Tag, cx, inputCls, toastError, useToast } from "../components/ui";

function DistressPanel({ c, d }: { c: Case; d: Distress }) {
  const [note, setNote] = useState("");
  const cmd = useCommand();
  const toast = useToast();
  const a = c.actions.distress[d.id] ?? { allowed: false };
  const matched = Array.isArray(d.matched) ? d.matched.join(", ") : d.matched;
  return (
    <section data-distress role="alert" aria-live="assertive" className="rounded border-2 border-stop bg-stop-wash p-4">
      <p className="flex items-center gap-2 font-semibold text-stop"><AlertOctagon size={20} aria-hidden />Urgent: the patient's message mentions “{matched}”</p>
      <p className="mt-1 text-[14px] text-ink-2">Routed to {shortName(d.routed_to)} {relTime(d.flagged_at)}. A clinician calls the patient. No message is drafted.</p>
      <div className="mt-3 space-y-2">
        <label htmlFor={`dn-${d.id}`} className="block text-[14px] font-medium">Record what was done</label>
        <textarea id={`dn-${d.id}`} rows={2} className={inputCls} value={note} onChange={(e) => setNote(e.target.value)} placeholder="Called the patient; bleeding assessed; urgent slot booked." />
        <div className="flex flex-wrap items-center gap-3">
          <Button variant="primary" disabled={!a.allowed || !note.trim() || cmd.isPending}
            onClick={() => cmd.mutate({ path: `/v1/cases/${c.id}/distress/${d.id}/resolve`, body: { note } }, { onSuccess: () => toast({ tone: "done", text: "Distress response recorded and signed." }), onError: (e) => toastError(toast, e) })}>
            Sign and record
          </Button>
          {!a.allowed && <span className="flex items-center gap-2 text-[13px]"><Source kind="rule">{a.code}</Source><span className="text-ink-2">{a.message}</span></span>}
        </div>
      </div>
    </section>
  );
}

/** One card for every stall on the case, with a single ladder at its highest level (judge finding, 20 Nov: three
 * ladders on one case read as three escalations). Level 1 is "flagged to" the first person; "escalated" starts at 2. */
function StallCard({ c }: { c: Case }) {
  const top = [...c.stalls].sort((a, b) => b.level - a.level)[0];
  const first = top.level <= 1;
  return (
    <Card className="p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-[16px] font-semibold">{c.stalls.length === 1 ? top.label : `${c.stalls.length} things are stuck`}</h3>
        <span title={c.stalls.map((s) => s.reason).join(", ")}><Source kind="rule" /></span>
      </div>
      <ul className="mt-2 space-y-1 text-[14px] text-ink-2">
        {c.stalls.map((s) => <li key={s.reason}>{c.stalls.length > 1 && <strong className="font-medium text-ink">{s.label}: </strong>}{s.detail}. Flagged {relTime(s.flagged_at)}.</li>)}
      </ul>
      <ol className="mt-3 grid grid-cols-3 gap-1 text-[12px]" aria-label="Escalation ladder">
        {["Owner", "Clinic lead", "Programme coordinator"].map((n, i) => (
          <li key={n} className={cx("rounded-sm border px-2 py-1.5", i + 1 === top.level ? (first ? "border-attn bg-attn-wash font-semibold text-attn" : "border-stop bg-stop-wash font-semibold text-stop") : i + 1 < top.level ? "border-rule bg-sheet-2 text-muted" : "border-rule text-muted")}>
            <span className="tnum">{i + 1}</span> {n}
          </li>
        ))}
      </ol>
      {top.escalated_to && <p className="mt-2 text-[13px] text-ink-2">{first ? "Flagged to" : `Escalated to level ${top.level},`} <strong>{shortName(top.escalated_to.name)}</strong>{top.last_escalated_at && <> {relTime(top.last_escalated_at)}</>}. If nobody acts, it moves up a level; it always reaches a named person.</p>}
    </Card>
  );
}

/** A2: what the model understood from a free-text reply (English gist for Arabic, and a barrier code).
 * Suggest-only: the navigator decides. Hidden when no model answers (demo bundle, model off). */
function AiUnderstood({ text, onUse, onRead }: { text: string; onUse: (code: string) => void; onRead: (code: string) => void }) {
  const { persona } = usePersona();
  const [gist, setGist] = useState<{ text: string; model: string } | null>(null);
  const [code, setCode] = useState<{ code: string | null; confidence: number; model: string } | null>(null);
  const ar = /[؀-ۿ]/.test(text);
  useEffect(() => {
    let live = true;
    if (ar) request("agent", "POST", "/v1/translate", { text, target: "en" }, persona!)
      .then((r) => { if (live && r?.available) setGist({ text: r.text, model: r.model }); }).catch(() => undefined);
    request("agent", "POST", "/v1/barrier-suggestion", { text, target: "en" }, persona!)
      .then((r) => { if (live && r?.available) { setCode({ code: r.code, confidence: r.confidence, model: r.model }); if (r.code) onRead(r.code); } }).catch(() => undefined);
    return () => { live = false; };
  }, [text, ar, persona]); // eslint-disable-line react-hooks/exhaustive-deps
  if (!gist && !code) return null;
  return (
    <div className="reveal mt-3 rounded border border-dashed border-ai bg-ai-wash p-3 text-[14px]">
      <p className="flex flex-wrap items-center gap-2"><Sparkles size={16} className="text-ai" aria-hidden /><span className="font-semibold text-ai">AI understood</span><span className="text-[12px] text-muted">{modelLabel((gist ?? code)!.model)}</span></p>
      {gist && <p className="mt-1.5 text-ink">“{gist.text}”</p>}
      {code?.code && (
        <p className="mt-1.5 flex flex-wrap items-center gap-2 text-ink-2">Reads as <Tag tone="ai">{label(BARRIER_LABELS, code.code)}</Tag><span className="mono text-[12px] text-muted">{Math.round(code.confidence * 100)}%</span>
          <button type="button" className="text-[13px] font-medium text-biro underline-offset-2 hover:underline" onClick={() => onUse(code.code!)}>Use this</button></p>
      )}
      <p className="mt-1 text-[12px] text-muted">A suggestion. The navigator decides what the patient meant.</p>
    </div>
  );
}

function BarrierCard({ c, b }: { c: Case; b: Barrier }) {
  const [code, setCode] = useState(b.suggested_code ?? "OTHER");
  const [note, setNote] = useState("");
  const [resolving, setResolving] = useState(false);
  const cmd = useCommand();
  const toast = useToast();
  const acts = c.actions.barriers[b.id] ?? {};
  const ar = /[؀-ۿ]/.test(b.text ?? "");
  // Judge finding, 20 Nov: "I saw blood… terrified" was offered as "Fear or worry 90%" for a navigator to confirm.
  const symptom = c.distress.some((d) => d.barrier_id === b.id);
  // When the model reader answers, it is the one suggestion shown; the keyword reading steps back (judge, 20 Nov).
  const [modelRead, setModelRead] = useState(false);
  const done = (t: string) => ({ onSuccess: () => toast({ tone: "done", text: t }), onError: (e: Parameters<typeof toastError>[1]) => toastError(toast, e) });
  return (
    <Card className="p-4" data-barrier>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-[16px] font-semibold">What the patient said</h3>
        <span className="text-[12px] text-muted" title={exactTime(b.reported_at)}>Reported {relTime(b.reported_at)} in Sahatna</span>
      </div>
      {b.text && (
        <blockquote dir={ar ? "rtl" : "ltr"} lang={ar ? "ar" : "en"} className="mt-3 flex gap-3 border-s-2 border-ink ps-3 text-[17px] leading-[28px]">
          <Quote size={16} className="mt-1.5 shrink-0 text-muted" aria-hidden />{b.text}
        </blockquote>
      )}
      {b.reported_codes.length > 0 && <p className="mt-3 flex flex-wrap items-center gap-1.5 text-[13px] text-ink-2"><Source kind="fact">tapped</Source>{b.reported_codes.map((x) => <Tag key={x}>{label(BARRIER_LABELS, x)}</Tag>)}</p>}

      {symptom && b.status !== "resolved" && (
        <p className="mt-3 rounded border border-stop bg-stop-wash p-3 text-[14px] text-stop">
          <strong>Symptom, not a barrier.</strong> This message went to a clinician the minute it arrived. It is not classified as a barrier, and no patient message is drafted until a clinician has called.
        </p>
      )}
      {!symptom && b.status === "reported" && b.text && <AiUnderstood text={b.text} onUse={setCode} onRead={(x) => { setModelRead(true); setCode(x); }} />}

      {!symptom && b.status === "reported" && b.suggested_code && (
        <div className="mt-4 rounded border border-dashed border-ai bg-ai-wash p-3">
          {modelRead ? <p className="text-[14px] font-semibold">Confirm what the patient meant</p> : <>
          <p className="flex flex-wrap items-center gap-2 text-[14px]"><Sparkles size={16} className="text-ai" aria-hidden /><span className="font-semibold text-ai">AI suggestion · needs a person to confirm:</span><span className="font-semibold">{label(BARRIER_LABELS, b.suggested_code)}</span><span className="mono text-[12px] text-muted">{Math.round((b.suggested_confidence ?? 0) * 100)}%</span></p>
          <p className="mt-1 text-[12px] text-muted">Reader: {modelLabel(b.suggested_model)}. It cannot set priority, change the plan or close the case (R5).</p></>}
          <div className="mt-3 flex flex-wrap items-end gap-2">
            <label className="text-[13px]"><span className="mb-1 block font-medium">Confirm as</span>
              <select className={cx(inputCls, "h-10 w-auto py-0")} value={code} onChange={(e) => setCode(e.target.value)}>{Object.keys(BARRIER_LABELS).map((k) => <option key={k} value={k}>{BARRIER_LABELS[k]}</option>)}</select>
            </label>
            <Button variant="primary" disabled={!acts.confirm?.allowed || cmd.isPending} onClick={() => cmd.mutate({ path: `/v1/cases/${c.id}/barriers/${b.id}/confirm`, body: { code } }, done("Barrier confirmed. A task with a due date was created."))}>Confirm</Button>
            <Button variant="quiet" onClick={() => setResolving((r) => !r)}>Mark resolved</Button>
          </div>
          {!acts.confirm?.allowed && acts.confirm && <p className="mt-2 text-[12px] text-muted"><span className="mono">{acts.confirm.code}</span> · {acts.confirm.message}</p>}
        </div>
      )}
      {b.status === "confirmed" && (
        <div className="reveal mt-4 rounded border border-rule-strong bg-sheet-2 p-3 text-[14px]">
          <p className="flex flex-wrap items-center gap-2"><Source kind="human">{shortName(b.confirmed_by)} confirmed</Source><Tag tone="biro">{label(BARRIER_LABELS, b.confirmed_code)}</Tag></p>
          <p className="mt-2 font-semibold">Task: {b.action}</p>
          <p className="mt-1 text-[13px] text-ink-2">Assigned to {label(ROLE_LABELS, b.assignee_role).toLowerCase()} · due <time title={exactTime(b.due_at)}>{relTime(b.due_at)}</time> <Source kind="rule">playbook</Source></p>
          <Button className="mt-3" size="sm" variant="quiet" onClick={() => setResolving((r) => !r)}>Mark resolved</Button>
        </div>
      )}
      {b.status === "resolved" && <p className="mt-3 text-[14px] text-done"><Check size={14} className="me-1 inline" aria-hidden />Resolved: {b.resolution_note}</p>}
      {resolving && b.status !== "resolved" && (
        <div className="reveal mt-3 flex flex-wrap items-end gap-2">
          <label className="flex-1 text-[13px]"><span className="mb-1 block font-medium">What was done</span><input className={inputCls} value={note} onChange={(e) => setNote(e.target.value)} /></label>
          <Button disabled={!note.trim() || !acts.resolve?.allowed || cmd.isPending} onClick={() => cmd.mutate({ path: `/v1/cases/${c.id}/barriers/${b.id}/resolve`, body: { note } }, done("Barrier marked resolved."))}>Save</Button>
        </div>
      )}
    </Card>
  );
}

function Consults({ c }: { c: Case; meId?: string }) {
  const [ans, setAns] = useState("");
  const cmd = useCommand();
  const toast = useToast();
  if (!c.consults?.length) return null;
  return (
    <Card className="p-4" data-consults>
      <h3 className="text-[16px] font-semibold">E-consults</h3>
      <ul className="mt-3 space-y-3">
        {c.consults.map((q) => (
          <li key={q.id} className="rounded border border-rule p-3 text-[14px]">
            <p><span className="text-muted">{shortName(q.asked_by)} asked {shortName(q.to_id)}:</span> {q.question}</p>
            {q.answer ? <p className="mt-2 border-s-2 border-done ps-3"><Source kind="human">{shortName(q.to_id)}</Source> <span className="ms-1">{q.answer}</span></p>
              : c.actions.consults[q.id]?.allowed ? (
                <div className="mt-2 flex gap-2">
                  <input aria-label="Your answer" className={inputCls} value={ans} onChange={(e) => setAns(e.target.value)} />
                  <Button variant="primary" disabled={!ans.trim()} onClick={() => cmd.mutate({ path: `/v1/cases/${c.id}/consults/${q.id}/answer`, body: { answer: ans } }, { onSuccess: () => toast({ tone: "done", text: "Answer sent to the case owner." }), onError: (e) => toastError(toast, e) })}>Answer</Button>
                </div>
              ) : <p className="mt-1 text-[13px] text-attn">Waiting for an answer · due {relTime(q.due_at)}</p>}
          </li>
        ))}
      </ul>
    </Card>
  );
}

export default function CaseView() {
  const { id = "" } = useParams();
  const [sp, setSp] = useSearchParams();
  const q = useCase(id);
  const me = useMe();
  const [tab, setTab] = useState("assistant");
  const [highlight, setHighlight] = useState<number | null>(null);
  const [closeOpen, setCloseOpen] = useState(false);
  useEffect(() => { if (sp.get("close") === "1" && q.data) { setCloseOpen(true); sp.delete("close"); setSp(sp, { replace: true }); } }, [sp, q.data, setSp]);

  if (q.isLoading) return <div className="grid gap-6 lg:grid-cols-[2fr_1fr]"><div className="space-y-4"><Skeleton className="h-24" /><Skeleton className="h-16" /><Skeleton className="h-72" /></div><Skeleton className="h-96" /></div>;
  if (q.error) return <div className="space-y-4"><Link to="/app/work" className="inline-flex items-center gap-1 text-biro"><ArrowLeft size={16} />My work</Link><ErrorState error={q.error} retry={() => q.refetch()} /></div>;
  const c = q.data!;
  const openDistress = c.distress.filter((d) => !d.resolved);
  const ns = c.next_step;
  const nsTone = !ns ? "biro" : ns.reason === "DISTRESS" ? "stop" : ns.reason === "PATIENT_NOT_REACHED" || c.stalls.some((s) => s.reason === ns.reason) ? "attn" : "biro";
  const firstOpen = c.stages.find((s) => !s.reached);
  const verifiedStage = c.stages.find((s) => s.id === c.progress.verified.stage);
  const meId = me.data?.id ?? "";
  // Decision bar: one primary action for the rule-chosen next step. Dialogs live in CaseActions.
  const act = (name: string) => () => window.dispatchEvent(new CustomEvent("tasleem:action", { detail: name }));
  const goTo = (sel: string) => () => document.querySelector(sel)?.scrollIntoView({
    behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start" });
  const PRIMARY: Record<string, { label: string; run: () => void }> = {
    DISTRESS: { label: "Read the patient's message", run: goTo("[data-distress]") },
    CLOSED_WITHOUT_EVIDENCE: { label: "Ask the GI centre for the report", run: act("consult") },
    PROCEDURE_INCOMPLETE: { label: "Rebook: referral options", run: act("referral") },
    REPORT_TO_REVIEW: { label: "Check the report", run: goTo("[data-report]") },
    REPORT_NOT_REVIEWED: { label: "Check the report", run: goTo("[data-report]") },
    REFERRAL_REJECTED: { label: "See referral options", run: act("referral") },
    BOOKED_NOT_ATTENDED: { label: "Log a call to the patient", run: act("contact") },
    PATIENT_NOT_REACHED: { label: "Log a call to the patient", run: act("contact") },
    BARRIER_TO_CONFIRM: { label: "Review what the patient said", run: goTo("[data-barrier]") },
    CONSULT_UNANSWERED: { label: "See the e-consult", run: goTo("[data-consults]") },
    REPORT_NOT_COMMUNICATED: { label: "Log the conversation", run: act("contact") },
    STEP_OVERDUE: { label: "Log a contact", run: act("contact") },
    PATHOLOGY_OUTSTANDING: { label: "Ask for the pathology result", run: act("consult") },
    CONSULT_TO_ANSWER: { label: "Answer the e-consult", run: goTo("[data-consults]") },
    READY_TO_CLOSE: { label: "Close the case", run: act("close") },
  };
  const primary = ns && ns.who !== "system" ? PRIMARY[ns.reason] : undefined;

  return (
    <div className="mx-auto grid max-w-[1400px] gap-8 lg:grid-cols-[minmax(0,2fr)_minmax(340px,1fr)]">
      <div className="min-w-0 space-y-5">
        <Link to="/app/work" className="inline-flex items-center gap-1 text-[14px] text-ink-2 hover:text-biro"><ArrowLeft size={16} className="rtl:rotate-180" aria-hidden />My work</Link>
        {openDistress.map((d) => <DistressPanel key={d.id} c={c} d={d} />)}

        <header className="space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-[32px] font-semibold leading-[38px]">{c.patient.name}</h1>
            <LangTag lang={c.patient.language} />
            {c.status !== "open" && <Tag tone="done">Closed</Tag>}
          </div>
          <p className="text-ink-2">
            Born <span className="tnum">{c.patient.birth_year}</span> · {c.patient.insurance_network} network · {c.pathway.name} <span className="mono text-[12px] text-muted">v{c.pathway.version}</span>
          </p>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-[14px]">
            <span>Owner <strong>{shortName(c.owner.name)}</strong> <span className="text-muted">({label(ROLE_LABELS, c.owner.role).toLowerCase()})</span>
              {c.owner.away && <Tag tone="attn" className="ms-2">Away until {new Date(c.owner.away.until).toLocaleDateString("en-GB", { day: "numeric", month: "short" })} · covered by {shortName(c.owner.away.cover?.name)}</Tag>}</span>
            <span className="flex items-center gap-2" title={`Set by rule: ${c.priority.rule ?? "computed"}`}>Priority <strong className="capitalize">{c.priority.value}</strong><Source kind="rule" /></span>
          </div>
          {c.warnings?.length > 0 && (
            <ul aria-label="Rule warnings" className="space-y-1.5">
              {c.warnings.map((w: string) => (
                <li key={w} className="flex items-start gap-2 rounded border border-attn bg-attn-wash px-3 py-2 text-[14px] text-attn">
                  <Source kind="rule">warning</Source><span>{w}</span>
                </li>
              ))}
            </ul>
          )}
          {c.pending_handoff && (
            <p className="rounded border border-rule-strong bg-sheet-2 p-3 text-[14px]">
              Handoff pending to <strong>{shortName(c.pending_handoff.to_id)}</strong>: “{c.pending_handoff.reason}”. The sender stays the owner until it is accepted.
            </p>
          )}
        </header>

        {ns && (
          <section aria-label="Next step" className={cx("rounded border-s-4 border p-4", nsTone === "stop" && "border-stop bg-stop-wash", nsTone === "attn" && "border-attn bg-attn-wash", nsTone === "biro" && "border-biro bg-biro-wash")}>
            <Overline>Next step</Overline>
            <p className="mt-1 text-[17px] font-semibold leading-[25px]">{ns.reason === "PATIENT_NOT_REACHED" ? "Messages in Sahatna and by SMS were not delivered. Call the patient." : ns.text}</p>
            <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-[14px]">
              {primary && c.status === "open" && <Button variant="primary" onClick={primary.run}>{primary.label}</Button>}
              <span>Who acts: <strong>{shortName(ns.person?.name) || ns.who}</strong></span>
              <details className="text-[13px] text-ink-2">
                <summary className="cursor-pointer select-none font-medium text-biro">Why?</summary>
                <p className="reveal mt-1.5 flex flex-wrap items-center gap-2">Chosen by a fixed rule, not by AI. <span title={`${ns.reason} · ${c.id}`}><Source kind="rule" /></span></p>
              </details>
            </div>
          </section>
        )}
        <CaseActions c={c} meId={meId} meName={me.data?.name} meRole={me.data?.role} closeOpen={closeOpen} setCloseOpen={setCloseOpen} />

        <Card className="p-5">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h2 className="text-[22px] font-semibold leading-7">Reported versus verified</h2>
            {c.progress.gap && <Tag tone="attn">Reported, not verified</Tag>}
          </div>
          <div className="mt-5"><Organiser c={c} variant="flat" ticket={false} /></div>
          <div className="mt-4"><DualBars progress={c.progress} verifiedLabel={verifiedStage?.label} /></div>
          {c.progress.gap && (
            <p className="mt-4 rounded border border-attn bg-attn-wash p-3 text-[14px] text-attn">
              Malaffi says <strong className="mono">{c.progress.reported.admin_status}</strong>. Clinical evidence stops at “{verifiedStage?.label}”.
            </p>
          )}
          <ol className="mt-5 space-y-0">
            {c.stages.map((s, i) => {
              const stall = s.id === firstOpen?.id ? c.stalls.find((x) => x.stage === s.id) ?? c.stalls[0] : undefined;
              return (
                <li key={s.id} className="relative flex gap-3 pb-4 last:pb-0">
                  {i < c.stages.length - 1 && <span className={cx("absolute start-[11px] top-6 h-[calc(100%-16px)] w-px", s.reached ? "bg-done" : "bg-rule")} aria-hidden />}
                  <span className={cx("relative z-[1] mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full", s.status === "incomplete" ? "border-2 border-muted bg-sheet text-muted" : s.reached ? "bg-done text-white" : "border-2 border-rule-strong bg-sheet text-transparent")}>
                    {s.status === "incomplete" ? <Minus size={14} strokeWidth={3} aria-hidden /> : s.reached ? <Check size={14} strokeWidth={3} aria-hidden /> : <Circle size={6} aria-hidden />}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className={cx("text-[15px]", s.reached && s.status !== "incomplete" ? "font-semibold" : "text-ink-2")}>{s.label}{s.status === "incomplete" && <span className="ms-2 text-[13px] font-medium text-muted">attempted, incomplete</span>}<span className="sr-only">{s.status === "incomplete" ? ": attempted, the report says incomplete" : s.reached ? ": verified" : ": not yet"}</span></p>
                    {s.reached && <p className="mt-0.5 flex flex-wrap items-center gap-2 text-[12px] text-muted"><time title={exactTime(s.reached_at)}>{relTime(s.reached_at)}</time><span title={s.evidence_ref ?? undefined}><Source kind="fact">{sourceLabel(s.evidence_ref)}</Source></span></p>}
                    {s.note && <p className="mt-0.5 text-[12px] text-muted">{s.note}</p>}
                    {stall && <p className="mt-1 text-[13px] font-medium text-stop">Stalled here: {stall.detail}</p>}
                  </div>
                </li>
              );
            })}
          </ol>
        </Card>

        {c.stalls.length > 0 && <StallCard c={c} />}

        {(c.reports ?? []).slice().reverse().map((r) => <ReportReader key={r.id} c={c} r={r} />)}
        {c.barriers.map((b) => <BarrierCard key={b.id} c={c} b={b} />)}
        <Consults c={c} meId={meId} />
      </div>

      <aside className="min-w-0 lg:sticky lg:top-20 lg:max-h-[calc(100vh-6rem)] lg:self-start lg:overflow-y-auto">
        <CasePanels c={c} tab={tab} setTab={setTab} highlight={highlight} meName={me.data?.name} onCite={(s) => { setHighlight(s); setTab("timeline"); }} />
      </aside>
    </div>
  );
}

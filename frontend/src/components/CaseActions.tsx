/* Sticky action bar and its dialogs. Every button reads `actions` from the server (R1-R3 live there). */
import { useEffect, useState } from "react";
import { ArrowRightLeft, Building2, CheckCircle2, MessageCircle, Phone, Stethoscope } from "lucide-react";
import { useCommand, useDirectory, useReferralOptions, now } from "../lib/api";
import { label, OUTCOME_LABELS, ROLE_LABELS, shortName } from "../lib/labels";
import type { Allowed, Case } from "../lib/types";
import Composer from "./Composer";
import { Button, Dialog, Field, Source, Tag, cx, inputCls, toastError, useToast } from "./ui";

function Blocked({ a }: { a: Allowed }) {
  if (a.allowed) return null;
  return <p className="text-[12px] text-muted" title={a.code}>{a.message}</p>;
}

export function CloseDialog({ c, open, onOpenChange, meName, meRole }: { c: Case; open: boolean; onOpenChange: (o: boolean) => void; meName?: string; meRole?: string }) {
  const [outcome, setOutcome] = useState<string | null>(null);
  const [evidence, setEvidence] = useState("");
  const [reason, setReason] = useState("");
  const [err, setErr] = useState<{ code: string; message: string } | null>(null);
  const cmd = useCommand();
  const toast = useToast();
  useEffect(() => { if (open) { setOutcome(null); setEvidence(""); setReason(""); setErr(null); } }, [open]);
  const opt = c.actions.close.find((o) => o.outcome === outcome);
  const needs = opt?.requires ?? [];
  const ready = !!opt?.allowed && (!needs.includes("evidence_ref") || evidence.trim()) && (!needs.includes("reason") || reason.trim());

  const tryClose = (o: string, body: Record<string, string>) => {
    setErr(null);
    cmd.mutate({ path: `/v1/cases/${c.id}/close`, body: { outcome: o, ...body } }, {
      onSuccess: () => { toast({ tone: "done", text: `Case closed as “${label(OUTCOME_LABELS, o)}”. Written to the audit log.` }); onOpenChange(false); },
      onError: (e) => { if (e.code === "DEMO_NOT_RECORDED") toastError(toast, e); setErr({ code: e.code, message: e.message }); },
    });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange} wide title="Close this case" description="A case closes only with an allowed outcome and the evidence or signed decision it needs (R3).">
      <fieldset className="space-y-2">
        <legend className="sr-only">Outcome</legend>
        {c.actions.close.map((o) => (
          <label key={o.outcome} className={cx("press-wide flex cursor-pointer items-start gap-3 rounded border p-3", outcome === o.outcome ? "border-biro bg-biro-wash" : "border-rule-strong bg-sheet hover:bg-sheet-2")}>
            <input type="radio" name="outcome" className="mt-1 h-4 w-4 accent-[var(--biro)]" checked={outcome === o.outcome} onChange={() => { setOutcome(o.outcome); setErr(null); }} />
            <span className="flex-1">
              <span className="flex flex-wrap items-center gap-2"><span className="font-semibold">{label(OUTCOME_LABELS, o.outcome)}</span>{["COMPLETED_WITH_REPORT", "COMPLETED_ELSEWHERE"].includes(o.outcome) && <Tag tone="done">Counts as care completed</Tag>}</span>
              {o.allowed ? <span className="block text-[13px] text-ink-2">{o.requires.length ? `Needs: ${o.requires.map((r) => (r === "evidence_ref" ? "an evidence reference" : "a clinical reason")).join(" and ")}` : "Evidence already on file."}</span>
                : <span className="mt-1 flex flex-wrap items-center gap-2 text-[13px] text-stop"><span title={o.code}><Source kind="rule" /></span><span>{o.message}</span></span>}
            </span>
          </label>
        ))}
      </fieldset>
      {opt && !opt.allowed && (
        <div className="reveal mt-4 rounded border border-attn bg-attn-wash p-3 text-[14px]">
          <p className="text-attn">The rules block this outcome. You can still try: the server will refuse it and say why.</p>
          <Button className="mt-2" size="sm" onClick={() => tryClose(opt.outcome, {})}>Try to close anyway</Button>
          {err && <p role="alert" className="reveal mt-3 border-t border-attn pt-3 text-stop"><span title={err.code}>Not allowed: {err.message}</span></p>}
        </div>
      )}
      {opt?.allowed && needs.length > 0 && (
        <div className="reveal mt-4 space-y-3">
          {needs.includes("evidence_ref") && (
            <Field label="Evidence reference" htmlFor="ev" required hint="A FHIR reference to the report or record, e.g. DiagnosticReport/dr-123">
              <input id="ev" className={cx(inputCls, "mono")} value={evidence} onChange={(e) => setEvidence(e.target.value)} />
            </Field>
          )}
          {needs.includes("reason") && (
            <Field label="Clinical reason" htmlFor="rs" required>
              <textarea id="rs" rows={3} className={inputCls} value={reason} onChange={(e) => setReason(e.target.value)} />
            </Field>
          )}
        </div>
      )}
      {err && opt?.allowed && <p role="alert" className="reveal mt-4 rounded border border-stop bg-stop-wash p-3 text-[14px] text-stop"><span title={err.code}>{err.message}</span></p>}
      <div className="mt-6 flex flex-wrap items-end justify-between gap-4 border-t border-rule pt-4">
        <div>
          <p className="text-[12px] text-muted">Signing as</p>
          <p className="biro-underline inline-block text-[15px] font-semibold">{shortName(meName)}, {label(ROLE_LABELS, meRole).toLowerCase()}</p>
          <p className="mono mt-1 text-[11px] text-muted">{now().toISOString().slice(0, 16).replace("T", " ")} UTC · written to the audit log (R6)</p>
        </div>
        <div className="flex gap-2">
          <Button variant="quiet" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button variant="primary" disabled={!ready || cmd.isPending} onClick={() => opt && tryClose(opt.outcome, { ...(needs.includes("evidence_ref") ? { evidence_ref: evidence } : {}), ...(needs.includes("reason") ? { reason } : {}) })}>
            <CheckCircle2 size={16} aria-hidden />Close case
          </Button>
        </div>
      </div>
    </Dialog>
  );
}

export default function CaseActions({ c, meId, meName, meRole, closeOpen, setCloseOpen }: { c: Case; meId: string; meName?: string; meRole?: string; closeOpen: boolean; setCloseOpen: (o: boolean) => void }) {
  const [dlg, setDlg] = useState<null | "contact" | "message" | "handoff" | "consult" | "referral" | "decline">(null);
  const [more, setMore] = useState(false);
  // The decision bar's primary button opens the matching dialog here (one source of truth for the dialogs).
  useEffect(() => {
    const on = (e: Event) => {
      const d = (e as CustomEvent<string | { name: string; q?: string }>).detail;
      const name = typeof d === "string" ? d : d.name;
      if (name === "close") { setCloseOpen(true); return; }
      setF(typeof d === "string" ? {} : { q: d.q ?? "" });
      setDlg(name as typeof dlg);
    };
    window.addEventListener("tasleem:action", on);
    return () => window.removeEventListener("tasleem:action", on);
  }, [setCloseOpen]);
  const cmd = useCommand();
  const toast = useToast();
  const dir = useDirectory();
  const refs = useReferralOptions(c.id);
  const [f, setF] = useState<Record<string, string>>({});
  const set = (k: string, v: string) => setF((x) => ({ ...x, [k]: v }));
  const open = (d: typeof dlg) => { setF({}); setDlg(d); };
  const run = (path: string, body: unknown, done: string) => cmd.mutate({ path, body }, {
    onSuccess: () => { toast({ tone: "done", text: done }); setDlg(null); },
    onError: (e) => toastError(toast, e),
  });
  const a = c.actions;
  const isTarget = c.pending_handoff?.to_id === meId;
  const closed = c.status !== "open";

  if (closed) return <div className="rounded border border-rule bg-sheet-2 p-3 text-[14px] text-ink-2">This case is closed. The record stays in the audit log.</div>;

  return (
    <>
      <div className="rounded border border-rule bg-sheet px-3 py-3" role="group" aria-label="Case actions">
        <div className="flex flex-wrap gap-2">
          {isTarget ? (
            <>
              <Button variant="primary" disabled={!a.accept_handoff.allowed || cmd.isPending} onClick={() => run(`/v1/cases/${c.id}/handoff/accept`, {}, "Handoff accepted. You are now the owner.")}>Accept handoff</Button>
              <Button variant="danger" disabled={!a.reject_handoff.allowed} onClick={() => open("decline")}>Decline</Button>
            </>
          ) : null}
          <Button disabled={!a.log_contact.allowed} onClick={() => open("contact")} title={a.log_contact.message}><Phone size={16} aria-hidden />Log contact</Button>
          <Button disabled={!a.message_patient.allowed} onClick={() => open("message")} title={a.message_patient.message}><MessageCircle size={16} aria-hidden />Message patient</Button>
          <Button disabled={!a.request_consult.allowed} onClick={() => open("consult")} title={a.request_consult.message}><Stethoscope size={16} aria-hidden />E-consult</Button>
          <Button variant="quiet" aria-expanded={more} onClick={() => setMore((m) => !m)}>{more ? "Less" : "More…"}</Button>
          {more && <>
            <Button className="reveal" disabled={!a.offer_handoff.allowed} onClick={() => open("handoff")} title={a.offer_handoff.message}><ArrowRightLeft size={16} aria-hidden />Hand off</Button>
            <Button className="reveal" onClick={() => open("referral")}><Building2 size={16} aria-hidden />Referral options</Button>
          </>}
          <Button variant="secondary" className="ms-auto border-ink" onClick={() => setCloseOpen(true)}><CheckCircle2 size={16} aria-hidden />Close case…</Button>
        </div>
        {more && !a.offer_handoff.allowed && <Blocked a={a.offer_handoff} />}
      </div>

      <CloseDialog c={c} open={closeOpen} onOpenChange={setCloseOpen} meName={meName} meRole={meRole} />

      <Dialog open={dlg === "contact"} onOpenChange={(o) => !o && setDlg(null)} title="Log a contact attempt" description="Three attempts and one escalation are needed before a case can close as unreachable (R3).">
        <div className="space-y-4">
          <Field label="Channel" htmlFor="ch"><select id="ch" className={inputCls} value={f.channel ?? "phone"} onChange={(e) => set("channel", e.target.value)}>{["phone", "sms", "sahatna", "whatsapp", "in_person", "email"].map((x) => <option key={x} value={x}>{x.replace("_", " ")}</option>)}</select></Field>
          <Field label="Result" htmlFor="rs2"><select id="rs2" className={inputCls} value={f.result ?? "no_answer"} onChange={(e) => set("result", e.target.value)}>{["reached", "no_answer", "wrong_number", "left_message", "declined"].map((x) => <option key={x} value={x}>{x.replace("_", " ")}</option>)}</select></Field>
          <div className="flex justify-end gap-2"><Button variant="quiet" onClick={() => setDlg(null)}>Cancel</Button><Button variant="primary" disabled={cmd.isPending} onClick={() => run(`/v1/cases/${c.id}/contact-attempts`, { channel: f.channel ?? "phone", result: f.result ?? "no_answer" }, "Contact attempt logged.")}>Log attempt</Button></div>
        </div>
      </Dialog>

      <Dialog open={dlg === "message"} onOpenChange={(o) => !o && setDlg(null)} title="Message the patient" description="Goes to the patient's Sahatna app. Nothing is sent until you press Send.">
        <Composer caseId={c.id} defaultLanguage={c.patient.language} meName={meName} onSent={() => setDlg(null)} />
      </Dialog>

      <Dialog open={dlg === "handoff"} onOpenChange={(o) => !o && setDlg(null)} title="Hand off this case" description="You stay owner until they accept (R2).">
        <div className="space-y-4">
          <Field label="To" htmlFor="to"><select id="to" className={inputCls} value={f.to ?? ""} onChange={(e) => set("to", e.target.value)}><option value="">Choose a person</option>{dir.data?.staff.filter((s) => s.id !== meId).map((s) => <option key={s.id} value={s.id}>{shortName(s.name)} · {label(ROLE_LABELS, s.role)}</option>)}</select></Field>
          <Field label="Reason" htmlFor="hr" required><textarea id="hr" rows={3} className={inputCls} value={f.reason ?? ""} onChange={(e) => set("reason", e.target.value)} /></Field>
          <div className="flex justify-end gap-2"><Button variant="quiet" onClick={() => setDlg(null)}>Cancel</Button><Button variant="primary" disabled={!f.to || !f.reason?.trim() || cmd.isPending} onClick={() => run(`/v1/cases/${c.id}/handoff`, { to: f.to, reason: f.reason }, "Handoff offered. You stay owner until they accept.")}>Offer handoff</Button></div>
        </div>
      </Dialog>

      <Dialog open={dlg === "decline"} onOpenChange={(o) => !o && setDlg(null)} title="Decline the handoff" description="The sender stays owner and is told why.">
        <div className="space-y-4">
          <Field label="Reason" htmlFor="dr"><select id="dr" className={inputCls} value={f.code ?? "NOT_MY_CATCHMENT"} onChange={(e) => set("code", e.target.value)}>{["NOT_MY_CATCHMENT", "CAPACITY", "WRONG_SPECIALTY", "OTHER"].map((x) => <option key={x} value={x}>{x.toLowerCase().replace(/_/g, " ")}</option>)}</select></Field>
          <div className="flex justify-end gap-2"><Button variant="quiet" onClick={() => setDlg(null)}>Cancel</Button><Button variant="danger" disabled={cmd.isPending} onClick={() => run(`/v1/cases/${c.id}/handoff/reject`, { reason_code: f.code ?? "NOT_MY_CATCHMENT" }, "Handoff declined. The sender stays owner.")}>Decline handoff</Button></div>
        </div>
      </Dialog>

      <Dialog open={dlg === "consult"} onOpenChange={(o) => !o && setDlg(null)} title="Ask a GI specialist" description="An e-consult goes to the specialist's EMR inbox with a due date.">
        <div className="space-y-4">
          <Field label="Specialist" htmlFor="sp"><select id="sp" className={inputCls} value={f.to ?? ""} onChange={(e) => set("to", e.target.value)}><option value="">Choose a specialist</option>{dir.data?.staff.filter((s) => s.role === "gi_specialist").map((s) => <option key={s.id} value={s.id}>{shortName(s.name)}</option>)}</select></Field>
          <Field label="Question" htmlFor="qq" required><textarea id="qq" rows={3} className={inputCls} value={f.q ?? ""} onChange={(e) => set("q", e.target.value)} placeholder="Referral shows completed but no report. Was the colonoscopy done?" /></Field>
          <div className="flex justify-end gap-2"><Button variant="quiet" onClick={() => setDlg(null)}>Cancel</Button><Button variant="primary" disabled={!f.to || !f.q?.trim() || cmd.isPending} onClick={() => run(`/v1/cases/${c.id}/consults`, { to: f.to, question: f.q }, `E-consult sent to ${shortName(dir.data?.staff.find((s) => s.id === f.to)?.name)}.`)}>Send question</Button></div>
        </div>
      </Dialog>

      <Dialog open={dlg === "referral"} onOpenChange={(o) => !o && setDlg(null)} title="Referral options" description={`Services that accept the patient's ${c.patient.insurance_network ?? ""} network.`}>
        {refs.data?.prefer_female && <p className="mb-3 rounded border border-biro bg-biro-wash px-3 py-2 text-[14px]">The patient asked for a female doctor. Centres with a female endoscopist are listed first.</p>}
        <ul className="space-y-2">
          {(refs.data?.options ?? []).map((o: { org_id: string; name: string; in_network: boolean; networks: string[]; female_endoscopist?: boolean }) => (
            <li key={o.org_id} className="flex items-center justify-between gap-3 rounded border border-rule p-3">
              <span><span className="block font-semibold">{o.name}</span><span className="text-[13px] text-muted">Accepts {o.networks.join(", ")}</span></span>
              <span className="flex flex-wrap justify-end gap-1.5">
                {o.female_endoscopist && <Tag tone="biro">Female endoscopist</Tag>}
                {o.in_network ? <Tag tone="done">In network</Tag> : <Tag tone="attn">Out of network</Tag>}
              </span>
            </li>
          ))}
          {refs.data && !refs.data.options?.length && <li className="text-ink-2">No other services on record for this pathway.</li>}
        </ul>
      </Dialog>
    </>
  );
}

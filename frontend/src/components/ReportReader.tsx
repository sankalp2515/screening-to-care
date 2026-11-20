import { useEffect, useMemo, useState } from "react";
import { Check, FileText, Sparkles } from "lucide-react";
import { request, useCommand } from "../lib/api";
import { usePersona } from "../lib/persona";
import { exactTime, modelLabel, relTime, shortName } from "../lib/labels";
import type { Case, ReportFieldReading, ReportReview } from "../lib/types";
import { Button, Card, Source, Tag, cx, toastError, useToast } from "./ui";

/**
 * Evidence Reader card: a free-text colonoscopy report, what the AI read from it (each value quoting its
 * sentence), and the clinician's one-click confirmation. Rules act only on confirmed findings (R3, R5).
 *
 * Props: `c` the case (from GET /v1/cases/{id}), `r` one of `c.reports`.
 * Reading source, in order: the agent's model reading (verbatim quotes enforced server-side), else the
 * deterministic keyword reading case-core always includes. The clinician can correct any field before confirming;
 * corrections are recorded so AI accuracy is measured from the audit log.
 */

type Value = boolean | number | string | null;
const ORDER = ["completed", "prep_adequate", "polyps_removed", "pathology_pending", "next_step", "follow_up"] as const;
const BOOL_FIELDS = new Set(["completed", "prep_adequate", "pathology_pending"]);

function show(field: string, v: Value): string {
  if (v === null || v === undefined || v === "") return "Not stated";
  if (BOOL_FIELDS.has(field)) return v ? "Yes" : "No";
  return String(v);
}

/** Is this value one that keeps the loop open? Used to colour it. */
function worrying(field: string, v: Value): boolean {
  return (field === "completed" && v === false) || (field === "prep_adequate" && v === false) || (field === "pathology_pending" && v === true);
}

/** Highlight each quoted sentence inside the report text. Quotes are verbatim, so a plain search is enough. */
function Highlighted({ text, quotes, active }: { text: string; quotes: { field: string; quote: string }[]; active: string | null }) {
  const parts = useMemo(() => {
    const spans: { start: number; end: number; field: string }[] = [];
    for (const q of quotes) {
      const i = text.indexOf(q.quote);
      if (i >= 0 && !spans.some((s) => i < s.end && i + q.quote.length > s.start)) spans.push({ start: i, end: i + q.quote.length, field: q.field });
    }
    spans.sort((a, b) => a.start - b.start);
    const out: { text: string; field?: string }[] = [];
    let at = 0;
    for (const s of spans) { if (s.start > at) out.push({ text: text.slice(at, s.start) }); out.push({ text: text.slice(s.start, s.end), field: s.field }); at = s.end; }
    if (at < text.length) out.push({ text: text.slice(at) });
    return out;
  }, [text, quotes]);
  const ar = /[؀-ۿ]/.test(text);
  return (
    <p dir={ar ? "rtl" : "ltr"} lang={ar ? "ar" : "en"} className="rounded border border-rule bg-sheet-2 p-3 text-[15px] leading-[26px]">
      {parts.map((p, i) => p.field
        ? <mark key={i} data-field={p.field} className={cx("rounded-sm px-0.5 text-ink underline decoration-ai decoration-2 underline-offset-4 transition-colors duration-150", p.field === active ? "bg-ai/20" : "bg-transparent")}>{p.text}</mark>
        : <span key={i}>{p.text}</span>)}
    </p>
  );
}

function FieldInput({ field, value, onChange }: { field: string; value: Value; onChange: (v: Value) => void }) {
  if (BOOL_FIELDS.has(field)) {
    return (
      <div role="radiogroup" aria-label="Value" className="inline-flex overflow-hidden rounded border border-rule-strong text-[13px]">
        {([[true, "Yes"], [false, "No"], [null, "Not stated"]] as const).map(([v, l]) => (
          <button key={l} type="button" role="radio" aria-checked={value === v} onClick={() => onChange(v)}
            className={cx("px-2.5 py-1 transition-colors duration-150", value === v ? "bg-ink text-sheet" : "bg-sheet hover:bg-sheet-2")}>{l}</button>
        ))}
      </div>
    );
  }
  if (field === "polyps_removed") {
    return <input type="number" min={0} max={50} aria-label="Number of polyps removed" className="h-8 w-20 rounded border border-rule-strong bg-sheet px-2 text-[14px]"
      value={value === null ? "" : String(value)} onChange={(e) => onChange(e.target.value === "" ? null : Math.max(0, Math.floor(Number(e.target.value))))} />;
  }
  return <input aria-label="Value" className="h-8 w-full min-w-0 rounded border border-rule-strong bg-sheet px-2 text-[14px]"
    value={value === null ? "" : String(value)} onChange={(e) => onChange(e.target.value || null)} />;
}

export default function ReportReader({ c, r }: { c: Case; r: ReportReview }) {
  const { persona } = usePersona();
  const cmd = useCommand();
  const toast = useToast();
  const allowed = c.actions.reports?.[r.id];
  const [reading, setReading] = useState<{ reader: string; fields: Record<string, ReportFieldReading>; ai: boolean } | null>(null);
  const [values, setValues] = useState<Record<string, Value>>({});
  const [editing, setEditing] = useState(false);
  const [compare, setCompare] = useState(false);
  const [drafting, setDrafting] = useState(false);
  const rulesOnly = r.keyword_reading.fields;
  const rulesRead = ORDER.filter((f) => rulesOnly[f]?.value !== null && rulesOnly[f]?.value !== undefined).length;
  // After an incomplete colonoscopy is confirmed, the agent drafts the rebook request to the GI centre; it opens in
  // the e-consult form for the physician to edit and send (nothing is sent by the agent).
  const draftRebook = async () => {
    setDrafting(true);
    try {
      const d = await request("agent", "POST", `/v1/cases/${c.id}/reports/${r.id}/rebook-draft`, {}, persona!);
      window.dispatchEvent(new CustomEvent("tasleem:action", { detail: { name: "consult", q: d.text } }));
    } catch (e) { toastError(toast, e as Parameters<typeof toastError>[1]); } finally { setDrafting(false); }
  };
  const [active, setActive] = useState<string | null>(null);

  // Ask the agent for a model reading; fall back to case-core's keyword reading (always present, deterministic).
  useEffect(() => {
    if (r.reviewed) return;
    let live = true;
    const fallback = { reader: r.keyword_reading.reader, fields: r.keyword_reading.fields, ai: false };
    request("agent", "POST", `/v1/cases/${c.id}/reports/${r.id}/reading`, {}, persona!)
      .then((res) => { if (live) setReading(res?.available ? { reader: res.reader, fields: res.fields, ai: true } : fallback); })
      .catch(() => { if (live) setReading(fallback); });
    return () => { live = false; };
  }, [c.id, r.id, r.reviewed, persona, r.keyword_reading]);

  useEffect(() => {
    if (reading) setValues(Object.fromEntries(ORDER.map((f) => [f, (reading.fields[f]?.value ?? null) as Value])));
  }, [reading]);

  const confirmed = r.reviewed ? r.findings ?? {} : null;
  const quotes = useMemo(() => {
    const src = reading?.fields ?? (r.reviewed ? r.keyword_reading.fields : {});
    return ORDER.flatMap((f) => (src[f]?.quote ? [{ field: f, quote: src[f]!.quote! }] : []));
  }, [reading, r.reviewed, r.keyword_reading]);
  const suggestion = reading ? Object.fromEntries(ORDER.map((f) => [f, (reading.fields[f]?.value ?? null) as Value])) : null;
  const changed = suggestion ? ORDER.filter((f) => suggestion[f] !== values[f]) : [];

  const confirm = () => cmd.mutate(
    { path: `/v1/cases/${c.id}/reports/${r.id}/review`, body: { findings: values, suggested_by: reading?.reader, suggestion } },
    {
      onSuccess: () => toast({ tone: "done", text: worrying("completed", values.completed) || worrying("prep_adequate", values.prep_adequate) ? "Findings confirmed. The case stays open: the colonoscopy must be rebooked." : worrying("pathology_pending", values.pathology_pending) ? "Findings confirmed. The case stays open until the pathology result arrives." : "Findings confirmed." }),
      onError: (e) => toastError(toast, e),
    },
  );

  return (
    <Card className="p-4" data-report aria-labelledby={`rpt-${r.id}`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 id={`rpt-${r.id}`} className="flex items-center gap-2 text-[16px] font-semibold"><FileText size={16} aria-hidden />Colonoscopy report</h3>
        <span className="text-[12px] text-muted" title={exactTime(r.received_at)}>Arrived {relTime(r.received_at)} from the GI centre</span>
      </div>
      <p className="mt-1 text-[13px] text-ink-2">A report arriving does not close the loop. What it says does.</p>

      <div className="mt-3"><Highlighted text={r.text} quotes={quotes} active={active} /></div>

      {confirmed ? (
        <div className="reveal mt-4 rounded border border-rule-strong bg-sheet-2 p-3">
          <p className="flex flex-wrap items-center gap-2 text-[14px]"><Source kind="human">{shortName(r.reviewed_by)} confirmed</Source>
            <span className="text-[12px] text-muted">read by {r.suggested_by ? modelLabel(r.suggested_by) : "a person"}{r.corrected.length > 0 ? `, ${r.corrected.length} field${r.corrected.length > 1 ? "s" : ""} corrected` : ", accepted unchanged"}</span></p>
          <dl className="mt-3 grid gap-x-4 gap-y-1.5 text-[14px] sm:grid-cols-2">
            {ORDER.map((f) => (
              <div key={f} className="flex min-w-0 justify-between gap-3 border-b border-rule py-1">
                <dt className="text-ink-2">{r.field_labels[f]}</dt>
                <dd className={cx("text-end font-semibold", worrying(f, confirmed[f] as Value) && "text-stop")}>{show(f, confirmed[f] as Value)}</dd>
              </div>
            ))}
          </dl>
          {(worrying("completed", confirmed.completed as Value) || worrying("prep_adequate", confirmed.prep_adequate as Value)) && c.status === "open" && (
            <div className="mt-3 flex flex-wrap items-center gap-3 border-t border-rule pt-3">
              <Button variant="secondary" disabled={drafting} onClick={() => void draftRebook()}><Sparkles size={16} className="text-ai" aria-hidden />{drafting ? "Drafting…" : "Draft the rebook request"}</Button>
              <span className="text-[12px] text-muted">The AI writes it from the report; you edit and send it as an e-consult.</span>
            </div>
          )}
        </div>
      ) : !reading ? (
        <p className="mt-4 flex items-center gap-2 text-[14px] text-ai" aria-live="polite"><Sparkles size={16} aria-hidden />Reading the report…</p>
      ) : (
        <div className="mt-4 rounded border border-dashed border-ai bg-ai-wash p-3">
          <p className="flex flex-wrap items-center gap-2 text-[14px]">
            <Sparkles size={16} className="text-ai" aria-hidden />
            <span className="font-semibold text-ai">{reading.ai ? "AI read this report" : "Read by the keyword reader"} · a physician must confirm</span>
            <span className="text-[12px] text-muted">{modelLabel(reading.reader)}</span>
          </p>
          <p className="mt-1 text-[12px] text-muted">Each value quotes the sentence it came from. Hover a row to see it in the report. Nothing changes on the case until you confirm.</p>
          {reading.ai && (
            <label className="mt-2 inline-flex cursor-pointer items-center gap-2 text-[13px] text-ink-2">
              <input type="checkbox" checked={compare} onChange={(e) => setCompare(e.target.checked)} className="h-4 w-4 accent-[var(--color-accent)]" />
              Compare with rules only {compare && <span className="text-muted">: keyword rules read {rulesRead} of 6 findings from this report</span>}
            </label>
          )}
          <ul className="mt-3 divide-y divide-rule rounded border border-rule bg-sheet">
            {ORDER.map((f) => {
              const q = reading.fields[f]?.quote;
              return (
                <li key={f} className={cx("grid gap-1 px-3 py-2", BOOL_FIELDS.has(f) || f === "polyps_removed" ? "sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center" : "")} onMouseEnter={() => setActive(f)} onMouseLeave={() => setActive(null)} onFocus={() => setActive(f)}>
                  <div className="min-w-0">
                    <p className="text-[14px] font-medium">{r.field_labels[f]}</p>
                    {compare && <p className={cx("text-[12px]", rulesOnly[f]?.value === null || rulesOnly[f]?.value === undefined ? "text-stop" : "text-muted")}>Rules only: {show(f, (rulesOnly[f]?.value ?? null) as Value)}</p>}
                    {(BOOL_FIELDS.has(f) || f === "polyps_removed" || !values[f]) && <p className="truncate text-[12px] text-muted" title={q ?? undefined}>{q ? `“${q}”` : "The report does not say. Read it and decide."}</p>}
                  </div>
                  <div className={cx("flex items-center gap-2", (BOOL_FIELDS.has(f) || f === "polyps_removed") && "sm:justify-end")}>
                    {editing ? <FieldInput field={f} value={values[f] ?? null} onChange={(v) => setValues((s) => ({ ...s, [f]: v }))} />
                      : <span className={cx("text-[14px] font-semibold", worrying(f, values[f] ?? null) && "text-stop", values[f] === null && "font-normal text-muted")}>{show(f, values[f] ?? null)}</span>}
                    {suggestion && suggestion[f] !== values[f] && <Tag tone="biro">changed</Tag>}
                  </div>
                </li>
              );
            })}
          </ul>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <Button variant="primary" disabled={!allowed?.allowed || cmd.isPending} onClick={confirm}>
              <Check size={16} aria-hidden />{changed.length ? `Confirm with ${changed.length} correction${changed.length > 1 ? "s" : ""}` : "Confirm findings"}
            </Button>
            <Button variant="quiet" onClick={() => setEditing((e) => !e)}>{editing ? "Done correcting" : "Correct a value"}</Button>
            {allowed && !allowed.allowed && <span className="text-[12px] text-muted">{allowed.code === "R3_SIGNATURE_REQUIRED" ? "Only a physician can confirm what a report says." : allowed.message}</span>}
          </div>
        </div>
      )}
    </Card>
  );
}

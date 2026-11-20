/* eslint-disable @typescript-eslint/no-explicit-any */
import * as Tabs from "@radix-ui/react-tabs";
import { useState } from "react";
import { Link } from "react-router-dom";
import { Bar, BarChart, Cell, LabelList, ResponsiveContainer, XAxis, YAxis } from "recharts";
import { CheckCircle2, Download, Lock, Sparkles } from "lucide-react";
import { MODE, request, useAiOversight, useChannels, useCommand, useDirectory, useMe, useMetrics, useUnmatched, useUsage } from "../lib/api";
import { usePersona } from "../lib/persona";
import type { ApiError } from "../lib/types";
import { BARRIER_LABELS, CHANNEL_LABELS, label, OUTCOME_LABELS, ORG_LABELS, ROLE_LABELS, STALL_LABELS, exactTime } from "../lib/labels";
import { BenchmarkChart, EVIDENCE_URL, StatTiles } from "../components/Benchmark";
import WhatsAppVision from "../components/WhatsAppVision";
import { Card, ErrorState, Skeleton, Tag, cx, toastError, useToast } from "../components/ui";

/** Axis labels on one line (Recharts' own wrapping glued words together: "discussresult"); long ones end in an
 * ellipsis with the full label in a tooltip. */
const PATHWAY_NAMES: Record<string, string> = {
  "fit-positive-colonoscopy": "Positive FIT to colonoscopy", "hba1c-diabetes-range": "HbA1c in diabetes range",
  "hypertension-screening": "Raised blood pressure", "obesity-screening": "Obesity screening",
};

function OneLineTick({ x, y, payload }: { x?: number; y?: number; payload?: { value: string } }) {
  const full = String(payload?.value ?? "");
  const text = full.length > 34 ? full.slice(0, 33).trimEnd() + "…" : full;
  return <text x={x} y={y} dy={4} textAnchor="end" fill="var(--ink-2)" fontSize={12} fontFamily="Instrument Sans, ui-sans-serif, sans-serif"><title>{full}</title>{text}</text>;
}

function HBar({ data, color = "var(--ink-2)", height }: { data: { name: string; v: number }[]; color?: string; height?: number }) {
  if (!data.length) return <p className="text-[14px] text-muted">Nothing to show.</p>;
  return (
    <div style={{ height: height ?? Math.max(80, data.length * 34) }} role="img" aria-label={data.map((d) => `${d.name}: ${d.v}`).join(", ")}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ top: 0, right: 40, bottom: 0, left: 0 }} barCategoryGap={8}>
          <XAxis type="number" hide allowDecimals={false} />
          <YAxis type="category" dataKey="name" width={230} tickLine={false} axisLine={false} tick={OneLineTick} />
          <Bar dataKey="v" radius={[0, 2, 2, 0]} isAnimationActive={false}>
            {data.map((d) => <Cell key={d.name} fill={color} />)}
            <LabelList dataKey="v" position="right" style={{ fill: "var(--ink)", fontSize: 12, fontFamily: "DM Mono, ui-monospace, monospace" }} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

const FILTERS = [["", "All"], ["org=org-ghaf", "Ghaf health centre"], ["org=org-samar", "Samar clinic"], ["language=ar", "Arabic"], ["language=en", "English"]];

const STATUS: Record<string, { text: string; tone: "stop" | "attn" | "done" }> = {
  below: { text: "Below the national target", tone: "attn" },
  acceptable: { text: "Meets the acceptable level", tone: "attn" },
  desirable: { text: "Meets the desirable level", tone: "done" },
};
const pct = (v: number) => `${Math.round(v * 100)}%`;

/** UAE national guideline indicators, counted from clinical evidence. Hidden when the API does not send them. */
function Guideline({ blocks }: { blocks?: any[] }) {
  const g = blocks?.[0];
  if (!g) return null;
  return (
    <Card className="p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-[16px] font-semibold">National guideline scorecard</h3>
        <span className="text-[12px] text-muted">Counted from clinical evidence, not referral status</span>
      </div>
      <div className="mt-3 grid gap-4 md:grid-cols-2">
        {g.targets.map((t: any) => {
          const st = t.status ? STATUS[t.status] : null;
          return (
            <div key={t.id} className="rounded border border-rule bg-sheet p-3">
              <p className="text-[14px] text-ink-2">{t.label}</p>
              <div className="mt-1 flex items-baseline gap-3">
                <p className="serif text-[34px] font-semibold leading-[40px] tnum">{t.rate == null ? "–" : pct(t.rate)}</p>
                {st && <Tag tone={st.tone}>{st.text}</Tag>}
              </div>
              <div className="relative mt-2 h-2 rounded-full bg-sheet-2" role="img" aria-label={`${t.rate == null ? "no data" : pct(t.rate)} against a target of ${pct(t.acceptable)} acceptable and ${pct(t.desirable)} desirable`}>
                <div className={cx("h-2 rounded-full", st?.tone === "done" ? "bg-done" : st?.tone === "attn" ? "bg-attn" : "bg-stop")} style={{ width: `${Math.round((t.rate ?? 0) * 100)}%` }} />
                <span className="absolute -top-1 h-4 w-px bg-ink" style={{ left: `${t.acceptable * 100}%` }} aria-hidden />
              </div>
              <p className="mt-2 text-[13px] text-muted tnum">
                {t.met} of {t.due} · target {pct(t.acceptable)} acceptable, above {pct(t.desirable)} desirable
                {t.pending ? ` · ${t.pending} still inside the ${t.window_working_days}-working-day window` : ""}
              </p>
            </div>
          );
        })}
      </div>
      <p className="mt-3 text-[12px] text-muted">{g.source}, Appendix 2. Working days are Monday to Friday; public holidays are not counted.</p>
    </Card>
  );
}

/** One row per case, pseudonymous ids only (TSL-182). */
function ExportCsv() {
  const { persona } = usePersona();
  const toast = useToast();
  const download = async () => {
    try {
      const csv = await request<string>("core", "GET", "/v1/program/export.csv", undefined, persona!);
      const url = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
      const a = document.createElement("a");
      a.href = url; a.download = "tasleem-programme.csv"; a.click();
      URL.revokeObjectURL(url);
    } catch (e) { toastError(toast, e as ApiError); }
  };
  return <button type="button" onClick={download} className="press ms-auto inline-flex h-9 items-center gap-2 rounded border border-rule-strong bg-sheet px-3 text-[14px] font-medium text-ink-2 hover:bg-sheet-2"><Download size={15} aria-hidden />Download CSV</button>;
}

/** TSL-161: messages for a patient Tasleem does not know. None is dropped; each waits for a person. */
function Unmatched() {
  const q = useUnmatched();
  const people = useDirectory();
  const cmd = useCommand();
  const toast = useToast();
  const [pick, setPick] = useState<Record<number, string>>({});
  if (MODE !== "live") return <p className="text-ink-2">The unmatched queue needs the live API.</p>;
  if (q.isLoading) return <Skeleton className="h-40" />;
  if (q.error) return <ErrorState error={q.error} />;
  const resolve = (id: number, action: "match" | "dismiss") => cmd.mutate(
    { path: `/v1/integration/unmatched/${id}/resolve`, body: action === "match" ? { action, patient_id: pick[id] } : { action } },
    { onSuccess: (r: any) => toast({ tone: "done", text: action === "match" ? `Matched. ${r.effects?.some((e: any) => e.effect === "opened") ? "A case opened with a named owner." : "Applied to the patient's case."}` : "Dismissed and recorded." }),
      onError: (e) => toastError(toast, e) });
  return (
    <div className="space-y-4">
      <p className="text-ink-2">Results and messages for a record number Tasleem cannot match to a patient. They are stored on arrival and never dropped; match each one to a patient, or dismiss it. Every decision is recorded.</p>
      {!q.data.items.length && <Card className="p-6 text-ink-2">Nothing waiting. Every message matched a patient.</Card>}
      {q.data.items.map((m: any) => (
        <Card key={m.id} className="space-y-3 p-4">
          <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
            <p className="font-semibold">{m.signals.map((s: any) => `${s.kind === "LAB_RESULT" ? "Lab result" : s.kind} ${s.codes.join(", ")}${s.interpretation?.length ? ` (${s.interpretation.join(", ")})` : ""}`).join(" · ")}</p>
            <span className="mono text-[13px] text-muted">record {m.patient_ref}</span>
            <span className="text-[13px] text-muted">from {m.source} · {exactTime(m.received_at)}</span>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <label className="sr-only" htmlFor={`pick-${m.id}`}>Patient</label>
            <select id={`pick-${m.id}`} className="h-9 rounded border border-rule-strong bg-sheet px-2 text-[14px]" value={pick[m.id] ?? ""} onChange={(e) => setPick({ ...pick, [m.id]: e.target.value })}>
              <option value="">Match to a patient…</option>
              {(people.data?.patients ?? []).map((p: any) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
            <button type="button" disabled={!pick[m.id] || cmd.isPending} onClick={() => resolve(m.id, "match")} className="press h-9 rounded bg-biro px-3 text-[14px] font-semibold text-white disabled:bg-rule-strong">Match</button>
            <button type="button" disabled={cmd.isPending} onClick={() => resolve(m.id, "dismiss")} className="press h-9 rounded border border-rule-strong bg-sheet px-3 text-[14px] font-medium text-ink-2">Dismiss</button>
          </div>
        </Card>
      ))}
    </div>
  );
}

function Measures() {
  const [filter, setFilter] = useState("");
  const m = useMetrics(filter);
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap gap-2" role="group" aria-label="Filter">
        {FILTERS.map(([v, l]) => (
          <button key={v} type="button" aria-pressed={filter === v} onClick={() => setFilter(v)} className={cx("press h-9 rounded border px-3 text-[14px] font-medium", filter === v ? "border-biro bg-biro-wash text-biro-ink" : "border-rule-strong bg-sheet text-ink-2 hover:bg-sheet-2")}>{l}</button>
        ))}
        <span className="self-center text-[12px] text-muted">One filter at a time in the demo.</span>
        {MODE === "live" && <ExportCsv />}
      </div>
      {m.isLoading ? <Skeleton className="h-64" /> : m.error ? <ErrorState error={m.error} /> : (() => {
        const x = m.data;
        return (
          <>
            <div className="grid gap-px overflow-hidden rounded border border-rule bg-rule sm:grid-cols-2 lg:grid-cols-4">
              <div className="bg-sheet p-4 sm:col-span-2">
                <p className="text-[13px] text-ink-2">Malaffi says completed <span className="text-muted">vs</span> verified complete</p>
                <p className="serif mt-1 text-[40px] font-semibold leading-[44px] tnum"><span className="text-muted">{x.referral_status_says_completed}</span> <span className="text-[22px] text-muted">vs</span> <span className="text-done">{x.verified_complete}</span></p>
                <p className="mt-1 text-[13px] text-muted">The gap is care reported but not proven.</p>
              </div>
              <div className="bg-sheet p-4">
                <p className="text-[13px] text-ink-2">False “done” found</p>
                <p className="serif mt-1 text-[40px] font-semibold leading-[44px] text-attn tnum">{x.false_done.count}</p>
                <div className="mt-1 flex flex-wrap gap-2 text-[13px]">{x.false_done.case_ids.map((id: string, i: number) => <Link key={id} to={`/app/cases/${id}`} title={id} className="text-biro underline underline-offset-2">Open case {x.false_done.case_ids.length > 1 ? i + 1 : ""}</Link>)}</div>
              </div>
              <div className="bg-sheet p-4">
                <p className="text-[13px] text-ink-2">Open cases</p>
                <p className="serif mt-1 text-[40px] font-semibold leading-[44px] tnum">{x.cases.open}</p>
                <p className="mt-1 text-[13px] text-muted">{x.cases.closed} closed of {x.cases.total}</p>
              </div>
              <div className="bg-sheet p-4">
                <p className="text-[13px] text-ink-2">Cases without an owner</p>
                <p className="serif mt-1 flex items-center gap-2 text-[40px] font-semibold leading-[44px] tnum">{x.open_cases_without_owner}{x.open_cases_without_owner === 0 && <CheckCircle2 className="text-done" size={26} aria-label="None" />}</p>
                <p className="mt-1 text-[13px] text-muted">R1 holds when this is zero.</p>
              </div>
              <div className="bg-sheet p-4">
                <p className="text-[13px] text-ink-2">Open distress</p>
                <p className={cx("serif mt-1 text-[40px] font-semibold leading-[44px] tnum", x.open_distress > 0 && "text-stop")}>{x.open_distress}</p>
              </div>
              <div className="bg-sheet p-4 sm:col-span-2">
                <p className="text-[13px] text-ink-2">Median days, result to procedure</p>
                <p className="serif mt-1 text-[40px] font-semibold leading-[44px] tnum">{x.median_days_result_to_procedure ?? "–"}</p>
              </div>
            </div>
            <Guideline blocks={x.guideline} />
            <div className="grid gap-6 lg:grid-cols-2">
              {Object.entries<any>(x.by_pathway).map(([id, p]) => (
                <Card key={id} className="p-4">
                  <h3 className="text-[16px] font-semibold">{p.name} <span className="font-normal text-muted">· {p.cases} {p.cases === 1 ? "case" : "cases"}</span></h3>
                  <p className="mb-3 text-[13px] text-muted">Verified on clinical evidence at each step</p>
                  <HBar data={p.funnel.map((f: any) => ({ name: f.label, v: f.count }))} color="var(--done)" />
                </Card>
              ))}
              <Card className="p-4">
                <h3 className="mb-3 text-[16px] font-semibold">Open stalls by reason</h3>
                <HBar data={Object.entries<number>(x.open_stalls_by_reason).map(([k, v]) => ({ name: label(STALL_LABELS, k), v }))} color="var(--attn)" />
              </Card>
              <Card className="p-4">
                <h3 className="mb-3 text-[16px] font-semibold">Barriers patients reported (confirmed)</h3>
                <HBar data={Object.entries<number>(x.barriers_by_code).map(([k, v]) => ({ name: label(BARRIER_LABELS, k), v }))} />
              </Card>
              <Card className="p-4">
                <h3 className="mb-3 text-[16px] font-semibold">Outcomes of closed cases</h3>
                <HBar data={Object.entries<number>(x.outcomes).map(([k, v]) => ({ name: label(OUTCOME_LABELS, k), v }))} />
              </Card>
            </div>
            <p className="text-[12px] text-muted">As of {exactTime(new Date((typeof x.as_of === "number" ? x.as_of * 1000 : x.as_of)).toISOString())}. Computed by rules from recorded events.</p>
          </>
        );
      })()}
    </div>
  );
}

function Channels() {
  const ch = useChannels();
  if (ch.isLoading) return <Skeleton className="h-48" />;
  if (ch.error) return <ErrorState error={ch.error} />;
  const x = ch.data;
  const pad = (n: number) => String(n).padStart(2, "0") + ":00";
  const steps = (s: any[] | null) => (s?.length ? s.map((r) => `${CHANNEL_LABELS[r.channel] ?? r.channel}${r.wait_hours ? ` (wait ${r.wait_hours}h)` : ""}`).join(" → ") : "–");
  return (
    <div className="space-y-4">
      <p className="text-ink-2">Patients never receive clinical content by SMS. Clinicians get tasks in the EMR inbox they already use.</p>
      <Card className="overflow-x-auto">
        <table className="w-full text-[14px]">
          <thead className="bg-sheet-2 text-[12px] text-muted"><tr>{["Recipient", "Routine", "Urgent", "Quiet hours", "When all fail"].map((h) => <th key={h} className="px-4 py-2 text-start font-semibold">{h}</th>)}</tr></thead>
          <tbody className="divide-y divide-rule">
            {x.recipients.map((r: any) => (
              <tr key={r.recipient}>
                <td className="px-4 py-3 font-semibold">{label(ROLE_LABELS, r.recipient)}</td>
                <td className="px-4 py-3">{steps(r.routine)}</td>
                <td className="px-4 py-3">{steps(r.urgent)}</td>
                <td className="px-4 py-3 mono text-[13px]">{r.quiet_hours ? `${pad(x.quiet_hours.start)}–${pad(x.quiet_hours.end)} Gulf time` : "Not applied"}</td>
                <td className="px-4 py-3">{r.when_all_fail ? <Tag tone="attn">{r.when_all_fail.replace(/_/g, " ")}</Tag> : "–"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
      <WhatsAppVision compact />
    </div>
  );
}

function Usage() {
  const me = useMe();
  const u = useUsage();
  if (me.data && me.data.role !== "program_coordinator") return <p className="flex items-center gap-2 rounded border border-rule bg-sheet-2 p-4 text-ink-2"><Lock size={16} aria-hidden />Usage is visible to the programme coordinator only.</p>;
  if (u.isLoading) return <Skeleton className="h-40" />;
  if (u.error) return <ErrorState error={u.error} />;
  return (
    <div className="space-y-4">
      <p className="text-ink-2">Active cases for <span className="mono">{u.data.month}</span>. Billing unit: active case per month (pricing hypothesis).</p>
      <Card className="overflow-x-auto">
        <table className="w-full text-[14px]">
          <thead className="bg-sheet-2 text-[12px] text-muted"><tr><th className="px-4 py-2 text-start font-semibold">Provider</th><th className="px-4 py-2 text-start font-semibold">By pathway</th><th className="px-4 py-2 text-end font-semibold">Active cases</th></tr></thead>
          <tbody className="divide-y divide-rule">
            {u.data.by_org.map((o: any) => (
              <tr key={o.org_id}><td className="px-4 py-3 font-semibold">{ORG_LABELS[o.org_id] ?? o.org_id}</td><td className="px-4 py-3 text-ink-2">{Object.entries(o.pathways).map(([k, v]) => `${PATHWAY_NAMES[k] ?? k.replace(/-/g, " ")}: ${v}`).join("; ")}</td><td className="mono px-4 py-3 text-end">{o.active_cases}</td></tr>
            ))}
            <tr className="bg-sheet-2"><td className="px-4 py-3 font-semibold">Total</td><td /><td className="mono px-4 py-3 text-end font-semibold">{u.data.active_cases}</td></tr>
          </tbody>
        </table>
      </Card>
    </div>
  );
}

/** A5: every AI suggestion and what a named person did with it, from the audit log. */
function AiAtWork() {
  const q = useAiOversight();
  if (q.isLoading) return <Skeleton className="h-40" />;
  if (q.error) return <ErrorState error={q.error} retry={() => q.refetch()} />;
  const items: any[] = q.data?.items ?? [];
  const pct = (v: number | null) => (v == null ? "–" : `${Math.round(v * 100)}%`);
  return (
    <div className="space-y-4">
      <p className="max-w-3xl text-ink-2">Where AI works in Tasleem, and how often people agreed with it. AI reads reports and replies and drafts messages; rules decide; a named person confirms every suggestion. A falling acceptance rate is the signal to retrain or switch a model off.</p>
      <div className="grid gap-4 md:grid-cols-3">
        {items.map((i) => (
          <Card key={i.kind} className="p-4">
            <p className="flex items-center gap-2 text-[13px] font-semibold text-ai"><Sparkles size={14} aria-hidden />{i.label}</p>
            <p className="mt-3 text-[32px] font-semibold leading-none tnum">{pct(i.acceptance_rate)}</p>
            <p className="mt-1 text-[13px] text-muted">accepted unchanged by a person</p>
            <dl className="mt-3 grid grid-cols-3 gap-2 text-[13px]">
              {[["Suggested", i.suggested], ["Accepted", i.accepted], ["Corrected", i.corrected]].map(([k, v]) => (
                <div key={k as string}><dt className="text-muted">{k}</dt><dd className="mono font-semibold">{v}</dd></div>
              ))}
            </dl>
            {Object.keys(i.models ?? {}).length > 0 && <p className="mt-3 truncate text-[12px] text-muted">Readers: <span className="mono">{Object.keys(i.models).join(", ")}</span></p>}
          </Card>
        ))}
      </div>
      <p className="text-[13px] text-muted">{q.data?.note} Evidence Reader accuracy on 28 labelled synthetic reports is in the repository (docs/evidence).</p>
    </div>
  );
}

function Benchmark() {
  const rows = [["Reminders only", "0.0%", "–", "–"], ["Malaffi status only", "81.8%", "16.5", "160"], ["Tasleem", "99.9%", "1.9", "0"]];
  return (
    <div className="space-y-6">
      <div className="grid gap-6 lg:grid-cols-2"><Card className="p-4"><BenchmarkChart /></Card><StatTiles /></div>
      <Card className="overflow-x-auto">
        <table className="w-full text-[14px]">
          <thead className="bg-sheet-2 text-[12px] text-muted"><tr>{["Arm", "Stalls flagged to a person", "Median days to alert", "False done"].map((h) => <th key={h} className="px-4 py-2 text-start font-semibold">{h}</th>)}</tr></thead>
          <tbody className="divide-y divide-rule">{rows.map((r) => <tr key={r[0]} className={cx(r[0] === "Tasleem" && "font-semibold")}>{r.map((v, i) => <td key={i} className={cx("px-4 py-3", i > 0 && "mono")}>{v}</td>)}</tr>)}</tbody>
        </table>
      </Card>
      <p className="text-[14px] text-ink-2"><strong>Why “Reminders only” scores 0%:</strong> reminders nudge patients but nobody watches the referral, so by definition no stall ever reaches a person. It is the common baseline, not a straw man.</p>
      <p className="text-[14px] text-ink-2">Clean journeys falsely alerted: <span className="mono">0.0%</span> for status only vs <span className="mono">0.2%</span> for Tasleem. Staff alerts per 100 patients: <span className="mono">38.5</span> vs <span className="mono">53.5</span>: more alerts, each naming one person and one action; they are the stalls status-only monitoring misses.</p>
      <p className="text-[13px] text-muted">Synthetic cohort of 2,000 patients with a published failure mix (Martin 2017), three seeds. This tests the software, not patient outcomes; that needs a clinical pilot. <a className="text-biro underline underline-offset-2" href={EVIDENCE_URL} target="_blank" rel="noreferrer">Read the evidence</a></p>
    </div>
  );
}

export default function Programme() {
  const trig = "press -mb-px border-b-2 px-3 py-2.5 text-[14px] font-semibold data-[state=active]:border-biro data-[state=active]:text-ink data-[state=inactive]:border-transparent data-[state=inactive]:text-muted hover:text-ink";
  return (
    <div className="mx-auto max-w-6xl space-y-5">
      <header>
        <h1 className="text-[32px] font-semibold leading-[38px]">Programme</h1>
        <p className="mt-1 text-ink-2">Verified completion, false “done” and time to colonoscopy, by clinic and language.</p>
      </header>
      <Tabs.Root defaultValue="measures">
        <Tabs.List className="flex gap-1 overflow-x-auto border-b border-rule" aria-label="Programme views">
          <Tabs.Trigger value="measures" className={trig}>Measures</Tabs.Trigger>
          <Tabs.Trigger value="channels" className={trig}>Channels</Tabs.Trigger>
          <Tabs.Trigger value="usage" className={trig}>Usage</Tabs.Trigger>
          <Tabs.Trigger value="ai" className={trig}>AI at work</Tabs.Trigger>
          <Tabs.Trigger value="benchmark" className={trig}>Benchmark</Tabs.Trigger>
          <Tabs.Trigger value="unmatched" className={trig}>Unmatched</Tabs.Trigger>
        </Tabs.List>
        <div className="pt-6">
          <Tabs.Content value="measures"><Measures /></Tabs.Content>
          <Tabs.Content value="channels"><Channels /></Tabs.Content>
          <Tabs.Content value="usage"><Usage /></Tabs.Content>
          <Tabs.Content value="ai"><AiAtWork /></Tabs.Content>
          <Tabs.Content value="benchmark"><Benchmark /></Tabs.Content>
          <Tabs.Content value="unmatched"><Unmatched /></Tabs.Content>
        </div>
      </Tabs.Root>
    </div>
  );
}

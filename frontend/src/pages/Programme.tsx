/* eslint-disable @typescript-eslint/no-explicit-any */
import * as Tabs from "@radix-ui/react-tabs";
import { useState } from "react";
import { Link } from "react-router-dom";
import { Bar, BarChart, Cell, LabelList, ResponsiveContainer, XAxis, YAxis } from "recharts";
import { CheckCircle2, Lock } from "lucide-react";
import { useChannels, useMe, useMetrics, useUsage } from "../lib/api";
import { BARRIER_LABELS, CHANNEL_LABELS, label, OUTCOME_LABELS, ORG_LABELS, ROLE_LABELS, STALL_LABELS, exactTime } from "../lib/labels";
import { BenchmarkChart, EVIDENCE_URL, StatTiles } from "../components/Benchmark";
import { Card, ErrorState, Skeleton, Tag, cx } from "../components/ui";

function HBar({ data, color = "var(--ink-2)", height }: { data: { name: string; v: number }[]; color?: string; height?: number }) {
  if (!data.length) return <p className="text-[14px] text-muted">Nothing to show.</p>;
  return (
    <div style={{ height: height ?? Math.max(80, data.length * 34) }} role="img" aria-label={data.map((d) => `${d.name}: ${d.v}`).join(", ")}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ top: 0, right: 40, bottom: 0, left: 0 }} barCategoryGap={8}>
          <XAxis type="number" hide allowDecimals={false} />
          <YAxis type="category" dataKey="name" width={190} tickLine={false} axisLine={false} tick={{ fill: "var(--ink-2)", fontSize: 12, fontFamily: "Libre Franklin" }} />
          <Bar dataKey="v" radius={[0, 2, 2, 0]} isAnimationActive={false}>
            {data.map((d) => <Cell key={d.name} fill={color} />)}
            <LabelList dataKey="v" position="right" style={{ fill: "var(--ink)", fontSize: 12, fontFamily: "IBM Plex Mono" }} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

const FILTERS = [["", "All"], ["org=org-ghaf", "Ghaf health centre"], ["org=org-samar", "Samar clinic"], ["language=ar", "Arabic"], ["language=en", "English"]];

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
                <div className="mt-1 flex flex-wrap gap-2 text-[13px]">{x.false_done.case_ids.map((id: string) => <Link key={id} to={`/app/cases/${id}`} className="mono text-biro underline underline-offset-2">{id}</Link>)}</div>
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
            <div className="grid gap-6 lg:grid-cols-2">
              {Object.entries<any>(x.by_pathway).map(([id, p]) => (
                <Card key={id} className="p-4">
                  <h3 className="text-[16px] font-semibold">{p.name} <span className="font-normal text-muted">· {p.cases} cases</span></h3>
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
          <thead className="bg-sheet-2 text-[12px] uppercase tracking-[0.06em] text-muted"><tr>{["Recipient", "Routine", "Urgent", "Quiet hours", "When all fail"].map((h) => <th key={h} className="px-4 py-2 text-start font-semibold">{h}</th>)}</tr></thead>
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
          <thead className="bg-sheet-2 text-[12px] uppercase tracking-[0.06em] text-muted"><tr><th className="px-4 py-2 text-start font-semibold">Provider</th><th className="px-4 py-2 text-start font-semibold">By pathway</th><th className="px-4 py-2 text-end font-semibold">Active cases</th></tr></thead>
          <tbody className="divide-y divide-rule">
            {u.data.by_org.map((o: any) => (
              <tr key={o.org_id}><td className="px-4 py-3 font-semibold">{ORG_LABELS[o.org_id] ?? o.org_id}</td><td className="px-4 py-3 text-ink-2">{Object.entries(o.pathways).map(([k, v]) => `${k.replace(/-/g, " ")}: ${v}`).join(" · ")}</td><td className="mono px-4 py-3 text-end">{o.active_cases}</td></tr>
            ))}
            <tr className="bg-sheet-2"><td className="px-4 py-3 font-semibold">Total</td><td /><td className="mono px-4 py-3 text-end font-semibold">{u.data.active_cases}</td></tr>
          </tbody>
        </table>
      </Card>
    </div>
  );
}

function Benchmark() {
  const rows = [["Reminders only", "0%", "–", "–"], ["Malaffi status only", "70.1%", "14.4", "125"], ["Tasleem", "98.5%", "4.0", "0"]];
  return (
    <div className="space-y-6">
      <div className="grid gap-6 lg:grid-cols-2"><Card className="p-4"><BenchmarkChart /></Card><StatTiles /></div>
      <Card className="overflow-x-auto">
        <table className="w-full text-[14px]">
          <thead className="bg-sheet-2 text-[12px] uppercase tracking-[0.06em] text-muted"><tr>{["Arm", "Stalls flagged to a person", "Median days to alert", "False done"].map((h) => <th key={h} className="px-4 py-2 text-start font-semibold">{h}</th>)}</tr></thead>
          <tbody className="divide-y divide-rule">{rows.map((r) => <tr key={r[0]} className={cx(r[0] === "Tasleem" && "font-semibold")}>{r.map((v, i) => <td key={i} className={cx("px-4 py-3", i > 0 && "mono")}>{v}</td>)}</tr>)}</tbody>
        </table>
      </Card>
      <p className="text-[14px] text-ink-2">Clean journeys falsely alerted: <span className="mono">0.0%</span>. Staff alerts per 100 patients: <span className="mono">38.5</span> for status only vs <span className="mono">66.4</span> for Tasleem: more alerts, each naming one person and one action; they are the stalls status-only monitoring misses.</p>
      <p className="text-[13px] text-muted">Synthetic cohort of 1,000 patients, three seeds. This tests the software, not patient outcomes; that needs a clinical pilot. <a className="text-biro underline underline-offset-2" href={EVIDENCE_URL} target="_blank" rel="noreferrer">Read the evidence</a></p>
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
          <Tabs.Trigger value="benchmark" className={trig}>Benchmark</Tabs.Trigger>
        </Tabs.List>
        <div className="pt-6">
          <Tabs.Content value="measures"><Measures /></Tabs.Content>
          <Tabs.Content value="channels"><Channels /></Tabs.Content>
          <Tabs.Content value="usage"><Usage /></Tabs.Content>
          <Tabs.Content value="benchmark"><Benchmark /></Tabs.Content>
        </div>
      </Tabs.Root>
    </div>
  );
}

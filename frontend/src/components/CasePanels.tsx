import type { ReactNode } from "react";
/* eslint-disable @typescript-eslint/no-explicit-any */
import * as Tabs from "@radix-ui/react-tabs";
import { useEffect, useRef } from "react";
import { Check, Clock, Inbox, List, Mail, MessageSquare, ShieldAlert, ShieldCheck, Smartphone, Sparkles, X } from "lucide-react";
import { useAssist, useAudit, useTrail } from "../lib/api";
import { CHANNEL_LABELS, EVENT_LABELS, exactTime, label, relTime, shortName } from "../lib/labels";
import type { Case } from "../lib/types";
import Composer from "./Composer";
import { EmptyState, ErrorState, Skeleton, Source, Tag, cx } from "./ui";

function Cite({ seq, onCite }: { seq: number; onCite: (s: number) => void }) {
  return <button type="button" onClick={() => onCite(seq)} className="press mono ms-1 rounded-sm border border-rule px-1 text-[11px] leading-4 text-ink-2 hover:border-biro hover:text-biro" aria-label={`Show event ${seq} in the timeline`}>#{seq}</button>;
}

function Assistant({ c, onCite, meName }: { c: Case; onCite: (s: number) => void; meName?: string }) {
  const a = useAssist(c.id);
  if (a.isLoading) return <Skeleton className="h-64" />;
  if (a.error) return <ErrorState error={a.error} />;
  const x = a.data!;
  const pm = x.act.patient_message;
  return (
    <div className="space-y-5 rounded border border-dashed border-ai p-4">
      <p className="flex items-center gap-2 text-[14px] font-semibold text-ai"><Sparkles size={16} aria-hidden />Assistant · suggestions only</p>
      <section>
        <h3 className="mb-2 text-[13px] font-semibold uppercase tracking-[0.06em] text-muted">What happened</h3>
        <ul className="space-y-2 text-[14px] leading-[21px]">
          {x.sense.map((s) => <li key={s.id}>{s.text}{s.cites.map((n) => <Cite key={n} seq={n} onCite={onCite} />)}</li>)}
        </ul>
      </section>
      <section className="rounded border border-rule-strong bg-sheet-2 p-3">
        <h3 className="mb-1 text-[13px] font-semibold uppercase tracking-[0.06em] text-muted">What the rules say</h3>
        <p className="text-[14px] text-ink-2">{x.decide.next_step?.text}</p>
        <p className="mt-2 flex flex-wrap items-center gap-2"><Source kind="rule">{x.decide.next_step?.reason}</Source><span className="text-[12px] text-muted">The assistant cannot change this.</span></p>
      </section>
      <section>
        <h3 className="mb-2 flex items-center gap-2 text-[13px] font-semibold uppercase tracking-[0.06em] text-muted">Brief {x.act.brief.source === "extractive" ? <Tag tone="muted">Extracted from facts</Tag> : <Tag tone="ai">AI drafted</Tag>}</h3>
        <p className="text-[14px] leading-[22px]">{x.act.brief.sentences.map((s, i) => <span key={i}>{s.text}{s.cites.map((n) => <Cite key={n} seq={n} onCite={onCite} />)} </span>)}</p>
      </section>
      <section>
        <h3 className="mb-2 text-[13px] font-semibold uppercase tracking-[0.06em] text-muted">Message to the patient</h3>
        {pm.draft === null ? (
          <div className="rounded border border-attn bg-attn-wash p-3 text-[14px] text-attn">{pm.why}</div>
        ) : c.actions.message_patient.allowed ? (
          <>
            <Composer key={pm.draft_id ?? "none"} caseId={c.id} draft={pm} defaultLanguage={c.patient.language} meName={meName} />
            <p className="mt-2 text-[12px] text-muted">{pm.why}</p>
          </>
        ) : <p className="text-[14px] text-muted">{c.actions.message_patient.message} <span className="mono text-[12px]">{c.actions.message_patient.code}</span></p>}
      </section>
      <p className="border-t border-dashed border-ai pt-3 text-[13px] text-ink-2">Hands off to {shortName(x.hand_off.to?.name) || "the owner"}. Nothing is sent or changed until a person acts.</p>
    </div>
  );
}

function Timeline({ c, highlight }: { c: Case; highlight: number | null }) {
  const ref = useRef<HTMLOListElement>(null);
  useEffect(() => {
    if (highlight == null) return;
    ref.current?.querySelector(`[data-seq="${highlight}"]`)?.scrollIntoView({ block: "center" });
  }, [highlight]);
  const items = [...c.timeline].sort((a, b) => b.seq - a.seq);
  return (
    <ol ref={ref} className="space-y-0 border-s border-rule ps-4">
      {items.map((e) => {
        const keys = Object.entries(e.payload).filter(([k, v]) => !["case_id", "patient_id"].includes(k) && v != null && typeof v !== "object").slice(0, 3);
        return (
          <li key={e.seq} data-seq={e.seq} className={cx("relative -ms-4 rounded py-2.5 ps-4 pe-2", highlight === e.seq && "bg-biro-wash")}>
            <span className="absolute -start-[5px] top-4 h-2.5 w-2.5 rounded-full border-2 border-sheet bg-ink-2" aria-hidden />
            <div className="flex flex-wrap items-baseline gap-x-2">
              <span className="mono text-[12px] text-muted">#{e.seq}</span>
              <span className="text-[14px] font-semibold">{label(EVENT_LABELS, e.type)}</span>
              <time className="text-[12px] text-muted" title={exactTime(e.at)} dateTime={e.at}>{relTime(e.at)}</time>
            </div>
            <div className="mt-0.5 flex flex-wrap items-center gap-2 text-[12px] text-muted">
              <span>{e.actor}</span>
              {e.provenance === "fact" ? <Tag tone="muted">FACT</Tag> : e.provenance === "computed" ? <span className="rounded-sm border border-rule-strong px-1 font-semibold text-ink-2">RULE</span> : e.provenance?.includes("ai") ? <Tag tone="ai">AI</Tag> : <Tag tone="ink">HUMAN</Tag>}
              {"ai_draft_id" in e.payload && e.payload.ai_draft_id && <Tag tone="ai">AI-assisted</Tag>}
            </div>
            {keys.length > 0 && <p className="mono mt-1 break-all text-[11px] leading-4 text-ink-2">{keys.map(([k, v]) => `${k}: ${String(v)}`).join(" · ")}</p>}
          </li>
        );
      })}
    </ol>
  );
}

const CH_ICON: Record<string, ReactNode> = {
  sahatna_push: <Smartphone size={14} aria-hidden />, sahatna: <Smartphone size={14} aria-hidden />, sms_nudge: <MessageSquare size={14} aria-hidden />,
  sms_page: <MessageSquare size={14} aria-hidden />, emr_task: <Inbox size={14} aria-hidden />, worklist: <List size={14} aria-hidden />,
  email: <Mail size={14} aria-hidden />, email_digest: <Mail size={14} aria-hidden />,
};
const statusTone = (s: string) => (s === "failed" ? "stop" : s === "read" ? "done" : s === "queued" ? "muted" : "biro") as "stop" | "done" | "muted" | "biro";

function Messages({ c }: { c: Case }) {
  const t = useTrail(c.id);
  if (t.isLoading) return <Skeleton className="h-40" />;
  if (t.error) return <ErrorState error={t.error} />;
  const items: any[] = t.data?.items ?? [];
  return (
    <div className="space-y-4">
      {items.length === 0 && <EmptyState title="No delivery trail yet.">Messages and tasks appear here once the notifier sends them.</EmptyState>}
      {items.map((it) => (
        <div key={it.outbox_id} className="rounded border border-rule p-3">
          <p className="text-[13px] text-ink-2"><span className="font-semibold text-ink">{it.recipient_role === "patient" ? "Patient" : shortName(it.recipient_id)}</span> · {it.template.replace(/_/g, " ")}{it.urgent && <Tag tone="stop" className="ms-2">Urgent</Tag>}</p>
          <ol className="mt-2 flex flex-wrap items-center gap-1.5">
            {it.deliveries.map((d: any, i: number) => (
              <li key={d.id} className="flex items-center gap-1.5">
                {i > 0 && <span className="text-muted" aria-hidden>→</span>}
                <span className={cx("inline-flex items-center gap-1 rounded-sm border px-1.5 py-0.5 text-[12px]", d.status === "failed" ? "border-stop text-stop" : "border-rule text-ink-2")} title={d.detail || undefined}>
                  {CH_ICON[d.channel]}{CHANNEL_LABELS[d.channel] ?? d.channel}<Tag tone={statusTone(d.status)}>{d.status}</Tag>
                </span>
                {d.channel === "sms_nudge" && <span className="text-[11px] text-muted">nudge only (no case content)</span>}
              </li>
            ))}
          </ol>
          <p className="mt-2 text-[13px]">
            {it.status === "done" ? <span className="inline-flex items-center gap-1 text-done"><Check size={14} aria-hidden />Done</span>
              : it.status === "exhausted" ? <span className="inline-flex items-center gap-1 font-semibold text-stop"><X size={14} aria-hidden />Not reached; a navigator was asked to call</span>
              : it.next_at ? <span className="inline-flex items-center gap-1 text-ink-2"><Clock size={14} aria-hidden />Next try {relTime(it.next_at)}</span> : <span className="text-muted">{it.status}</span>}
          </p>
        </div>
      ))}
      {c.notifications?.length > 0 && (
        <div className="space-y-2">
          <h3 className="text-[13px] font-semibold uppercase tracking-[0.06em] text-muted">What this case asked to send</h3><p className="text-[12px] text-muted">Delivery is tracked in the trail above.</p>
          {c.notifications.map((n: any) => {
            const content = n.payload?.payload?.[0]?.contentString;
            return n.recipient_role === "patient" && content ? (
              <div key={n.id} className="max-w-[85%] rounded-[10px] rounded-es-[2px] border border-rule bg-sheet-2 px-3 py-2 text-[14px]" dir={n.payload?.language === "ar" ? "rtl" : "ltr"} lang={n.payload?.language}>
                {content}<p className="mt-1 text-[11px] text-muted" dir="ltr">Sahatna · {relTime(n.created_at)}</p>
              </div>
            ) : (
              <div key={n.id} className="flex items-center gap-2 rounded border border-rule px-3 py-2 text-[13px]">
                {CH_ICON[n.channel] ?? <Inbox size={14} aria-hidden />}<span className="font-medium">{CHANNEL_LABELS[n.channel] ?? n.channel}</span>
                <span className="text-ink-2">{shortName(n.recipient)} · {n.template.replace(/_/g, " ")}</span><Tag tone={statusTone(n.status)} className="ms-auto">{n.status}</Tag>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function Audit({ c }: { c: Case }) {
  const a = useAudit(c.id);
  if (a.isLoading) return <Skeleton className="h-40" />;
  if (a.error) return <ErrorState error={a.error} />;
  const v = a.data.verification;
  return (
    <div className="space-y-3">
      {v.ok ? (
        <p className="flex items-center gap-2 rounded border border-done bg-done-wash p-3 font-semibold text-done"><ShieldCheck size={20} aria-hidden />Chain intact: <span className="tnum">{v.checked}</span> events verified</p>
      ) : (
        <p className="flex items-center gap-2 rounded border border-stop bg-stop-wash p-3 font-semibold text-stop"><ShieldAlert size={20} aria-hidden />Broken at #{v.broken_at_seq}: {v.problem}</p>
      )}
      <p className="text-[13px] text-muted">Each event stores the hash of the one before it, so any edit breaks the chain (R6).</p>
      <div className="overflow-x-auto rounded border border-rule">
        <table className="mono w-full text-[11px] leading-4">
          <thead className="bg-sheet-2 text-start text-muted"><tr><th className="px-2 py-1.5 text-start">#</th><th className="px-2 py-1.5 text-start">Event</th><th className="px-2 py-1.5 text-start">Actor</th><th className="px-2 py-1.5 text-start">prev → hash</th></tr></thead>
          <tbody className="divide-y divide-rule">
            {a.data.events.map((e: any) => (
              <tr key={e.seq}>
                <td className="px-2 py-1.5">{e.seq}</td>
                <td className="px-2 py-1.5">{e.type}</td>
                <td className="px-2 py-1.5">{e.actor_id}</td>
                <td className="whitespace-nowrap px-2 py-1.5 text-muted">{e.prev_hash.slice(0, 10)} → <span className="text-ink">{e.hash.slice(0, 10)}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function CasePanels({ c, tab, setTab, highlight, onCite, meName }: { c: Case; tab: string; setTab: (t: string) => void; highlight: number | null; onCite: (s: number) => void; meName?: string }) {
  const trig = "press -mb-px border-b-2 px-3 py-2.5 text-[14px] font-semibold data-[state=active]:border-biro data-[state=active]:text-ink data-[state=inactive]:border-transparent data-[state=inactive]:text-muted hover:text-ink";
  return (
    <Tabs.Root value={tab} onValueChange={setTab}>
      <Tabs.List className="flex gap-1 overflow-x-auto border-b border-rule" aria-label="Case details">
        <Tabs.Trigger value="assistant" className={trig}>Assistant</Tabs.Trigger>
        <Tabs.Trigger value="timeline" className={trig}>Timeline</Tabs.Trigger>
        <Tabs.Trigger value="messages" className={trig}>Messages</Tabs.Trigger>
        <Tabs.Trigger value="audit" className={trig}>Audit</Tabs.Trigger>
      </Tabs.List>
      <div className="pt-4">
        <Tabs.Content value="assistant"><Assistant c={c} onCite={onCite} meName={meName} /></Tabs.Content>
        <Tabs.Content value="timeline"><Timeline c={c} highlight={highlight} /></Tabs.Content>
        <Tabs.Content value="messages"><Messages c={c} /></Tabs.Content>
        <Tabs.Content value="audit"><Audit c={c} /></Tabs.Content>
      </div>
    </Tabs.Root>
  );
}

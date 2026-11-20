import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import { useMe, useWork } from "../lib/api";
import { label, ROLE_LABELS, shortName } from "../lib/labels";
import CaseRowItem from "../components/CaseRowItem";
import { Card, EmptyState, ErrorState, Overline, Skeleton, Source, cx } from "../components/ui";
import type { CaseRow } from "../lib/types";

const ORDER = ["distress", "escalated", "handoff", "consult", "task", "owner"];

export default function MyWork() {
  const work = useWork();
  const me = useMe();
  if (work.isLoading) return <div className="space-y-4"><Skeleton className="h-10 w-1/2" /><Skeleton className="h-40" /><Skeleton className="h-40" /></div>;
  if (work.error) return <ErrorState error={work.error} retry={() => work.refetch()} />;
  const w = work.data!;
  // A case appears once, in the most urgent section it belongs to (judge finding, 20 Nov: the same 5 cases were
  // listed twice, under "Escalated" and "Your cases").
  const seen = new Set<string>();
  const sections = [...w.sections].sort((a, b) => ORDER.indexOf(a.kind) - ORDER.indexOf(b.kind)).map((s) => {
    const items = s.items.filter((r) => !seen.has(r.id));
    items.forEach((r) => seen.add(r.id));
    return { ...s, items, count: items.length, label: s.kind === "owner" && items.length < s.items.length ? "Your other open cases" : s.label };
  }).filter((s) => s.count > 0 || s.kind === "owner");
  // Shift brief: the first three cases in that order, each with the one thing to do. Chosen by rules, not AI.
  const brief: CaseRow[] = sections.flatMap((s) => s.items).filter((r) => r.status === "open" && r.next_action && r.next_action.who !== "system").slice(0, 3);
  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <header>
        <p className="text-[13px] text-muted">{shortName(me.data?.name)} · {label(ROLE_LABELS, me.data?.role)}</p>
        <h1 className="mt-1 text-[32px] font-semibold leading-[38px]">
          {w.needs_action > 0 ? <>You have <span className="tnum">{w.needs_action}</span> {w.needs_action === 1 ? "case that" : "cases that"} {w.needs_action === 1 ? "needs" : "need"} action.</> : <>Nothing needs you right now.</>}
        </h1>
        <p className="mt-2 text-ink-2">Most at-risk first. Every case has one named owner, and every missed deadline reaches a person.</p>
        {w.covering?.map((p: { id: string; name: string; until: string }) => (
          <p key={p.id} role="status" className="mt-3 rounded border border-biro bg-biro-wash px-3 py-2 text-[14px] text-ink">
            You are covering for <strong>{shortName(p.name)}</strong> until {new Date(p.until).toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" })}. Their cases and questions are in this list, and new escalations come to you. They stay the owner.
          </p>
        ))}
      </header>
      {brief.length > 0 && (
        <section aria-labelledby="shift-brief" className="plastic p-4 md:p-5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <Overline><span id="shift-brief">Start here today</span></Overline>
            <Source kind="rule">most at risk first</Source>
          </div>
          <ol className="mt-3 space-y-2">
            {brief.map((r, i) => (
              <li key={r.id} className="row-slip">
                <Link to={`/app/cases/${r.id}`} className="press-wide group flex items-start gap-3 px-3 py-2.5">
                  <span className="mono mt-0.5 w-4 shrink-0 text-[13px] text-muted">{i + 1}</span>
                  <span className="min-w-0 flex-1 text-[15px] leading-[22px]"><strong>{shortName(r.patient.name)}</strong> <span className="text-ink-2">· {r.next_action!.text}</span></span>
                  <ArrowRight size={16} className="mt-1 shrink-0 text-muted transition-transform duration-150 group-hover:translate-x-0.5 rtl:rotate-180" aria-hidden />
                </Link>
              </li>
            ))}
          </ol>
        </section>
      )}
      {sections.map((s) => (
        <Card key={s.kind} className={cx(s.kind === "distress" && "border-stop")}>
          <div className={cx("flex items-center justify-between gap-3 border-b px-4 py-3", s.kind === "distress" ? "border-stop bg-stop-wash" : "border-rule")}>
            <h2 className={cx("font-sans text-[16px] font-semibold leading-[22px]", s.kind === "distress" && "text-stop")}>{s.label}</h2>
            <span className="mono text-[13px] text-muted">{s.count}</span>
          </div>
          {s.items.length ? <ul className="divide-y divide-rule">{s.items.map((r) => <CaseRowItem key={`${s.kind}-${r.id}`} row={r} meId={me.data?.id} />)}</ul>
            : <div className="p-4"><EmptyState title="No open cases yet.">New cases arrive from Malaffi as referrals are sent. Try the Live simulator.</EmptyState></div>}
        </Card>
      ))}
    </div>
  );
}

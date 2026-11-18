import { useMe, useWork } from "../lib/api";
import { label, ROLE_LABELS, shortName } from "../lib/labels";
import CaseRowItem from "../components/CaseRowItem";
import { Card, EmptyState, ErrorState, Skeleton, cx } from "../components/ui";

const ORDER = ["distress", "escalated", "handoff", "consult", "task", "owner"];

export default function MyWork() {
  const work = useWork();
  const me = useMe();
  if (work.isLoading) return <div className="space-y-4"><Skeleton className="h-10 w-1/2" /><Skeleton className="h-40" /><Skeleton className="h-40" /></div>;
  if (work.error) return <ErrorState error={work.error} retry={() => work.refetch()} />;
  const w = work.data!;
  const sections = [...w.sections].sort((a, b) => ORDER.indexOf(a.kind) - ORDER.indexOf(b.kind)).filter((s) => s.count > 0 || s.kind === "owner");
  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <header>
        <p className="text-[13px] text-muted">{shortName(me.data?.name)} · {label(ROLE_LABELS, me.data?.role)}</p>
        <h1 className="mt-1 text-[32px] font-semibold leading-[38px]">
          {w.needs_action > 0 ? <>You have <span className="tnum">{w.needs_action}</span> {w.needs_action === 1 ? "case" : "cases"} that <em className="font-medium">need</em> action.</> : <>Nothing needs you <em className="font-medium">right now</em>.</>}
        </h1>
        <p className="mt-2 text-ink-2">Most at-risk first. Every case has one named owner, and every missed deadline reaches a person.</p>
      </header>
      {sections.map((s) => (
        <Card key={s.kind} className={cx(s.kind === "distress" && "border-stop")}>
          <div className={cx("flex items-center justify-between gap-3 border-b px-4 py-3", s.kind === "distress" ? "border-stop bg-stop-wash" : "border-rule")}>
            <h2 className={cx("font-sans text-[16px] font-semibold leading-[22px]", s.kind === "distress" && "text-stop")}>{s.label}</h2>
            <span className="mono text-[13px] text-muted">{s.count}</span>
          </div>
          {s.items.length ? <ul className="divide-y divide-rule">{s.items.map((r) => <CaseRowItem key={`${s.kind}-${r.id}`} row={r} />)}</ul>
            : <div className="p-4"><EmptyState title="No open cases yet.">New cases arrive from Malaffi as referrals are sent. Try the Live simulator.</EmptyState></div>}
        </Card>
      ))}
    </div>
  );
}

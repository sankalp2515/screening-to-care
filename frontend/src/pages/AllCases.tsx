import { useMemo, useState } from "react";
import { Search } from "lucide-react";
import { useCases } from "../lib/api";
import { shortName } from "../lib/labels";
import CaseRowItem from "../components/CaseRowItem";
import { Card, EmptyState, ErrorState, Skeleton, cx, inputCls } from "../components/ui";

export default function AllCases() {
  const [status, setStatus] = useState("open");
  const [stalled, setStalled] = useState(false);
  const [pathway, setPathway] = useState("");
  const [owner, setOwner] = useState("");
  const [q, setQ] = useState("");
  const all = useCases({ status: "all" });
  const list = useCases({ status, stalled: stalled ? "true" : "", pathway, owner });
  const pathways = useMemo(() => [...new Map((all.data?.items ?? []).map((r) => [r.pathway.id, r.pathway.name])).entries()], [all.data]);
  const owners = useMemo(() => [...new Map((all.data?.items ?? []).map((r) => [r.owner.id, r.owner.name])).entries()], [all.data]);
  const rows = (list.data?.items ?? []).filter((r) => r.patient.name.toLowerCase().includes(q.toLowerCase()));

  return (
    <div className="mx-auto max-w-6xl space-y-5">
      <header>
        <h1 className="text-[32px] font-semibold leading-[38px]">All cases</h1>
        <p className="mt-1 text-ink-2">Ordered most at-risk first, by the rules. Each clinic sees only its own patients.</p>
      </header>
      <div className="flex flex-wrap items-end gap-3">
        <div className="inline-flex rounded border border-rule-strong bg-sheet p-0.5" role="group" aria-label="Status">
          {["open", "closed", "all"].map((s) => (
            <button key={s} type="button" aria-pressed={status === s} onClick={() => setStatus(s)} className={cx("press h-9 rounded-[3px] px-3 text-[14px] font-medium capitalize", status === s ? "bg-ink text-paper" : "text-ink-2 hover:bg-sheet-2")}>{s}</button>
          ))}
        </div>
        <label className="flex h-10 items-center gap-2 rounded border border-rule-strong bg-sheet px-3 text-[14px]">
          <input type="checkbox" checked={stalled} onChange={(e) => setStalled(e.target.checked)} className="h-4 w-4 accent-[var(--biro)]" />Stalled only
        </label>
        <select aria-label="Pathway" value={pathway} onChange={(e) => setPathway(e.target.value)} className={cx(inputCls, "h-10 w-auto py-0")}>
          <option value="">All pathways</option>{pathways.map(([id, n]) => <option key={id} value={id}>{n}</option>)}
        </select>
        <select aria-label="Owner" value={owner} onChange={(e) => setOwner(e.target.value)} className={cx(inputCls, "h-10 w-auto py-0")}>
          <option value="">All owners</option>{owners.map(([id, n]) => <option key={id} value={id}>{shortName(n)}</option>)}
        </select>
        <div className="relative ms-auto min-w-[200px] flex-1 md:max-w-xs">
          <Search size={16} className="pointer-events-none absolute start-3 top-1/2 -translate-y-1/2 text-muted" aria-hidden />
          <input aria-label="Search by patient name" placeholder="Search by patient name" value={q} onChange={(e) => setQ(e.target.value)} className={cx(inputCls, "h-10 ps-9")} />
        </div>
      </div>
      {list.isLoading ? <Skeleton className="h-64" /> : list.error ? <ErrorState error={list.error} retry={() => list.refetch()} /> : (
        <Card>
          <div className="hidden grid-cols-[minmax(180px,1.2fr)_minmax(160px,1fr)_minmax(0,1.4fr)] gap-x-6 border-b border-rule bg-sheet-2 px-4 py-2 text-[12px] font-semibold uppercase tracking-[0.06em] text-muted md:grid">
            <span>Patient</span><span>Reported vs verified</span><span>Stalls and owner</span>
          </div>
          {rows.length ? <ul className="divide-y divide-rule">{rows.map((r) => <CaseRowItem key={r.id} row={r} showPriority />)}</ul>
            : <div className="p-4"><EmptyState title="No cases match these filters.">Clear a filter, or choose “all” to include closed cases.</EmptyState></div>}
        </Card>
      )}
      <p className="text-[13px] text-muted"><span className="tnum">{rows.length}</span> shown. Each clinic sees only its own patients.</p>
    </div>
  );
}

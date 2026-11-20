import { Link } from "react-router-dom";
import { AlertOctagon, MessageSquareText } from "lucide-react";
import type { CaseRow } from "../lib/types";
import { plural, relTime, shortName } from "../lib/labels";
import { JourneyBar, LangTag, StallChip, cx } from "./ui";

const WHY: Record<string, string> = {
  escalated: "Escalated to you", handoff: "Waiting for you to accept", consult: "Answer requested",
  task: "Task due", distress: "Patient message needs a clinician", owner: "You own this case",
};

export default function CaseRowItem({ row, showPriority, meId }: { row: CaseRow; showPriority?: boolean; meId?: string }) {
  const ar = row.patient.language === "ar";
  return (
    <li>
      <Link to={`/app/cases/${row.id}`} className="row-hover press-wide grid gap-x-6 gap-y-2 px-4 py-3 md:grid-cols-[minmax(180px,1.2fr)_minmax(160px,1fr)_minmax(0,1.4fr)] md:items-center">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="truncate font-semibold text-ink">{row.patient.name}</span>
            <LangTag lang={row.patient.language} />
            {row.distress_open > 0 && <AlertOctagon size={16} className="text-stop" aria-label="Distress open" />}
            {row.open_barriers > 0 && <MessageSquareText size={16} className="text-ink-2" aria-label={`${row.open_barriers} open barrier`} />}
          </div>
          <p className="truncate text-[13px] text-muted">{row.pathway.name}{showPriority && <> · <span className={cx(row.priority === "high" && "font-semibold text-ink-2")}>{row.priority} priority</span></>}</p>
        </div>
        <div className="space-y-1.5">
          <JourneyBar progress={row.progress} compact />
          <p className="text-[12px] text-muted">
            {row.progress.gap ? <span className="font-semibold text-attn">Says {row.progress.reported.admin_status}, verified to step {row.progress.verified.step}</span> : <>Verified to step {row.progress.verified.step} of {row.progress.verified.of}</>}
          </p>
        </div>
        <div className="min-w-0 space-y-1.5">
          <div className="flex flex-wrap gap-1.5">
            {row.distress_open > 0 && <span className="rounded-[2px] border border-stop bg-stop-wash px-1.5 text-[12px] font-semibold text-stop">Symptom: clinician call</span>}
            {row.stalls.length === 0 ? <span className="text-[13px] text-muted">{row.status === "closed" ? `Closed${row.outcome ? ": " + String(row.outcome).toLowerCase().replace(/_/g, " ") : ""}` : row.distress_open > 0 ? "" : row.next_action && row.next_action.who !== "system" ? "Needs a step" : "On track"}</span>
              : row.stalls.map((s) => <StallChip key={s.reason} label={s.label} level={s.level} />)}
          </div>
          {row.status === "open" && row.next_action && row.next_action.who !== "system" && (
            <p className="text-[13px] leading-[18px] text-ink-2"><span className="font-semibold text-ink">{meId && row.next_action.who === "owner" && row.owner.id !== meId ? `Next, for ${shortName(row.owner.name)}:` : "Next:"}</span> {row.next_action.text}</p>
          )}
          <p className="text-[12px] text-muted" dir="ltr">
            <span lang={ar ? "en" : undefined}>Owner {shortName(row.owner.name)}</span>
            {row.days_since_progress != null && <> · <span className="tnum">{plural(Math.round(row.days_since_progress), "day")}</span> since progress</>}
            {row.why && row.why.kind !== "owner" && <> · <span className="font-medium text-ink-2">{row.why.kind === "escalated" && meId && row.owner.id === meId ? "Overdue on your case" : WHY[row.why.kind] ?? row.why.kind}</span> {relTime(row.why.since)}</>}
          </p>
        </div>
      </Link>
    </li>
  );
}

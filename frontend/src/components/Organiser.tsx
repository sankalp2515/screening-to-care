import { Check, Minus } from "lucide-react";
import type { Case } from "../lib/types";
import { exactTime, shortName } from "../lib/labels";
import { cx } from "./ui";

/**
 * The Organiser (Dose signature): a case's screening journey as nine plastic compartments, filled where clinical
 * evidence exists, clear where it does not, with a pharmacy-label ticket for what the referral system claims and
 * receipts for who acts. Built from a real `Case`, so it never shows a step the record does not hold.
 *
 * Props
 * - `c`        the case (GET /v1/cases/{id})
 * - `variant`  "tray": turned three-quarter, plays once (landing hero); "flat": straight on (case page)
 * - `ticket`   show the label and receipts (default true)
 */

const SHORT: Record<string, string> = {
  PATIENT_INVITED: "Invited", RESULT_DISCUSSED: "Discussed", REFERRED: "Referred", REFERRAL_ACCEPTED: "Accepted",
  BOOKED: "Booked", ATTENDED: "Attended", PROCEDURE_DONE: "Procedure", REPORT_RECEIVED: "Report", OUTCOME_COMMUNICATED: "Told",
};
const time = (iso?: string | null) => (iso ? new Date(iso).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" }) : "");
const day = (iso?: string | null) => (iso ? new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short" }) : "");

export default function Organiser({ c, variant = "tray", ticket = true }: { c: Case; variant?: "tray" | "flat"; ticket?: boolean }) {
  // An attempted step the report says did not finish counts as no evidence (it shows clear, with a grey mark).
  const stages = c.stages.slice(0, 9).map((s) => (s.status === "incomplete" ? { ...s, reached: false, attempted: true } : { ...s, attempted: false }));
  const reached = stages.filter((s) => s.reached).length;
  const lastOn = [...stages].reverse().find((s) => s.reached);
  const firstOff = stages.find((s) => !s.reached);
  const stall = c.stalls[0];
  const reported = c.progress.reported.admin_status;
  const gap = c.progress.gap;
  return (
    <figure className={cx("org m-0", variant === "flat" ? "org--flat" : "org--play")} aria-label={`${c.patient.name}: ${reached} of ${stages.length} steps have clinical evidence${gap ? `, while the referral system says ${reported}` : ""}`}>
      <div className="org-tray" aria-hidden="true">
        <div className="org-plane">
        <div className="org-row">
          {stages.map((s, i) => (
            <div key={s.id} className={cx("cell", s.reached ? "cell--on" : "cell--off")} style={{ ["--i" as string]: i }}>
              <span className="cell-n">{i + 1}</span>
              {s.reached && <span className="cell-tick"><Check strokeWidth={3} /></span>}
              {s.attempted && <span className="cell-tick cell-tick--grey"><Minus strokeWidth={3} /></span>}
            </div>
          ))}
        </div>
        <div className="org-steps">
          {stages.map((s) => <span key={s.id} className={s.reached ? undefined : "off"}>{SHORT[s.id] ?? s.label}</span>)}
        </div>
        </div>
      </div>

      {ticket && (
        <div className="org-overlap grid gap-[var(--space-md)] sm:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)] sm:items-start">
          <div className="ticket">
            <div className="ticket-head"><span>{shortName(c.patient.name)}</span><span>{c.pathway.name}</span></div>
            {gap ? (
              <>
                <p className="ticket-title">Malaffi says {reported}</p>
                <p>Evidence stops at {lastOn ? (SHORT[lastOn.id] ?? lastOn.label).toLowerCase() : "the start"}{lastOn?.reached_at && <> on <time dateTime={lastOn.reached_at} title={exactTime(lastOn.reached_at)}>{day(lastOn.reached_at)}</time></>}</p>
                <span className="stamp stamp--grey">Not verified</span>
              </>
            ) : (
              <>
                <p className="ticket-title">{lastOn ? `${SHORT[lastOn.id] ?? lastOn.label}, verified` : "Opened"}</p>
                <p>Next: {firstOff ? (SHORT[firstOff.id] ?? firstOff.label).toLowerCase() : "close on evidence"}</p>
                {lastOn?.reached_at && <span className="stamp stamp--given">Evidence {day(lastOn.reached_at)} {time(lastOn.reached_at)}</span>}
              </>
            )}
            <p className="ticket-stub">{stall ? stall.label : "No stall"}</p>
          </div>
          <ul className="receipts m-0 list-none p-0" aria-label="Who acts">
            <li className="receipt" style={{ ["--i" as string]: 0 }}><span className="receipt-mark"><Check strokeWidth={3} /></span><span><b>{shortName(c.owner.name)}</b><span>Named owner</span></span></li>
            {stall?.escalated_to && <li className="receipt" style={{ ["--i" as string]: 1 }}><span className="receipt-mark"><Check strokeWidth={3} /></span><span><b>{shortName(stall.escalated_to.name)}</b><span>Escalated, level {stall.level}</span></span></li>}
            {firstOff && <li className="receipt" style={{ ["--i" as string]: 2 }}><span className="receipt-mark receipt-mark--grey"><Minus strokeWidth={3} /></span><span><b>{SHORT[firstOff.id] ?? firstOff.label}</b><span>{firstOff.attempted ? "Attempted, incomplete" : "Not received"}</span></span></li>}
          </ul>
        </div>
      )}
    </figure>
  );
}

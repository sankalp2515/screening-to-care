import { useNavigate } from "react-router-dom";
import { X } from "lucide-react";
import { caseIdForPatient } from "../lib/api";
import { usePersona } from "../lib/persona";
import { Button } from "./ui";

/** A step goes to a fixed path, or to a patient's case (looked up at click time, so it works live too). */
interface Step { text: string; persona: string; to?: string; patient?: string; suffix?: string }
export const TOUR: Step[] = [
  { text: "Rajesh's referral says COMPLETED. The evidence stops at Attended. That gap is what Tasleem exists to catch.", persona: "dr-fatima", patient: "p-rajesh" },
  { text: "Try to close it as 'Completed, report received'. The rules block it (R3) and say why.", persona: "dr-fatima", patient: "p-rajesh", suffix: "?close=1" },
  { text: "Send a real event: run 'Malaffi says completed, colonoscopy never happened', then 'GI centre sends the report'.", persona: "dr-fatima", to: "/app/simulator" },
  { text: "Noura wrote in Arabic. Confirm the AI suggestion, then try adding 'your result is positive' to the message.", persona: "nav-aisha", patient: "p-noura" },
  { text: "Sunita mentions blood. It goes to a clinician, and only a clinician can record the response.", persona: "dr-salma", patient: "p-sunita" },
  { text: "The programme view: verified completion against what Malaffi says.", persona: "coord-sara", to: "/app/programme" },
  { text: "What Noura sees: no results, just her next step, in Arabic.", persona: "p-noura", to: "/patient" },
];

export default function Tour() {
  const { tour, setTour, setPersona } = usePersona();
  const nav = useNavigate();
  if (!tour.open) return null;
  const step = Math.min(tour.step, TOUR.length - 1);
  const s = TOUR[step];
  // Every button takes the reviewer to the screen the step talks about, so "Next" never leaves them reading
  // about a screen they cannot see.
  const visit = async (i: number) => {
    const target = TOUR[i];
    setTour({ open: true, step: i });
    setPersona(target.persona);
    if (!target.patient) { nav(target.to ?? "/app/work"); return; }
    const id = await caseIdForPatient(target.patient, target.persona).catch(() => null);
    nav(id ? `/app/cases/${id}${target.suffix ?? ""}` : "/app/cases");
  };
  return (
    <aside aria-label="Reviewer tour" className="reveal fixed bottom-4 end-4 z-30 w-[min(360px,calc(100vw-32px))] rounded border border-ink bg-sheet p-4">
      <div className="flex items-center justify-between">
        <p className="mono text-[12px] text-muted">Reviewer tour · step {step + 1} of {TOUR.length}</p>
        <button type="button" className="press -m-1 rounded p-1 text-ink-2 hover:bg-sheet-2" aria-label="Close tour" onClick={() => setTour({ ...tour, open: false })}><X size={16} /></button>
      </div>
      <p className="mt-2 text-[15px] leading-[22px] text-ink">{s.text}</p>
      <div className="mt-4 flex items-center gap-2">
        <Button variant="primary" size="sm" onClick={() => visit(step)}>Take me there</Button>
        <div className="ms-auto flex gap-1">
          <Button variant="quiet" size="sm" disabled={step === 0} onClick={() => visit(step - 1)}>Back</Button>
          {step === TOUR.length - 1
            ? <Button size="sm" onClick={() => setTour({ ...tour, open: false })}>Finish</Button>
            : <Button size="sm" onClick={() => visit(step + 1)}>Next</Button>}
        </div>
      </div>
    </aside>
  );
}

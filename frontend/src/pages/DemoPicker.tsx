import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Compass, Smartphone } from "lucide-react";
import { resetDemo } from "../lib/demo";
import { MODE, caseIdForPatient, request, usePeople } from "../lib/api";
import type { ApiError } from "../lib/types";
import { usePersona } from "../lib/persona";
import { initials, label, ROLE_LABELS, shortName } from "../lib/labels";
import { Wordmark } from "../components/Wordmark";
import { Button, Dialog, toastError, useToast } from "../components/ui";

const LINES: Record<string, string> = {
  "dr-fatima": "Owns Rajesh's false “completed” and Noura's missed appointment",
  "dr-salma": "Sunita's urgent message; a handoff waiting to be accepted",
  "nav-aisha": "Barrier tasks; can't close cases",
  "dr-hessa": "Clinic lead: level-2 escalations",
  "coord-sara": "Programme view across all clinics",
  "dr-omar": "GI specialist: e-consults",
  "dr-lina": "GI specialist: e-consults",
  "p-noura": "Patient view in Arabic",
  "p-rajesh": "Patient view in English",
};

export default function DemoPicker() {
  const { setPersona, setTour } = usePersona();
  const nav = useNavigate();
  const qc = useQueryClient();
  const toast = useToast();
  const [confirm, setConfirm] = useState(false);
  const [resetting, setResetting] = useState(false);
  const people = usePeople();
  const dir = people.data ?? { staff: [], patients: [] };
  const pick = (id: string, to: string) => { setPersona(id); nav(to); };
  // The tour opens straight on the headline case: Rajesh, "completed" in Malaffi with no colonoscopy.
  const startTour = async () => {
    setPersona("dr-fatima");
    setTour({ open: true, step: 0 });
    const id = await caseIdForPatient("p-rajesh", "dr-fatima").catch(() => null);
    nav(id ? `/app/cases/${id}` : "/app/work");
  };
  // The landing page's main button links here with ?tour=1, so the tour starts in one click.
  useEffect(() => {
    if (new URLSearchParams(window.location.search).get("tour") === "1") void startTour();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const staffOrder = ["dr-fatima", "nav-aisha", "dr-salma", "dr-hessa", "coord-sara", "dr-omar", "dr-lina"];
  const staff = [...dir.staff].sort((a: { id: string }, b: { id: string }) => staffOrder.indexOf(a.id) - staffOrder.indexOf(b.id));
  const patients = [...dir.patients].sort((a: { id: string }, b: { id: string }) => Number(!LINES[a.id]) - Number(!LINES[b.id]));

  const Account = ({ p, to }: { p: { id: string; name: string; role: string }; to: string }) => (
    <button type="button" onClick={() => pick(p.id, to)} className="mould flex w-full items-center gap-3 rounded bg-sheet px-4 py-3 text-start">
      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-[var(--color-paper-3)] text-[13px] font-semibold text-ink">{initials(p.name)}</span>
      <span className="min-w-0 flex-1">
        <span className="block font-semibold">{shortName(p.name)}{p.role === "patient" && <span className="font-normal text-muted"> {p.name.match(/\(\d+\)/)?.[0]}</span>}<span className="ms-2 text-[13px] font-normal text-muted">{label(ROLE_LABELS, p.role)}</span></span>
        {LINES[p.id] && <span className="mt-0.5 block truncate text-[14px] text-ink-2">{LINES[p.id]}</span>}
      </span>
      <ArrowRight size={18} className="shrink-0 text-muted rtl:rotate-180" aria-hidden />
    </button>
  );
  const group = (title: string, ids: string[]) => {
    const list = staff.filter((p: { id: string }) => ids.includes(p.id));
    return list.length ? (
      <section aria-label={title} className="space-y-2">
        <h3 className="text-[14px] font-medium text-muted">{title}</h3>
        {list.map((p) => <Account key={p.id} p={p} to="/app/work" />)}
      </section>
    ) : null;
  };

  return (
    <div className="min-h-screen bg-paper">
      <header className="mx-auto flex h-16 max-w-[1200px] items-center justify-between px-4 md:px-6">
        <Wordmark />
        <Link to="/" className="text-[14px] font-medium text-ink-2 hover:text-ink hover:underline">Back to the site</Link>
      </header>
      <main className="mx-auto grid max-w-[1200px] gap-8 px-4 pb-16 pt-4 md:px-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] lg:gap-12 lg:pt-10">
        <div className="plastic self-start p-6 md:p-8 lg:sticky lg:top-8">
          <h1 className="text-[40px] font-semibold leading-[44px]">Sign in to Tasleem</h1>
          <p className="mt-4 text-[17px] leading-[26px] text-ink-2">Choose an account. Each one sees only its own work: a physician's cases, a navigator's tasks, the programme's measures, or a patient's next step.</p>
          <dl className="mt-6 space-y-3 text-[15px]">
            <div className="rounded bg-sheet px-4 py-3"><dt className="font-medium">In production</dt><dd className="mt-0.5 text-ink-2">Staff sign in with their clinic account, patients with UAE Pass inside Sahatna.</dd></div>
            <div className="rounded bg-sheet px-4 py-3"><dt className="font-medium">Here</dt><dd className="mt-0.5 text-ink-2">Every account and patient is synthetic, so no password is needed.</dd></div>
          </dl>
          <button type="button" onClick={() => void startTour()} className="mt-6 inline-flex items-center gap-2 text-[15px] font-medium text-[var(--color-accent-deep)] hover:underline">
            <Compass size={18} aria-hidden />New here? Take the four-minute guided tour
          </button>
        </div>

        <div className="space-y-8">
          <h2 className="sr-only">Accounts</h2>
          {group("Family physicians and navigators", ["dr-fatima", "nav-aisha", "dr-salma"])}
          {group("Specialists and clinic leads", ["dr-omar", "dr-lina", "dr-hessa"])}
          {group("Programme", ["coord-sara"])}
          <section aria-label="Patients" className="space-y-2">
            <h3 className="flex items-center gap-2 text-[14px] font-medium text-muted"><Smartphone size={16} aria-hidden />Patients, inside the Sahatna app</h3>
            {patients.slice(0, 4).map((p) => <Account key={p.id} p={p} to="/patient" />)}
            {patients.length > 4 && (
              <details className="rounded">
                <summary className="cursor-pointer py-2 text-[14px] font-medium text-ink-2 hover:text-ink">{patients.length - 4} more patients</summary>
                <div className="mt-2 space-y-2">{patients.slice(4).map((p) => <Account key={p.id} p={p} to="/patient" />)}</div>
              </details>
            )}
          </section>
          <div className="flex flex-wrap items-center gap-4 border-t border-rule pt-6 text-[14px] text-muted">
            <Button variant="quiet" onClick={() => setConfirm(true)}>Reset demo</Button>
            <span>Puts every synthetic case back to its starting point.</span>
          </div>
        </div>
      </main>
      <Dialog open={confirm} onOpenChange={setConfirm} title="Reset the demo?"
        description={MODE === "live"
          ? "The live demo is shared. This puts every synthetic case back to its starting point for everyone using it."
          : "Every change you made in this browser goes back to the recorded starting point."}>
        <div className="flex justify-end gap-2">
          <Button variant="quiet" onClick={() => setConfirm(false)}>Cancel</Button>
          <Button variant="danger" disabled={resetting} onClick={async () => {
            setResetting(true);
            try {
              if (MODE === "live") await request("core", "POST", "/v1/admin/reset-demo", {}, "coord-sara");
              resetDemo(); qc.clear(); setConfirm(false);
              toast({ tone: "done", text: "Demo reset to the starting point." });
            } catch (e) { toastError(toast, e as ApiError); } finally { setResetting(false); }
          }}>Reset demo</Button>
        </div>
      </Dialog>
    </div>
  );
}

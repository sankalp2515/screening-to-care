import type { ReactNode } from "react";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Compass, Smartphone } from "lucide-react";
import { resetDemo } from "../lib/demo";
import { usePeople } from "../lib/api";
import { usePersona } from "../lib/persona";
import { initials, label, ROLE_LABELS, shortName } from "../lib/labels";
import { Wordmark } from "../components/Wordmark";
import { Button, Dialog, useToast } from "../components/ui";

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
  const people = usePeople();
  const dir = people.data ?? { staff: [], patients: [] };
  const pick = (id: string, to: string) => { setPersona(id); nav(to); };
  const staffOrder = ["dr-fatima", "nav-aisha", "dr-salma", "dr-hessa", "coord-sara", "dr-omar", "dr-lina"];
  const staff = [...dir.staff].sort((a: { id: string }, b: { id: string }) => staffOrder.indexOf(a.id) - staffOrder.indexOf(b.id));
  const patients = [...dir.patients].sort((a: { id: string }, b: { id: string }) => Number(!LINES[a.id]) - Number(!LINES[b.id]));

  const Card = ({ p, to, icon }: { p: { id: string; name: string; role: string }; to: string; icon?: ReactNode }) => (
    <button type="button" onClick={() => pick(p.id, to)} className="press-wide flex w-full items-start gap-3 rounded border border-rule bg-sheet p-4 text-start hover:border-ink">
      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-sheet-2 text-[13px] font-semibold text-ink">{icon ?? initials(p.name)}</span>
      <span className="min-w-0 flex-1">
        <span className="block font-semibold">{shortName(p.name)}{p.role === "patient" && <span className="font-normal text-muted"> {p.name.match(/\(\d+\)/)?.[0]}</span>}</span>
        <span className="block text-[13px] text-muted">{label(ROLE_LABELS, p.role)}</span>
        {LINES[p.id] && <span className="mt-1.5 block text-[14px] leading-5 text-ink-2">{LINES[p.id]}</span>}
      </span>
    </button>
  );

  return (
    <div className="min-h-screen bg-paper">
      <header className="mx-auto flex h-16 max-w-[1100px] items-center px-4 md:px-6"><Wordmark /></header>
      <main className="mx-auto max-w-[1100px] px-4 pb-16 pt-6 md:px-6">
        <h1 className="text-[40px] font-semibold leading-[46px]">Try <em className="font-medium">Tasleem</em></h1>
        <p className="mt-2 text-[17px] text-ink-2">Choose who you are. Everything here is synthetic.</p>

        <button type="button" onClick={() => { setPersona("dr-fatima"); setTour({ open: true, step: 0 }); nav("/app/work"); }}
          className="press-wide mt-8 flex w-full items-center gap-5 rounded border-2 border-biro bg-biro-wash p-5 text-start hover:bg-[#E3E9FB]">
          <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-biro text-white"><Compass size={22} aria-hidden /></span>
          <span className="flex-1">
            <span className="block text-[18px] font-semibold text-ink">Start the guided tour as Dr. Fatima, family physician</span>
            <span className="mt-0.5 block text-ink-2">Seven steps, about three minutes. Recommended for reviewers.</span>
          </span>
          <ArrowRight size={22} className="text-biro" aria-hidden />
        </button>

        <h2 className="mt-12 text-[22px] font-semibold">Care team</h2>
        <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{staff.map((p) => <Card key={p.id} p={p} to="/app/work" />)}</div>

        <h2 className="mt-12 text-[22px] font-semibold">Patients</h2>
        <p className="mt-1 text-ink-2">The companion screen as it would appear inside the Sahatna app.</p>
        <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{patients.map((p) => <Card key={p.id} p={p} to="/patient" icon={LINES[p.id] ? <Smartphone size={18} aria-hidden /> : undefined} />)}</div>

        <div className="mt-12 flex flex-wrap gap-4 border-t border-rule pt-6">
          <Button variant="quiet" onClick={() => setConfirm(true)}>Reset demo</Button>
          <Link to="/" className="inline-flex h-10 items-center px-2 text-[14px] font-semibold text-ink-2 hover:underline">Back to site</Link>
        </div>
      </main>
      <Dialog open={confirm} onOpenChange={setConfirm} title="Reset the demo?" description="Every change you made in this browser goes back to the recorded starting point.">
        <div className="flex justify-end gap-2">
          <Button variant="quiet" onClick={() => setConfirm(false)}>Cancel</Button>
          <Button variant="danger" onClick={() => { resetDemo(); qc.clear(); setConfirm(false); toast({ tone: "done", text: "Demo reset to the recorded starting point." }); }}>Reset demo</Button>
        </div>
      </Dialog>
    </div>
  );
}

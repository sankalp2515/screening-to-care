/* Cover while away (TSL-160). A clinician names a colleague before leave: their work list and new escalations go
   to the cover until they are back. Ownership stays with them (R1). */
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { request, useDirectory } from "../lib/api";
import { usePersona } from "../lib/persona";
import { label, ROLE_LABELS, shortName } from "../lib/labels";
import type { ApiError } from "../lib/types";
import { Button, Dialog, Field, inputCls, toastError, useToast } from "./ui";

export default function CoverDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const { persona } = usePersona();
  const dir = useDirectory();
  const qc = useQueryClient();
  const toast = useToast();
  const [days, setDays] = useState(5);
  const [cover, setCover] = useState("");
  const [busy, setBusy] = useState(false);
  const me = dir.data?.staff.find((s: { id: string }) => s.id === persona) as { away_until?: string | null } | undefined;
  const colleagues = (dir.data?.staff ?? []).filter((s: { id: string; role: string; away_until?: string | null }) =>
    s.id !== persona && s.role !== "program_coordinator" && !s.away_until);

  const save = async (until: string | null) => {
    setBusy(true);
    try {
      await request("core", "PUT", "/v1/me/absence", until ? { until, cover_id: cover } : { until: null }, persona!);
      await qc.invalidateQueries();
      toast({ tone: "done", text: until ? "Cover set. Your work goes to them until you are back." : "Welcome back. Your work list is yours again." });
      onOpenChange(false);
    } catch (e) { toastError(toast, e as ApiError); } finally { setBusy(false); }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange} title="Cover while you are away"
      description="You stay the owner of your cases. Until you are back, your work list and any new escalation go to the colleague you name.">
      {me?.away_until ? (
        <div className="space-y-4">
          <p className="text-[15px]">You are away until <strong>{new Date(me.away_until).toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" })}</strong>.</p>
          <div className="flex justify-end"><Button variant="primary" disabled={busy} onClick={() => save(null)}>I am back</Button></div>
        </div>
      ) : (
        <div className="space-y-4">
          <Field label="Away for" htmlFor="cover-days">
            <select id="cover-days" className={inputCls} value={days} onChange={(e) => setDays(Number(e.target.value))}>
              {[1, 2, 3, 5, 7, 10, 14].map((d) => <option key={d} value={d}>{d} {d === 1 ? "day" : "days"}</option>)}
            </select>
          </Field>
          <Field label="Cover" htmlFor="cover-who" required>
            <select id="cover-who" className={inputCls} value={cover} onChange={(e) => setCover(e.target.value)}>
              <option value="">Choose a colleague</option>
              {colleagues.map((s: { id: string; name: string; role: string }) => (
                <option key={s.id} value={s.id}>{shortName(s.name)} · {label(ROLE_LABELS, s.role)}</option>
              ))}
            </select>
          </Field>
          <div className="flex justify-end gap-2">
            <Button variant="quiet" onClick={() => onOpenChange(false)}>Cancel</Button>
            <Button variant="primary" disabled={busy || !cover}
              onClick={() => save(new Date(Date.now() + days * 86_400_000).toISOString())}>Set cover</Button>
          </div>
        </div>
      )}
    </Dialog>
  );
}

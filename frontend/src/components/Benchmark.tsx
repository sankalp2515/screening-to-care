import { Bar, BarChart, Cell, LabelList, ResponsiveContainer, XAxis, YAxis } from "recharts";

export const EVIDENCE_URL = "https://github.com/sankalp2515/screening-to-care/blob/main/docs/evidence/REAL_WORLD_FIT.md";
const DATA = [
  { arm: "Reminders only", v: 0 },
  { arm: "Malaffi status only", v: 81.8 },
  { arm: "Tasleem", v: 99.9 },
];

export function BenchmarkChart() {
  return (
    <figure className="w-full">
      <figcaption className="mb-3 text-[14px] font-semibold text-ink">Journeys needing action that reached a named person</figcaption>
      <div className="h-[168px]" role="img" aria-label="Reminders only 0%, Malaffi status only 81.8%, Tasleem 99.9%">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={DATA} layout="vertical" margin={{ top: 0, right: 56, bottom: 0, left: 0 }} barCategoryGap={14}>
            <XAxis type="number" domain={[0, 100]} hide />
            <YAxis type="category" dataKey="arm" width={140} tickLine={false} axisLine={false} tick={{ fill: "var(--ink-2)", fontSize: 13, fontFamily: "Libre Franklin" }} />
            <Bar dataKey="v" radius={[0, 2, 2, 0]} background={{ fill: "var(--sheet-2)" }} isAnimationActive={false}>
              {DATA.map((d) => <Cell key={d.arm} fill={d.arm === "Tasleem" ? "var(--done)" : "var(--rule-strong)"} />)}
              <LabelList dataKey="v" position="right" formatter={(v: number) => `${v}%`} style={{ fill: "var(--ink)", fontSize: 13, fontFamily: "IBM Plex Mono" }} />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </figure>
  );
}

export const TILES: [string, string][] = [
  ["0 vs 160", "journeys falsely counted as done, of 2,000 (Tasleem vs status only)"],
  ["1.9 vs 16.5 days", "median time from care stopping to an alert"],
  ["241", "automated tests passing"],
  ["64 of 67", "labelled hard cases handled"],
];

export function StatTiles() {
  return (
    <dl className="grid grid-cols-2 gap-px overflow-hidden rounded border border-rule bg-rule">
      {TILES.map(([n, t]) => (
        <div key={n} className="bg-sheet p-4">
          <dt className="sr-only">{t}</dt>
          <dd className="serif text-[28px] font-semibold leading-8 tnum">{n}</dd>
          <dd className="mt-1 text-[13px] leading-[18px] text-ink-2">{t}</dd>
        </div>
      ))}
    </dl>
  );
}

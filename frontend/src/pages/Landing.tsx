import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, BellRing, Check, ClipboardCheck, Eye, FileCheck2, GitBranch, HeartHandshake, Lock, Minus, ScrollText, ShieldCheck, Sparkles, UserCheck, Users, Workflow } from "lucide-react";
import { loadBundle } from "../lib/demo";
import { MODE } from "../lib/api";
import { shortName } from "../lib/labels";
import type { Case } from "../lib/types";
import { BENCH, EVIDENCE, LIT, REAL, REPO } from "../lib/landing-facts";
import { Wordmark } from "../components/Wordmark";
import { BenchmarkChart } from "../components/Benchmark";
import { DualBars, Skeleton, StallChip, cx } from "../components/ui";

const CONTACT_EMAIL = "pilot@tasleem.example";
const PILOT_MAIL = `mailto:${CONTACT_EMAIL}?subject=${encodeURIComponent("Tasleem pilot")}`;

/* ---------- small building blocks ---------- */

function PrimaryCta({ children = "Watch a stalled case get caught", className }: { children?: ReactNode; className?: string }) {
  return (
    <Link to="/demo" className={cx("press inline-flex h-12 items-center gap-2 rounded bg-biro px-5 text-[15px] font-semibold text-white hover:bg-biro-ink", className)}>
      {children}<ArrowRight size={18} aria-hidden className="cta-arrow" />
    </Link>
  );
}
function SecondaryCta({ children = "Plan a 90-day pilot", href = PILOT_MAIL }: { children?: ReactNode; href?: string }) {
  return <a href={href} className="press inline-flex h-12 items-center rounded border border-rule-strong bg-sheet px-5 text-[15px] font-semibold text-ink hover:bg-sheet-2">{children}</a>;
}

function Section({ id, over, title, lead, children, className }: { id: string; over: string; title: ReactNode; lead?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section aria-labelledby={id} className={cx("mx-auto max-w-[1200px] scroll-mt-20 px-4 py-[72px] md:px-6 md:py-[112px]", className)}>
      <div className="mb-10 border-t border-ink pt-3 md:mb-12">
        <p className="mb-6 text-[12px] font-semibold uppercase tracking-[0.06em] text-muted">{over}</p>
        <h2 id={id} className="max-w-3xl text-[32px] font-semibold leading-[38px] md:text-[44px] md:leading-[50px]">{title}</h2>
        {lead && <p className="mt-5 max-w-2xl text-[17px] leading-[27px] text-ink-2">{lead}</p>}
      </div>
      {children}
    </section>
  );
}

function Cite({ href, children }: { href: string; children: ReactNode }) {
  return <a href={href} target="_blank" rel="noreferrer" className="text-biro underline decoration-1 underline-offset-2 hover:decoration-2">{children}</a>;
}

/* ---------- hero: the real product card from the synthetic demo ---------- */

function HeroCase() {
  const [c, setC] = useState<Case | null>(null);
  useEffect(() => {
    if (MODE !== "demo") return;
    loadBundle().then((b) => {
      for (const entry of Object.values<{ detail_by_persona: Record<string, Case> }>(b.cases)) {
        const d = entry.detail_by_persona["dr-fatima"];
        if (d?.patient.id === "p-rajesh") { setC(d); return; }
      }
    }).catch(() => {});
  }, []);
  const stall = c?.stalls[0];
  const verified = c?.stages.find((s) => s.id === c.progress.verified.stage);
  return (
    <div className="enter enter-3 rounded border border-ink bg-sheet shadow-[6px_6px_0_var(--rule)]" aria-label="Product card from the synthetic demo">
      <div className="flex items-center justify-between gap-3 border-b border-rule px-5 py-3">
        <p className="text-[12px] font-semibold uppercase tracking-[0.06em] text-muted">Case sheet · synthetic</p>
        <p className="mono truncate text-[12px] text-muted">{c ? c.stages.find((s) => s.id === "REFERRED")?.evidence_ref : "ServiceRequest/…"}</p>
      </div>
      <div className="min-h-[338px] space-y-5 p-5">
        {!c ? (
          MODE === "demo"
            ? <div className="space-y-4" aria-busy="true"><Skeleton className="h-7 w-1/2" /><Skeleton className="h-16" /><Skeleton className="h-10" /><Skeleton className="h-16" /></div>
            : <StaticHeroCase />
        ) : (
          <>
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <p className="serif text-[24px] font-semibold leading-7">{c.patient.name}</p>
              <p className="text-[13px] text-ink-2">{c.pathway.name}</p>
            </div>
            <DualBars progress={c.progress} verifiedLabel={verified?.label.replace(" GI appointment", "")} />
            <p className="rounded border border-attn bg-attn-wash px-3 py-2 text-[14px] text-attn">Malaffi says <strong className="mono">{c.progress.reported.admin_status}</strong>. Evidence stops at “{verified?.label}”.</p>
            <div className="flex flex-wrap items-center gap-2">{stall && <StallChip label={stall.label} level={stall.level} />}</div>
            <dl className="grid grid-cols-2 gap-3 border-t border-rule pt-4 text-[14px]">
              <div><dt className="text-[12px] text-muted">Owner</dt><dd className="font-semibold">{shortName(c.owner.name)}</dd></div>
              <div><dt className="text-[12px] text-muted">Escalated to</dt><dd className="font-semibold">{shortName(stall?.escalated_to?.name)} <span className="font-normal text-muted">· level {stall?.level}</span></dd></div>
            </dl>
          </>
        )}
      </div>
    </div>
  );
}

/** Live mode has no bundle; show the same story without inventing data. */
function StaticHeroCase() {
  return (
    <div className="space-y-5">
      <p className="serif text-[24px] font-semibold leading-7">Rajesh K. (58)</p>
      <MiniBars reported={9} verified={6} />
      <p className="rounded border border-attn bg-attn-wash px-3 py-2 text-[14px] text-attn">Malaffi says <strong className="mono">COMPLETED</strong>. Evidence stops at “Attended”.</p>
      <p className="text-[14px] text-ink-2">Open the demo to see the live case.</p>
    </div>
  );
}

/* ---------- feature mini-visuals (static, drawn with the product's own tokens) ---------- */

function MiniBars({ reported, verified }: { reported: number; verified: number }) {
  const row = (label: string, n: number, cls: string) => (
    <div className="grid grid-cols-[72px_1fr] items-center gap-3">
      <span className="text-[12px] text-muted">{label}</span>
      <span className="flex gap-[3px]" aria-hidden>{Array.from({ length: 9 }, (_, i) => <span key={i} className={cx("h-2.5 flex-1 rounded-[1px]", i < n ? cls : "bg-sheet-2 border border-rule")} />)}</span>
    </div>
  );
  return <div className="space-y-2" role="img" aria-label={`Reported ${reported} of 9 steps, verified ${verified} of 9`}>{row("Reported", reported, "hatch")}{row("Verified", verified, "bg-ink")}</div>;
}

function FeatureVisual({ kind }: { kind: string }) {
  switch (kind) {
    case "verify":
      return <div className="space-y-3"><MiniBars reported={9} verified={6} /><p className="mono text-[12px] text-attn">gap: COMPLETED ≠ procedure + report</p></div>;
    case "ladder":
      return (
        <ol className="space-y-2 text-[13px]">
          {[["Day 0", "Dr. Fatima, owner", "bg-ink"], ["+2 days", "Aisha, navigator", "bg-attn"], ["+5 days", "Clinic lead", "bg-stop"]].map(([d, who, dot]) => (
            <li key={who} className="flex items-center gap-3"><span className={cx("h-2 w-2 rounded-full", dot)} aria-hidden /><span className="mono w-14 text-muted">{d}</span><span>{who}</span></li>
          ))}
        </ol>
      );
    case "gate":
      return (
        <div className="space-y-2 text-[13px]">
          <p className="flex items-center gap-2 rounded border border-stop bg-stop-wash px-2.5 py-1.5 text-stop"><Lock size={13} aria-hidden />Completed with report: no report on file</p>
          <p className="flex items-center gap-2 rounded border border-rule px-2.5 py-1.5 text-ink-2"><FileCheck2 size={13} aria-hidden />Plan changed: needs a signed clinician note</p>
        </div>
      );
    case "patient":
      return (
        <div className="mx-auto w-[168px] rounded-[14px] border border-ink bg-paper p-3" dir="rtl" lang="ar">
          <p className="text-[12px] leading-5">ما الذي منعك من الحضور؟</p>
          <div className="mt-2 space-y-1.5">{["أشعر بالخوف", "لا أحد يوصلني", "أريد أن يتصل بي أحد"].map((t, i) => <p key={t} className={cx("rounded-[6px] border px-2 py-1 text-[12px]", i === 1 ? "border-biro bg-biro-wash text-biro" : "border-rule bg-sheet")}>{t}</p>)}</div>
        </div>
      );
    case "ai":
      return (
        <div className="rounded border border-dashed border-ai bg-ai-wash p-3 text-[13px]">
          <p className="text-[11px] font-semibold uppercase tracking-[0.06em] text-ai">AI suggestion</p>
          <p className="mt-1">Barrier: no escort home</p>
          <div className="mt-2 flex gap-2"><span className="rounded bg-ink px-2 py-0.5 text-[12px] text-white">Confirm</span><span className="rounded border border-rule-strong bg-sheet px-2 py-0.5 text-[12px]">Change</span></div>
        </div>
      );
    default:
      return (
        <div className="mono space-y-1 text-[11px] leading-4 text-ink-2">
          {[["41", "STALL_FLAGGED", "a91f…"], ["42", "ESCALATED", "07c2…"], ["43", "CASE_CLOSED", "e5d8…"]].map(([n, t, h]) => <p key={n}><span className="text-muted">#{n}</span> {t} <span className="text-muted">prev {h}</span></p>)}
          <p className="text-done">chain verified ✓</p>
        </div>
      );
  }
}

/* ---------- page ---------- */

const NAV: [string, string][] = [["#story", "The problem"], ["#how", "How it works"], ["#proof", "Proof"], ["#pricing", "Pilot"], ["#faq", "FAQ"]];

export default function Landing() {
  return (
    <div className="bg-paper">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-2 focus:top-2 focus:z-50 focus:rounded focus:bg-sheet focus:p-2">Skip to content</a>
      <header className="sticky top-0 z-20 border-b border-rule bg-paper/95 backdrop-blur">
        <nav aria-label="Site" className="mx-auto flex h-16 max-w-[1200px] items-center gap-6 px-4 md:px-6">
          <Wordmark />
          <div className="hidden items-center gap-6 text-[14px] font-medium text-ink-2 lg:flex">
            {NAV.map(([href, t]) => <a key={href} href={href} className="link-draw hover:text-ink">{t}</a>)}
          </div>
          <div className="ms-auto flex items-center gap-3">
            <a href={PILOT_MAIL} className="hidden text-[14px] font-medium text-ink-2 hover:text-ink sm:inline">Talk to us</a>
            <Link to="/demo" className="press inline-flex h-10 items-center gap-2 rounded bg-biro px-4 text-[14px] font-semibold text-white hover:bg-biro-ink">Try the demo</Link>
          </div>
        </nav>
      </header>

      <main id="main">
        {/* 1. HERO: who it is for, the one outcome, one action, proof in the same view. */}
        <section className="mx-auto grid max-w-[1200px] items-center gap-12 px-4 pb-16 pt-12 md:px-6 lg:min-h-[calc(100vh-64px)] lg:grid-cols-[1.1fr_1fr] lg:py-14">
          <div>
            <p className="enter mb-6 flex items-center gap-3 text-[12px] font-semibold uppercase tracking-[0.06em] text-muted"><span className="h-px w-8 bg-ink" aria-hidden />For screening follow-up teams in Abu Dhabi</p>
            <h1 className="enter enter-1 text-[42px] font-semibold leading-[46px] md:text-[62px] md:leading-[66px]">Know whether the care <em className="font-medium">actually</em> happened.</h1>
            <p className="enter enter-2 mt-6 max-w-xl text-[18px] leading-[28px] text-ink-2">Malaffi tells you a referral exists. Tasleem checks it against clinical evidence, names one person when a positive screening result stalls, and keeps the case open until the colonoscopy report is back.</p>
            <div className="enter enter-2 mt-8 flex flex-wrap gap-3"><PrimaryCta /><SecondaryCta /></div>
            <p className="enter enter-3 mt-4 text-[13px] text-muted">60-second guided tour. No sign-up. Synthetic patients only.</p>
            <dl className="enter enter-3 mt-10 grid max-w-xl grid-cols-3 gap-px overflow-hidden rounded border border-rule bg-rule">
              {[[BENCH.tasleemFlagged, "of stalled journeys reach a named person"], [BENCH.falseDoneTasleem, "cases falsely counted as done"], [`${BENCH.tasleemDays} days`, "median time to an alert"]].map(([n, t]) => (
                <div key={t} className="bg-sheet px-4 py-3"><dt className="sr-only">{t}</dt><dd className="serif text-[24px] font-semibold leading-7 tnum">{n}</dd><dd className="mt-1 text-[12px] leading-4 text-ink-2">{t}</dd></div>
              ))}
            </dl>
            <p className="mt-2 text-[12px] text-muted">On a synthetic benchmark. <a href={`${EVIDENCE}/benchmark.md`} target="_blank" rel="noreferrer" className="underline underline-offset-2 hover:text-ink">How it was measured</a></p>
          </div>
          <HeroCase />
        </section>

        {/* 2. TRUST BAR: built on what the buyer already owns. */}
        <section aria-label="Built on existing systems" className="border-y border-rule bg-sheet">
          <div className="mx-auto flex max-w-[1200px] flex-wrap items-center gap-x-8 gap-y-3 px-4 py-5 md:px-6">
            <p className="text-[12px] font-semibold uppercase tracking-[0.06em] text-muted">Works beside</p>
            {["Malaffi referral events (Circular 210/2026)", "Sahatna patient app", "HL7 v2 · FHIR R4", "SNOMED CT · LOINC", "Arabic and English"].map((b) => <span key={b} className="text-[14px] font-medium text-ink-2">{b}</span>)}
          </div>
        </section>

        {/* 3. STORY: the same journey told twice, pain before the fix. */}
        <Section id="story" over="The problem" title={<>The same referral, <em className="font-medium">twice</em>.</>}
          lead="Rajesh, 58, has a positive stool test. He is referred for a colonoscopy. Here is what happens next, without and with Tasleem.">
          <div className="grid gap-px overflow-hidden rounded border border-rule bg-rule md:grid-cols-2">
            {[
              { head: "Today", tone: "text-muted", steps: [["Referral sent", true], ["Appointment booked", true], ["Rajesh attends the clinic visit", true], ["Malaffi shows COMPLETED", true], ["No colonoscopy, no report. Nobody notices.", false], ["Diagnosed later, at a worse stage", false]] },
              { head: "With Tasleem", tone: "text-biro", steps: [["Referral sent", true], ["Appointment booked", true], ["Rajesh attends the clinic visit", true], ["Malaffi shows COMPLETED, but no procedure or report arrives", true], ["Stall flagged. Dr. Fatima named owner. Navigator Aisha told in two days", true], ["Case stays open until the report is back and Rajesh is told", true]] },
            ].map((col) => (
              <div key={col.head} className="bg-sheet p-6 md:p-8">
                <p className={cx("mb-5 text-[12px] font-semibold uppercase tracking-[0.06em]", col.tone)}>{col.head}</p>
                <ol className="space-y-3">
                  {col.steps.map(([t, ok], i) => (
                    <li key={i} className="flex gap-3 text-[16px] leading-6">
                      <span className={cx("mt-1 flex h-4 w-4 shrink-0 items-center justify-center rounded-full", ok ? (col.head === "Today" ? "bg-rule-strong text-white" : "bg-done text-white") : "bg-stop text-white")} aria-hidden>{ok ? <Check size={11} strokeWidth={3} /> : <Minus size={11} strokeWidth={3} />}</span>
                      <span className={!ok ? "text-stop" : undefined}>{t as string}</span>
                    </li>
                  ))}
                </ol>
              </div>
            ))}
          </div>
          <dl className="mt-8 grid gap-6 md:grid-cols-3">
            {[
              ["42%", <>of people with a positive FIT had no colonoscopy within a year. <Cite href={LIT.martin.url}>{LIT.martin.cite}</Cite></>],
              ["Nearly half", <>of those missed a booked visit or procedure: a call could have reached them. <Cite href={LIT.martin.url}>Same study</Cite></>],
              ["9 months", <>Colonoscopy after this delay is linked to more cancer. <Cite href={LIT.forbes.url}>{LIT.forbes.cite}</Cite></>],
            ].map(([n, t], i) => (
              <div key={i} className="border-t border-rule pt-3"><dt className="serif text-[30px] font-semibold leading-9">{n}</dt><dd className="mt-1 text-[15px] leading-[23px] text-ink-2">{t}</dd></div>
            ))}
          </dl>
        </Section>

        {/* 4. VALUE PROPOSITION by role: what changes for each person who decides to use it. */}
        <Section id="value" over="What changes" title={<>One list. One owner. One <em className="font-medium">next</em> step.</>}
          lead="Every actionable result gets a clear next step, a responsible person and a documented outcome. Clinical teams stay central to every decision.">
          <div className="grid gap-px overflow-hidden rounded border border-rule bg-rule sm:grid-cols-2 lg:grid-cols-4">
            {[
              [<ClipboardCheck key="i" size={22} aria-hidden />, "Family physicians", "Only the cases that need you, with the reason and the evidence. Minutes a week, not another inbox."],
              [<Users key="i" size={22} aria-hidden />, "Navigators", "The patient's own words, a suggested barrier you confirm, and a task with a due date."],
              [<ShieldCheck key="i" size={22} aria-hidden />, "Programme leads", "Verified completion, false “done” and days to colonoscopy, by clinic and language."],
              [<HeartHandshake key="i" size={22} aria-hidden />, "Patients", "One plain question at a time in Arabic or English, and a button to ask for a call. Never a result by text."],
            ].map(([icon, t, d]) => (
              <div key={t as string} className="bg-sheet p-6">
                <span className="text-ink">{icon}</span>
                <p className="serif mt-5 text-[21px] font-semibold">{t}</p>
                <p className="mt-2 text-[15px] leading-[23px] text-ink-2">{d}</p>
              </div>
            ))}
          </div>
        </Section>

        {/* 5. HOW IT WORKS: reduce perceived complexity to four steps. */}
        <Section id="how" over="How it works" title={<>Four steps, and a <em className="font-medium">person</em> at the end of each.</>}>
          <ol className="grid gap-px overflow-hidden rounded border border-rule bg-rule md:grid-cols-2 lg:grid-cols-4">
            {[
              [<Eye key="i" size={22} aria-hidden />, "Sense", "Reads referral, booking and result events from Malaffi and labs (HL7 v2, FHIR R4)."],
              [<Workflow key="i" size={22} aria-hidden />, "Decide", "Fixed, tested rules spot stalls: booked but not attended, completed without a report, referral rejected, no reply."],
              [<BellRing key="i" size={22} aria-hidden />, "Act", "Names one owner, escalates on missed deadlines, and reaches each person on their own channel."],
              [<UserCheck key="i" size={22} aria-hidden />, "Hand off", "A clinician closes every case, on evidence. AI drafts; a person decides."],
            ].map(([icon, t, d], i) => (
              <li key={i} className="bg-sheet p-6">
                <div className="flex items-center justify-between text-ink">{icon}<span className="mono text-[12px] text-muted">0{i + 1}</span></div>
                <p className="serif mt-6 text-[22px] font-semibold">{t}</p>
                <p className="mt-2 text-[15px] leading-[23px] text-ink-2">{d}</p>
              </li>
            ))}
          </ol>
        </Section>

        {/* 6. FEATURE HIGHLIGHTS: each mechanism paired with what it means for a person. */}
        <Section id="features" over="Inside the product" title={<>Built for the moments where care is <em className="font-medium">lost</em>.</>}>
          <div className="grid gap-5 md:grid-cols-2 lg:grid-cols-3">
            {[
              ["verify", "Reported vs verified", "Every step needs evidence: an attended visit, a procedure, a report.", "A COMPLETED status can no longer hide a missing colonoscopy."],
              ["ladder", "Escalation to a named person", "Missed deadlines move up a ladder of real people, each on their own channel.", "Nobody waits on an unread queue."],
              ["gate", "Closure needs proof", "A case closes only with an allowed outcome and the evidence or signature it requires.", "No one can close a case to clear a list."],
              ["patient", "A patient app people finish", "Five plain choices, Arabic or English, right to left, one question at a time.", "Patients say why, in their words, in seconds."],
              ["ai", "AI that suggests, never decides", "Free-text replies get a suggested barrier code in a dashed box. A navigator confirms it.", "Faster triage, with a person accountable."],
              ["audit", "Tamper-evident audit", "Every change is an event in a hash-chained log you can verify.", "Every decision can be traced to a named person."],
            ].map(([kind, t, d, v]) => (
              <article key={kind} className="lift flex flex-col rounded border border-rule bg-sheet">
                <div className="flex min-h-[132px] items-center border-b border-rule bg-sheet-2 px-5 py-5"><div className="w-full"><FeatureVisual kind={kind} /></div></div>
                <div className="p-5">
                  <h3 className="serif text-[20px] font-semibold">{t}</h3>
                  <p className="mt-2 text-[15px] leading-[23px] text-ink-2">{d}</p>
                  <p className="mt-3 text-[15px] font-medium leading-[23px] text-ink">{v}</p>
                </div>
              </article>
            ))}
          </div>
        </Section>

        {/* 7. PROOF (social proof without testimonials): numbers anyone can rerun, a tightened baseline, a realistic cohort. */}
        <Section id="proof" over="Proof you can check" title={<>Tested before it is <em className="font-medium">trusted</em>.</>}
          lead="No customer logos yet, so we show what a clinical panel can verify: a benchmark against today's tools, rerun on a cohort built from published data, and the code that produced it.">
          <div className="grid items-start gap-8 lg:grid-cols-[1.2fr_1fr]">
            <div className="rounded border border-rule bg-sheet p-6"><BenchmarkChart /><p className="mt-3 text-[13px] text-muted">1,000 synthetic patients, three seeds, same messages and noise for every arm.</p></div>
            <dl className="grid grid-cols-2 gap-px overflow-hidden rounded border border-rule bg-rule">
              {[
                [`${BENCH.falseDoneTasleem} vs ${BENCH.falseDoneStatus}`, "journeys falsely counted as done (Tasleem vs status only)"],
                [`${BENCH.tasleemDays} vs ${BENCH.statusDays} d`, "median days from care stopping to an alert"],
                [REAL.neverColonoscopyFlaggedTasleem, `of people who never got a colonoscopy flagged, on a ${REAL.n}-patient cohort with a published failure mix`],
                [BENCH.tests, "automated tests passing, plus 64 of 67 labelled hard cases"],
              ].map(([n, t]) => (
                <div key={t} className="bg-sheet p-4"><dt className="sr-only">{t}</dt><dd className="serif text-[26px] font-semibold leading-8 tnum">{n}</dd><dd className="mt-1 text-[13px] leading-[18px] text-ink-2">{t}</dd></div>
              ))}
            </dl>
          </div>
          <div className="mt-8 rounded border border-rule bg-sheet p-6">
            <p className="text-[12px] font-semibold uppercase tracking-[0.06em] text-muted">Is the comparison fair?</p>
            <p className="mt-3 max-w-3xl text-[16px] leading-[25px]">We tightened the status-only monitor until it was nearly as fast ({REAL.veryTightDays} days, against Tasleem’s {REAL.medianDaysTasleem}). It then raised {REAL.veryTightAlertsPer100} alerts per 100 patients, alerted on {REAL.veryTightFalseAlertPct} of journeys that were fine, and still could not see a colonoscopy that never happened behind a COMPLETED status.</p>
            <p className="mt-4 flex flex-wrap gap-x-6 gap-y-2 text-[14px]">
              <Cite href={`${EVIDENCE}/benchmark.md`}>Three-arm benchmark</Cite>
              <Cite href={`${EVIDENCE}/REAL_WORLD_FIT.md`}>Real-world-fit analysis</Cite>
              <Cite href={`${EVIDENCE}/TEST_CASES.md`}>Every test case</Cite>
              <Cite href={REPO}>Source code</Cite>
            </p>
          </div>
          <p className="mt-4 text-[13px] text-muted">These results test the software on synthetic data. They do not show patient outcomes; that needs a clinical pilot.</p>
        </Section>

        {/* 8. CASE STUDIES: three synthetic journeys a judge or buyer can open in the demo. */}
        <Section id="cases" over="Case studies · synthetic" title={<>Three journeys you can <em className="font-medium">open</em> right now.</>}
          lead="Fictional patients, built from the failure points in published studies. Each one is a live case in the demo.">
          <div className="grid gap-5 lg:grid-cols-3">
            {[
              { who: "Rajesh, 58", tag: "False “done”", situation: "Referral marked COMPLETED in Malaffi. No colonoscopy, no report.", did: "Flagged the gap, named Dr. Fatima, escalated to navigator Aisha, refused to close the case without a report.", result: "Closure blocked by rule R3 until the report arrives." },
              { who: "Noura, 52", tag: "Missed appointment", situation: "Missed her colonoscopy. Replied in Arabic that she fears the sedation and has nobody to take her home.", did: "Showed her words with a suggested barrier; navigator Aisha confirmed it and got a task due in one day.", result: "The reason is known and owned within a day, not found weeks later." },
              { who: "Sunita, 53", tag: "Distress", situation: "Wrote that she saw blood and was frightened, while waiting for her appointment.", did: "Routed the message to a clinician the same day, on top of every list.", result: "Only Dr. Salma, a clinician, can mark it handled. A coordinator cannot." },
            ].map((cs) => (
              <article key={cs.who} className="lift flex flex-col rounded border border-rule bg-sheet p-6">
                <div className="flex items-center justify-between gap-3"><p className="serif text-[22px] font-semibold">{cs.who}</p><span className="rounded-[2px] border border-rule-strong px-2 py-0.5 text-[12px] font-medium text-ink-2">{cs.tag}</span></div>
                <dl className="mt-5 flex-1 space-y-4 text-[15px] leading-[23px]">
                  <div><dt className="text-[12px] font-semibold uppercase tracking-[0.06em] text-muted">Situation</dt><dd className="mt-1">{cs.situation}</dd></div>
                  <div><dt className="text-[12px] font-semibold uppercase tracking-[0.06em] text-muted">What Tasleem did</dt><dd className="mt-1">{cs.did}</dd></div>
                  <div><dt className="text-[12px] font-semibold uppercase tracking-[0.06em] text-done">Result in the demo</dt><dd className="mt-1">{cs.result}</dd></div>
                </dl>
                <Link to="/demo" className="link-draw mt-6 inline-flex items-center gap-1.5 self-start text-[14px] font-semibold text-biro">Open this case<ArrowRight size={15} aria-hidden /></Link>
              </article>
            ))}
          </div>
        </Section>

        {/* 9. SAFETY AND GOVERNANCE: the trust a clinical buyer needs before anything else. */}
        <Section id="safety" over="Safety and governance" title={<>Clinical teams stay in <em className="font-medium">charge</em>.</>}
          lead="Six rules are enforced in code and tested on every change. Any change that weakens one is rejected.">
          <ul className="grid gap-px overflow-hidden rounded border border-rule bg-rule sm:grid-cols-2 lg:grid-cols-3">
            {[
              [<UserCheck key="i" size={20} aria-hidden />, "R1", "Every open case has one named owner."],
              [<GitBranch key="i" size={20} aria-hidden />, "R2", "A handoff counts only when the receiver accepts."],
              [<FileCheck2 key="i" size={20} aria-hidden />, "R3", "A case closes only on evidence or a signed clinician decision."],
              [<BellRing key="i" size={20} aria-hidden />, "R4", "Every missed deadline reaches a named person."],
              [<Sparkles key="i" size={20} aria-hidden />, "R5", "AI suggests. It never closes a case, sets priority or advises a patient."],
              [<ScrollText key="i" size={20} aria-hidden />, "R6", "Every change is written to a tamper-evident audit log."],
            ].map(([icon, code, t]) => (
              <li key={code as string} className="flex gap-4 bg-sheet p-6">
                <span className="mt-0.5 text-ink">{icon}</span>
                <span><span className="mono text-[12px] text-muted">{code}</span><span className="mt-1 block text-[16px] leading-6">{t}</span></span>
              </li>
            ))}
          </ul>
          <p className="mt-6 flex items-start gap-2 text-[15px] text-ink-2"><Lock size={16} className="mt-1 shrink-0" aria-hidden />Patient messages never contain results; abnormal findings are discussed in person, as the IFHAS standard requires. Consent is recorded before any outreach.</p>
        </Section>

        {/* 10. OBJECTIONS: answer the reasons a buyer would say no, before they say it. */}
        <Section id="objections" over="Fair questions" title={<>What you might be <em className="font-medium">thinking</em>.</>}>
          <div className="grid gap-px overflow-hidden rounded border border-rule bg-rule md:grid-cols-2">
            {[
              ["“Another system for my staff to watch.”", `It sends work to the tools people already use: the EMR inbox for clinicians, Sahatna for patients. On a cohort with a published failure mix, a family physician with 20 positive results a year spends about ${REAL.fpMinutesPerWeekMid} minutes a week on it, even allowing 15 minutes per alert.`],
              ["“We already have Malaffi.”", "Tasleem reads Malaffi; it does not replace it. Malaffi carries the referral. Tasleem checks whether the care behind it happened."],
              ["“What if the AI is wrong?”", "AI never decides. Detection, owners, escalation and closure are fixed rules; with AI switched off, every one of those numbers is unchanged. AI only suggests, in a box a person confirms."],
              ["“It will flood us with alerts.”", `It raised ${REAL.alertsPer100} first alerts per 100 positive results on the realistic cohort, and alerted on ${REAL.falseAlertPct} of journeys that were going fine. A status monitor tuned to match its speed raised ${REAL.veryTightAlertsPer100}.`],
              ["“Patient data and consent.”", "Synthetic data in the demo. In a pilot: UAE-hosted, consent recorded before outreach, no results by message, and a tamper-evident log of who saw and changed what."],
              ["“Integration will take a year.”", "It reads standard HL7 v2 and FHIR R4 events that Circular 210 already requires facilities to send. The pilot starts read-only."],
            ].map(([q, a]) => (
              <div key={q} className="bg-sheet p-6 md:p-8">
                <p className="serif text-[19px] font-semibold leading-7">{q}</p>
                <p className="mt-2 text-[15px] leading-[23px] text-ink-2">{a}</p>
              </div>
            ))}
          </div>
        </Section>

        {/* 11. PRICING: a low-risk first step, then a unit price tied to value. */}
        <Section id="pricing" over="Pilot and pricing" title={<>Start with one <em className="font-medium">loop</em>.</>}
          lead="Begin with one pathway and a few clinics. Pay for the cases Tasleem is actually watching, not for seats.">
          <div className="grid gap-5 lg:grid-cols-3">
            {[
              { name: "Pilot", unit: "90 days, fixed scope", feat: false, items: ["Positive-FIT to colonoscopy pathway", "3 to 5 primary-care centres and one GI centre", "Read-only Malaffi feed", "Measured: verified completions, days to colonoscopy, false “done” found"], cta: "Plan a pilot" },
              { name: "Network", unit: "Per active case, per month", feat: true, items: ["Everything in the pilot", "Patient companion inside Sahatna", "Escalation to your own navigators and leads", "Usage metered per provider (built in)"], cta: "Talk about a network" },
              { name: "Programme", unit: "Annual licence per pathway", feat: false, items: ["Blood pressure, diabetes and other IFHAS findings", "Programme measures by clinic and language", "UAE-hosted deployment and support"], cta: "Talk about a programme" },
            ].map((p) => (
              <article key={p.name} className={cx("flex flex-col rounded border bg-sheet p-6", p.feat ? "border-ink shadow-[6px_6px_0_var(--rule)]" : "border-rule")}>
                <div className="flex items-center justify-between"><h3 className="serif text-[24px] font-semibold">{p.name}</h3>{p.feat && <span className="rounded-[2px] bg-ink px-2 py-0.5 text-[12px] font-semibold text-white">After the pilot</span>}</div>
                <p className="mt-1 text-[15px] font-medium text-ink-2">{p.unit}</p>
                <ul className="mt-6 flex-1 space-y-3 border-t border-rule pt-5">
                  {p.items.map((it) => <li key={it} className="flex gap-2.5 text-[15px] leading-[22px]"><Check size={16} className="mt-[3px] shrink-0 text-done" aria-hidden />{it}</li>)}
                </ul>
                <a href={PILOT_MAIL} className={cx("press mt-6 inline-flex h-11 items-center justify-center rounded px-4 text-[15px] font-semibold", p.feat ? "bg-biro text-white hover:bg-biro-ink" : "border border-rule-strong bg-sheet text-ink hover:bg-sheet-2")}>{p.cta}</a>
              </article>
            ))}
          </div>
          <p className="mt-5 text-[13px] text-muted">Prices are set with the first partner. The per-active-case model is a hypothesis we will test in the pilot.</p>
        </Section>

        {/* 12. FAQ: remaining practical questions, collapsed so they don't slow the scan. */}
        <Section id="faq" over="FAQ" title={<>Questions people <em className="font-medium">ask</em>.</>}>
          <div className="divide-y divide-rule rounded border border-rule bg-sheet">
            {[
              ["Who is Tasleem for?", "Family physicians, care navigators and screening programme teams who follow up positive screening results, starting with a positive stool test (FIT) and the colonoscopy that should follow."],
              ["What data does it need?", "The referral and result events Malaffi already carries (HL7 REF, FHIR R4), plus appointment and report events from the GI centre. No new data entry for clinicians."],
              ["Does it work in Arabic?", "Yes. The patient companion runs in Arabic and English, right to left, and staff see the patient's own words with their language."],
              ["Who sets the deadlines?", "The screening programme's clinical lead. The demo uses placeholder deadlines that are configuration, not code."],
              ["What does the AI do?", "It drafts case summaries and patient messages, translates, and suggests a barrier code from free text. Every output is labelled and confirmed by a person. It is off by default and the core works without it."],
              ["Where is it hosted?", "The pilot plan is a UAE-region cloud. The stack is containerised (web app, case-core, notifier, agent, HL7 connector) and not tied to one provider."],
              ["Is the demo data real?", "No. Every patient, clinician and message is synthetic, written by the team and labelled as such."],
            ].map(([q, a]) => (
              <details key={q} className="faq group px-5 py-4 md:px-6">
                <summary className="flex cursor-pointer list-none items-center justify-between gap-4 text-[17px] font-semibold leading-7"><span>{q}</span><span className="faq-mark mono text-[18px] text-muted" aria-hidden>+</span></summary>
                <p className="mt-2 max-w-3xl text-[15px] leading-[24px] text-ink-2">{a}</p>
              </details>
            ))}
          </div>
        </Section>

        {/* 13. FINAL CTA: one decision, repeated with the lowest-effort action first. */}
        <section aria-labelledby="final" className="mx-auto max-w-[1200px] px-4 pb-[72px] md:px-6 md:pb-[112px]">
          <div className="rounded border border-ink bg-sheet p-6 shadow-[6px_6px_0_var(--rule)] md:p-12">
            <h2 id="final" className="max-w-2xl text-[32px] font-semibold leading-[38px] md:text-[44px] md:leading-[50px]">See a stalled case get caught in <em className="font-medium">sixty seconds</em>.</h2>
            <p className="mt-4 max-w-xl text-[17px] leading-[27px] text-ink-2">Take the guided tour as Dr. Fatima, or open the patient app as Noura. Then tell us which clinics you would start with.</p>
            <div className="mt-8 flex flex-wrap gap-3"><PrimaryCta>Start the guided tour</PrimaryCta><SecondaryCta /></div>
          </div>
        </section>
      </main>

      <footer className="border-t border-rule">
        <div className="mx-auto flex max-w-[1200px] flex-wrap items-center justify-between gap-3 px-4 py-8 text-[13px] text-muted md:px-6">
          <p>Tasleem · Future Health Digital Innovation Challenge 2026 · Challenge 05</p>
          <p>Demo with synthetic data. No real patients. <a href={REPO} target="_blank" rel="noreferrer" className="text-biro underline underline-offset-2">GitHub</a></p>
        </div>
      </footer>
    </div>
  );
}

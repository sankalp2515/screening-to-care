import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { loadBundle } from "../lib/demo";
import { MODE, caseIdForPatient, request } from "../lib/api";
import type { Case } from "../lib/types";
import { LIT, REAL, SEHA } from "../lib/landing-facts";
import Organiser from "../components/Organiser";
import { HERO_SNAPSHOT } from "../lib/hero-snapshot";
import { SiteFooter, SiteNav } from "../components/SiteChrome";
import "../styles/landing.css";

/** Rajesh's real seeded case, live from the API (or the recorded bundle offline). The hero never invents a step. */
function useRajesh(): Case {
  // First paint from the bundled snapshot; the live case replaces it when it arrives (same steps, real dates).
  const [c, setC] = useState<Case>(HERO_SNAPSHOT);
  useEffect(() => {
    if (MODE === "live") {
      caseIdForPatient("p-rajesh", "dr-fatima")
        .then((id) => (id ? request<Case>("core", "GET", `/v1/cases/${id}`, undefined, "dr-fatima") : null))
        .then((d) => d && setC(d)).catch(() => undefined);
      return;
    }
    loadBundle().then((b) => {
      for (const e of Object.values<{ detail_by_persona: Record<string, Case> }>(b.cases)) {
        const d = e.detail_by_persona["dr-fatima"];
        if (d?.patient.id === "p-rajesh") { setC(d); return; }
      }
    }).catch(() => undefined);
  }, []);
  return c;
}

const MOMENTS = [
  { id: "verify", title: "Reported versus verified", line: "Malaffi says completed. The evidence stops at the clinic visit, so the case stays open and Dr. Fatima is named.", src: "/screens/case-rajesh.png", alt: "Rajesh's case: the decision bar asks Dr. Fatima to request the GI centre's report" },
  { id: "report", title: "The report, read", line: "The AI reads the colonoscopy report and quotes each finding. Incomplete, poor preparation: a physician confirms, and the case stays open as rebook.", src: "/screens/report-khalid.png", alt: "Khalid's colonoscopy report with each finding underlined and a Confirm findings button" },
  { id: "words", title: "The patient's own words", line: "Noura wrote in Arabic that she fears the sedation and has nobody to take her home. Aisha confirms the reason and gets a task.", src: "/screens/noura-reply.png", alt: "Noura's Arabic reply, the suggested reason and the navigator's confirm control" },
  { id: "owner", title: "One owner, one next step", line: "Each morning starts with the three cases that need you, and the one thing to do on each.", src: "/screens/my-work.png", alt: "Dr. Fatima's work list starting with three cases and their next steps" },
];

/** Named moments: one screen held while four panels scroll past it (static under 60rem). */
function Moments() {
  const [on, setOn] = useState(0);
  const refs = useRef<(HTMLElement | null)[]>([]);
  useEffect(() => {
    const io = new IntersectionObserver((es) => es.forEach((e) => { if (e.isIntersecting) setOn(Number((e.target as HTMLElement).dataset.i)); }), { rootMargin: "-45% 0px -45% 0px" });
    refs.current.forEach((r) => r && io.observe(r));
    return () => io.disconnect();
  }, []);
  return (
    <div className="moments">
      <div className="pin" aria-hidden="true">
        <div className="plate">
          {MOMENTS.map((m, i) => <figure key={m.id} className={`shot${i === on ? " is-on" : ""}`} data-slot={`moment-${m.id}`} data-kind="product" data-alt={m.alt}><img src={m.src} alt="" width={1440} height={900} loading="lazy" /></figure>)}
        </div>
      </div>
      {MOMENTS.map((m, i) => (
        <article key={m.id} className="moment" data-i={i} ref={(el) => { refs.current[i] = el; }}>
          <p className="moment-n">{String(i + 1).padStart(2, "0")}</p>
          <h3>{m.title}</h3>
          <p className="lead">{m.line}</p>
          <figure className="shot moment-shot" data-slot={`moment-${m.id}-inline`} data-kind="product" data-alt={m.alt}><img src={m.src} alt={m.alt} width={1440} height={900} loading="lazy" /></figure>
        </article>
      ))}
    </div>
  );
}

export default function Landing() {
  const rajesh = useRajesh();
  return (
    <div className="lp">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-2 focus:top-2 focus:z-50 focus:rounded focus:bg-sheet focus:p-2">Skip to content</a>
      <SiteNav />

      <main id="main">
        <section className="hero" aria-labelledby="hero-h">
          <div className="wrap hero-in">
            <div className="lede-col">
              <h1 id="hero-h">Know whether the care actually happened.</h1>
              <p className="lead">Tasleem checks every Malaffi referral against clinical evidence, and names who acts.</p>
              <div className="acts">
                <Link to="/signin" className="btn btn--primary">Open Tasleem</Link>
                <Link to="/demo?tour=1" className="btn">Watch a stalled case get caught</Link>
              </div>
              <p className="small">No sign-up: pick a synthetic account and use it as a physician, navigator, programme lead or patient.</p>
            </div>
            <div className="stage-col">
              <Organiser c={rajesh} />
            </div>
          </div>
        </section>

        <section className="sec" aria-labelledby="twice">
          <div className="wrap">
            <div className="head">
              <h2 id="twice">The same referral, twice.</h2>
              <p className="lead">Rajesh, 58, has a positive stool test and is referred for a colonoscopy.</p>
            </div>
            <div className="trays">
              <div className="tray">
                <h3>Malaffi alone</h3>
                {[["Day 5", "Referral sent"], ["Day 9", "Colonoscopy booked"], ["Day 16", "Clinic visit attended"], ["Day 17", "Status: completed"]].map(([d, t]) => (
                  <p key={t} className="slip"><span className="slip-time">{d}</span><span className="slip-text">{t}</span></p>
                ))}
                <p className="slip slip--miss"><span className="slip-time">Day 30</span><span className="slip-text">No colonoscopy, no report. Nobody notices.</span><span className="stamp stamp--grey">Missed</span></p>
              </div>
              <div className="tray tray--after">
                <h3>With Tasleem</h3>
                {[["Day 5", "Referral sent"], ["Day 9", "Colonoscopy booked"], ["Day 16", "Clinic visit attended"]].map(([d, t]) => (
                  <p key={t} className="slip"><span className="slip-time">{d}</span><span className="slip-text">{t}</span></p>
                ))}
                <p className="slip"><span className="slip-time">Day 20</span><span className="slip-text">Completed, but no report: Dr. Fatima named</span><span className="stamp stamp--given">Escalated</span></p>
                <p className="slip"><span className="slip-time">Open</span><span className="slip-text">Stays open until the report is back and Rajesh is told</span></p>
              </div>
            </div>
            <p className="cite">In Abu Dhabi's SEHA clinics, {SEHA.followedUp} of positive stool tests were followed by a colonoscopy; {SEHA.noColonoscopy} people were not, and {SEHA.missedGiVisitPct} of them had been referred, then missed the specialist visit. <a className="link" href={LIT.seha.url} target="_blank" rel="noreferrer">{LIT.seha.cite}</a></p>
          </div>
        </section>

        <section className="sec" aria-labelledby="moments">
          <div className="wrap">
            <div className="head"><h2 id="moments">Four ways a referral goes quiet.</h2></div>
            <Moments />
          </div>
        </section>

        <section className="band sec--s" aria-labelledby="ai">
          <div className="wrap">
            <h2 id="ai">AI reads the report. A physician decides.</h2>
            <p className="mint">Every value quotes the sentence it came from. 92% of findings read correctly on 28 labelled synthetic reports.</p>
          </div>
        </section>

        <section className="sec" aria-labelledby="noura">
          <div className="wrap split">
            <div className="phone-tray">
              <figure className="shot" data-slot="patient-phone" data-kind="product" data-alt="Noura's Sahatna screen in Arabic: her next step and what stopped her"><img src="/screens/patient-noura.png" alt="Noura's screen in Arabic: her next step, and a button to say what stopped her" width={390} height={844} loading="lazy" /></figure>
            </div>
            <div className="head" style={{ marginBottom: 0 }}>
              <h2 id="noura">Noura answers in Arabic.</h2>
              <p className="lead">One question at a time in Sahatna, a button to ask for a call, and never a result by text.</p>
              <p className="keys-cap">What Noura tapped, before writing in her own words</p>
              <div className="keys">
                <span className="key key--on" lang="ar" dir="rtl">أشعر بالخوف</span>
                <span className="key key--on" lang="ar" dir="rtl">لا أحد يوصلني</span>
                <span className="key" lang="ar" dir="rtl">أريد أن يتصل بي أحد</span>
              </div>
            </div>
          </div>
        </section>

        <section className="sec" aria-labelledby="beside">
          <div className="wrap">
            <div className="head"><h2 id="beside">Built beside what Abu Dhabi runs.</h2></div>
            <ul className="rows">
              {[
                ["Malaffi", "Reads referral and result events, HL7 v2 and FHIR R4, under Circular 210/2026.", "In the demo"],
                ["Sahatna", "Patients answer inside the app they already use, in Arabic or English.", "In the demo"],
                ["Six safety rules", "One owner, a two-step handoff, closure on evidence, escalation to a person, AI suggests only, a tamper-evident log.", "Enforced in code"],
                ["UAE hosting", "Azure today; UAE North and the clinic's own sign-in for the pilot.", "For the pilot"],
              ].map(([t, d, s]) => (
                <li key={t} className="row"><h3>{t}</h3><p>{d}</p><p className="row-state">{s}</p></li>
              ))}
            </ul>
          </div>
        </section>

        <section className="sec" aria-labelledby="close">
          <div className="wrap close-in">
            <div className="head" style={{ marginBottom: 0 }}>
              <h2 id="close">Use it as your team would.</h2>
              <p className="lead">Sign in as a physician, a navigator, the programme lead or a patient. Every account is synthetic.</p>
              <p className="small">On {REAL.n} synthetic patients with a published failure mix, {REAL.actionFlaggedTasleem} of stalled journeys reached a named person, against {REAL.actionFlaggedStatus} for Malaffi status alone. <Link className="link" to="/pilot#proof">How it was measured</Link></p>
              <div className="acts">
                <Link to="/signin" className="btn btn--primary">Open Tasleem</Link>
                <Link className="link" to="/demo?tour=1">Or take the guided tour</Link>
              </div>
            </div>
            <div className="plate plate--wed"><figure className="shot" data-slot="programme" data-kind="product" data-alt="The programme view: verified completion against what Malaffi says, and the national guideline scorecard"><img src="/screens/programme.png" alt="The programme view: verified completion against what Malaffi says, and the national guideline scorecard" width={1440} height={900} loading="lazy" /></figure></div>
          </div>
        </section>
      </main>

      <SiteFooter />
    </div>
  );
}

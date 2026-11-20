import { Link } from "react-router-dom";
import { BENCH, EVIDENCE, REAL } from "../lib/landing-facts";
import { PILOT_CONTACT, SiteFooter, SiteNav } from "../components/SiteChrome";
import "../styles/landing.css";

/** /pilot: the pilot plan, pricing hypothesis, proof, safety rules and fair questions, moved off the landing page
 * so that page keeps one idea a screen. Every figure comes from landing-facts.ts (reproducible in the repo). */
export default function Pilot() {
  return (
    <div className="lp">
      <SiteNav />
      <main id="main">
        <section className="pilot-hero" aria-labelledby="pilot-h">
          <div className="wrap head" style={{ marginBottom: 0 }}>
            <h1 id="pilot-h">Start with one loop.</h1>
            <p className="lead">One pathway, a few clinics, ninety days, measured against Malaffi alone.</p>
            <div className="acts">
              <a className="btn btn--primary" href={PILOT_CONTACT} target="_blank" rel="noreferrer">Start a pilot conversation</a>
              <Link className="btn" to="/demo?tour=1">Take the tour first</Link>
            </div>
          </div>
        </section>

        <section className="sec--s" aria-labelledby="plan">
          <div className="wrap">
            <div className="head"><h2 id="plan">Ninety days, four steps.</h2></div>
            <ol className="steps">
              {[
                ["Weeks 1 to 2", "Read-only feed", "Malaffi referral and result events for the positive-FIT pathway, no new data entry."],
                ["Weeks 3 to 4", "Owners named", "Three to five primary care centres and one GI centre; deadlines set by the programme's clinical lead."],
                ["Weeks 5 to 12", "Loops closed", "Stalls reach a named person; reports are read and confirmed; patients answer in Sahatna."],
                ["Week 13", "Measured", "Verified completions, days to colonoscopy and false “done” found, against the same months before."],
              ].map(([when, t, d]) => (
                <li key={t} className="step"><p className="step-when">{when}</p><h3>{t}</h3><p>{d}</p></li>
              ))}
            </ol>
          </div>
        </section>

        <section className="sec--s" aria-labelledby="pricing">
          <div className="wrap">
            <div className="head">
              <h2 id="pricing">Pay for watched cases.</h2>
              <p className="lead">A hypothesis we test in the pilot: price per active case, per month, not per seat.</p>
            </div>
            <div className="table-scroll">
              <table className="table">
                <thead><tr><th>Stage</th><th>Unit</th><th>What it covers</th></tr></thead>
                <tbody>
                  <tr><td>Pilot</td><td>90 days, fixed scope</td><td>Positive-FIT to colonoscopy, 3 to 5 centres and one GI centre, read-only Malaffi feed</td></tr>
                  <tr><td>Network</td><td>Per active case, per month</td><td>The patient companion in Sahatna, escalation to your own navigators and leads, usage metered per provider</td></tr>
                  <tr><td>Programme</td><td>Annual licence per pathway</td><td>Blood pressure, diabetes and other IFHAS findings, programme measures by clinic and language, UAE-hosted</td></tr>
                </tbody>
              </table>
            </div>
            <p className="small" style={{ marginTop: "var(--space-md)" }}>Prices are set with the first partner.</p>
          </div>
        </section>

        <section className="sec--s" aria-labelledby="proof">
          <div className="wrap">
            <div className="head">
              <h2 id="proof">Measured against Malaffi alone.</h2>
              <p className="lead">On {REAL.n} synthetic patients with a published failure mix, against monitoring Malaffi status alone.</p>
            </div>
            <div className="figs">
              <p className="fig"><b>{REAL.actionFlaggedTasleem}</b><span>of stalled journeys reached a named person, against {REAL.actionFlaggedStatus}</span></p>
              <p className="fig"><b>{REAL.falseDoneTasleem}</b><span>cases falsely counted as done, against {REAL.falseDoneStatus}</span></p>
              <p className="fig"><b>{REAL.medianDaysTasleem} d</b><span>median time to an alert, against {REAL.medianDaysStatus} days</span></p>
              <p className="fig"><b>{BENCH.tests}</b><span>automated tests, plus {BENCH.hardCases} labelled hard cases</span></p>
            </div>
            <p className="small" style={{ marginTop: "var(--space-lg)" }}>Software tested on synthetic data, not patient outcomes; that needs the pilot. <a className="link" href={`${EVIDENCE}/REAL_WORLD_FIT.md`} target="_blank" rel="noreferrer">How it was measured</a></p>
          </div>
        </section>

        <section className="sec--s" aria-labelledby="questions">
          <div className="wrap faq-wrap">
            <div className="head"><h2 id="questions">What a programme lead asks first.</h2></div>
            <div className="faq">
              {[
                ["Another system for my staff to watch?", `It sends work to the tools people already use: the clinician's inbox and Sahatna for patients. A family physician with 20 positive results a year spends about ${REAL.fpMinutesPerWeekMid} minutes a week on it.`],
                ["We already have Malaffi.", "Tasleem reads Malaffi; it does not replace it. Malaffi carries the referral. Tasleem checks whether the care behind it happened."],
                ["What if the AI is wrong?", "AI never decides. Detection, owners, escalation and closure are fixed rules. AI reads reports and replies and drafts messages, and a named person confirms every suggestion."],
                ["Will it flood us with alerts?", `It raised ${REAL.alertsPer100} first alerts per 100 positive results on the realistic cohort, and alerted on ${REAL.falseAlertPct} of journeys that were going fine.`],
                ["Patient data and consent?", "Synthetic data in the demo. In a pilot: UAE-hosted, consent recorded before outreach, no results by message, and a tamper-evident log of who saw and changed what."],
                ["Who sets the deadlines?", "The screening programme's clinical lead. The demo's deadlines are configuration, not code."],
              ].map(([q, a]) => (
                <details key={q}><summary>{q}</summary><p>{a}</p></details>
              ))}
            </div>
          </div>
        </section>
      </main>
      <SiteFooter />
    </div>
  );
}

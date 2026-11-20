import { Link } from "react-router-dom";
import { EVIDENCE, REPO } from "../lib/landing-facts";

/** The public site's chrome (landing and pilot pages): a slab nav and a mast footer, in the Dose system. */

const CHECK = <svg width="22" height="22" viewBox="0 0 32 32" aria-hidden="true"><rect width="32" height="32" rx="8" fill="var(--color-accent)" /><path d="M9 16.5l4.5 4.5L23 11" fill="none" stroke="var(--color-accent-ink)" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" /></svg>;

/** Where a pilot conversation starts until the team names an inbox: an issue on the public repository. */
export const PILOT_CONTACT = `${REPO}/issues/new?title=${encodeURIComponent("Pilot conversation")}`;

export function SiteNav() {
  return (
    <header className="nav">
      <nav aria-label="Site" className="wrap nav-in">
        <Link to="/" className="nav-mark" aria-label="Tasleem home">{CHECK}Tasleem</Link>
        <div className="nav-links">
          <a href="/#twice">The problem</a>
          <a href="/#moments">How it works</a>
          <a href="/#ai">AI</a>
          <Link to="/pilot">Pilot and pricing</Link>
          <Link to="/demo?tour=1">Guided tour</Link>
        </div>
        <div className="nav-act"><Link to="/signin" className="nav-signin">Sign in</Link><Link to="/signin" className="btn btn--primary">Open Tasleem</Link></div>
        <details className="nav-menu">
          <summary aria-label="Menu">Menu</summary>
          <div className="nav-menu-panel">
            <a href="/#twice">The problem</a>
            <a href="/#moments">How it works</a>
            <a href="/#ai">AI</a>
            <Link to="/pilot">Pilot and pricing</Link>
            <Link to="/demo?tour=1">Guided tour</Link>
            <Link to="/signin">Sign in</Link>
          </div>
        </details>
      </nav>
    </header>
  );
}

export function SiteFooter() {
  const cols: [string, [string, string][]][] = [
    ["Product", [["Open Tasleem", "/signin"], ["Guided tour", "/demo?tour=1"], ["Pilot and pricing", "/pilot"]]],
    ["Evidence", [["Three-arm benchmark", `${EVIDENCE}/benchmark.md`], ["Every test case", `${EVIDENCE}/TEST_CASES.md`], ["Source code", REPO]]],
    ["Talk to us", [["Start a pilot conversation", PILOT_CONTACT], ["How it works", "/#moments"], ["Questions", "/pilot#questions"]]],
  ];
  return (
    <footer className="foot">
      <div className="wrap">
        <p className="foot-mark" aria-hidden="true">Tasleem</p>
        <div className="foot-links">
          {cols.map(([head, links]) => (
            <nav key={head} aria-label={head}>
              <p>{head}</p>
              <ul>{links.map(([t, href]) => <li key={t}>{href.startsWith("/") && !href.includes("#") ? <Link to={href}>{t}</Link> : <a href={href} {...(href.startsWith("http") ? { target: "_blank", rel: "noreferrer" } : {})}>{t}</a>}</li>)}</ul>
            </nav>
          ))}
        </div>
        <div className="foot-legal">
          <p>Future Health Digital Innovation Challenge 2026, Challenge 05</p>
          <p>Demo with synthetic patients only</p>
        </div>
      </div>
    </footer>
  );
}

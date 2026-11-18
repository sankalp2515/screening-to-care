import type { ReactNode } from "react";
import { useEffect, useRef, useState } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { BarChart3, ChevronDown, Inbox, List, Menu, Radio, Smartphone, X, Compass, ArrowLeft } from "lucide-react";
import { MODE, useDirectory, useMe, useWork } from "../lib/api";
import { usePersona } from "../lib/persona";
import { initials, label, ROLE_LABELS, shortName } from "../lib/labels";
import { cx, Tag } from "./ui";
import { Wordmark } from "./Wordmark";
import Tour from "./Tour";

function PersonaSwitcher() {
  const { persona, setPersona } = usePersona();
  const me = useMe();
  const dir = useDirectory();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const nav = useNavigate();
  useEffect(() => {
    const h = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) setOpen(false); };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, []);
  const name = me.data?.name ?? persona ?? "";
  return (
    <div className="relative" ref={ref}>
      <button type="button" className="press flex h-10 items-center gap-2 rounded px-2 hover:bg-sheet-2" aria-haspopup="menu" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
        <span className="flex h-8 w-8 items-center justify-center rounded-full bg-ink text-[12px] font-semibold text-paper">{initials(name || "?")}</span>
        <span className="hidden text-start leading-tight sm:block">
          <span className="block text-[14px] font-semibold">{shortName(name)}</span>
          <span className="block text-[12px] text-muted">{label(ROLE_LABELS, me.data?.role)}</span>
        </span>
        <ChevronDown size={16} className="text-muted" aria-hidden />
      </button>
      {open && (
        <div role="menu" className="reveal absolute end-0 top-12 z-30 w-72 rounded border border-rule-strong bg-sheet p-1">
          <p className="px-3 pb-1 pt-2 text-[12px] font-semibold uppercase tracking-[0.06em] text-muted">Switch person (synthetic)</p>
          {dir.data?.staff.map((s) => (
            <button key={s.id} role="menuitem" type="button" onClick={() => { setPersona(s.id); setOpen(false); nav("/app/work"); }}
              className={cx("press-wide flex w-full items-center gap-3 rounded px-3 py-2 text-start hover:bg-sheet-2", s.id === persona && "bg-biro-wash")}>
              <span className="flex h-7 w-7 items-center justify-center rounded-full bg-sheet-2 text-[11px] font-semibold">{initials(s.name)}</span>
              <span className="leading-tight"><span className="block text-[14px] font-medium">{shortName(s.name)}</span><span className="block text-[12px] text-muted">{label(ROLE_LABELS, s.role)}</span></span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export default function AppShell() {
  const work = useWork();
  const { tour, setTour, setPersona } = usePersona();
  const [mobileOpen, setMobileOpen] = useState(false);
  const loc = useLocation();
  const nav = useNavigate();
  useEffect(() => setMobileOpen(false), [loc.pathname]);

  const item = (to: string, icon: ReactNode, text: string, badge?: number) => (
    <NavLink to={to} end={to === "/app/cases"} className={({ isActive }) => cx("press-wide flex h-10 items-center gap-3 rounded px-3 text-[14px] font-medium", isActive ? "bg-biro-wash text-biro-ink" : "text-ink-2 hover:bg-sheet-2 hover:text-ink")}>
      {icon}<span className="flex-1">{text}</span>
      {!!badge && <span className="mono rounded-sm bg-ink px-1.5 text-[12px] leading-5 text-paper">{badge}</span>}
    </NavLink>
  );

  const sidebar = (
    <nav aria-label="App" className="flex h-full flex-col gap-1 p-3">
      <div className="mb-4 px-2 pt-1"><Wordmark /></div>
      {item("/app/work", <Inbox size={18} aria-hidden />, "My work", work.data?.needs_action)}
      {item("/app/cases", <List size={18} aria-hidden />, "All cases")}
      {item("/app/programme", <BarChart3 size={18} aria-hidden />, "Programme")}
      {item("/app/simulator", <Radio size={18} aria-hidden />, "Live simulator")}
      <hr className="my-3 border-rule" />
      <button type="button" onClick={() => { setPersona("p-noura"); nav("/patient"); }} className="press-wide flex h-10 items-center gap-3 rounded px-3 text-start text-[14px] font-medium text-ink-2 hover:bg-sheet-2 hover:text-ink">
        <Smartphone size={18} aria-hidden />Patient view
      </button>
      <Link to="/" className="press-wide flex h-10 items-center gap-3 rounded px-3 text-[14px] font-medium text-ink-2 hover:bg-sheet-2 hover:text-ink"><ArrowLeft size={18} aria-hidden />Back to site</Link>
      <p className="mt-auto px-3 text-[12px] leading-5 text-muted">Synthetic data only. No real patients.</p>
    </nav>
  );

  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[240px_1fr]">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-2 focus:top-2 focus:z-50 focus:rounded focus:bg-sheet focus:p-2">Skip to content</a>
      <aside className="sticky top-0 hidden h-screen border-e border-rule bg-paper lg:block">{sidebar}</aside>
      {mobileOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="scrim absolute inset-0 bg-ink/40" onClick={() => setMobileOpen(false)} />
          <aside className="absolute inset-y-0 start-0 w-64 border-e border-rule bg-paper">
            <button type="button" className="absolute end-2 top-2 rounded p-2" aria-label="Close menu" onClick={() => setMobileOpen(false)}><X size={18} /></button>
            {sidebar}
          </aside>
        </div>
      )}
      <div className="min-w-0">
        <header className="sticky top-0 z-20 flex h-14 items-center gap-3 border-b border-rule bg-paper/95 px-4 backdrop-blur lg:px-6">
          <button type="button" className="press rounded p-2 lg:hidden" aria-label="Open menu" onClick={() => setMobileOpen(true)}><Menu size={20} /></button>
          <div className="flex items-center gap-2">
            <Tag tone={MODE === "demo" ? "muted" : "done"}>{MODE === "demo" ? "Demo data" : "Live API"}</Tag>
            <span className="hidden text-[13px] text-muted md:inline">Synthetic data</span>
          </div>
          <div className="ms-auto flex items-center gap-2">
            <button type="button" onClick={() => setTour({ ...tour, open: !tour.open })} aria-pressed={tour.open}
              className={cx("press flex h-10 items-center gap-2 rounded border px-3 text-[14px] font-semibold", tour.open ? "border-biro bg-biro-wash text-biro-ink" : "border-rule-strong bg-sheet text-ink hover:bg-sheet-2")}>
              <Compass size={16} aria-hidden />Tour
            </button>
            <PersonaSwitcher />
          </div>
        </header>
        <main id="main" className="px-4 py-6 lg:px-8 lg:py-8"><Outlet /></main>
      </div>
      <Tour />
    </div>
  );
}

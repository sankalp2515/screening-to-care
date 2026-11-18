import { Link } from "react-router-dom";

export function Wordmark({ to = "/" }: { to?: string }) {
  return (
    <Link to={to} className="inline-flex items-center gap-2 text-ink" aria-label="Tasleem home">
      <svg width="22" height="22" viewBox="0 0 32 32" aria-hidden><rect width="32" height="32" rx="6" fill="currentColor" /><path d="M9 16.5l4.5 4.5L23 11" fill="none" stroke="var(--paper)" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" /></svg>
      <span className="serif biro-underline text-[20px] font-semibold leading-6">Tasleem</span>
    </Link>
  );
}

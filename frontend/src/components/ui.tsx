/* Shared Sheet and biro primitives (DESIGN.md sections 5, 6.4, 9). */
import * as RD from "@radix-ui/react-dialog";
import { AlertTriangle, Check, ShieldCheck, Sparkles, X } from "lucide-react";
import { createContext, useCallback, useContext, useState, type ButtonHTMLAttributes, type ReactNode } from "react";
import type { ApiError, Progress } from "../lib/types";
import { STAGE_SHORT } from "../lib/labels";

const cx = (...c: (string | false | null | undefined)[]) => c.filter(Boolean).join(" ");
export { cx };

type BtnVariant = "primary" | "secondary" | "quiet" | "danger";
export function Button({ variant = "secondary", className, size = "md", ...p }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: BtnVariant; size?: "md" | "sm" | "lg" }) {
  const base = "press inline-flex items-center justify-center gap-2 rounded font-semibold whitespace-nowrap disabled:cursor-not-allowed";
  const sizes = { sm: "h-8 px-3 text-[13px]", md: "h-10 px-4 text-sm", lg: "h-12 px-5 text-[15px]" }[size];
  const v = {
    primary: "bg-biro text-white hover:bg-biro-ink disabled:bg-rule-strong disabled:text-muted",
    secondary: "bg-sheet text-ink border border-rule-strong hover:bg-sheet-2 disabled:text-muted disabled:bg-sheet-2",
    quiet: "text-ink-2 hover:underline underline-offset-4 disabled:text-muted px-2",
    danger: "bg-sheet text-stop border border-rule-strong hover:bg-stop-wash disabled:text-muted",
  }[variant];
  return <button type="button" {...p} className={cx(base, sizes, v, className)} />;
}

type Tone = "done" | "attn" | "stop" | "muted" | "biro" | "ai" | "ink";
export function Tag({ tone = "muted", children, className, outline }: { tone?: Tone; children: ReactNode; className?: string; outline?: boolean }) {
  const t = {
    done: "bg-done-wash text-done", attn: "bg-attn-wash text-attn", stop: "bg-stop-wash text-stop",
    muted: "bg-sheet-2 text-ink-2 border border-rule", biro: "bg-biro-wash text-biro-ink", ai: "bg-ai-wash text-ai",
    ink: "bg-ink text-paper",
  }[tone];
  return <span className={cx("inline-flex items-center gap-1 rounded-sm px-1.5 py-0.5 text-[12px] font-semibold leading-4 whitespace-nowrap", t, outline && "bg-transparent border border-current", className)}>{children}</span>;
}

/** Source-of-truth labels (DESIGN.md 6.4, Additional.md V1). */
export function Source({ kind, children }: { kind: "fact" | "rule" | "ai" | "human"; children?: ReactNode }) {
  if (kind === "fact") return <span className="inline-flex items-center gap-1.5"><Tag tone="muted">FACT</Tag>{children && <span className="mono text-[12px] text-muted">{children}</span>}</span>;
  if (kind === "rule") return <span className="inline-flex items-center gap-1.5"><span className="rounded-sm border border-rule-strong px-1.5 py-0.5 text-[12px] font-semibold leading-4 text-ink-2">RULE</span>{children && <span className="mono text-[12px] text-muted">{children}</span>}</span>;
  if (kind === "ai") return <span className="inline-flex items-center gap-1.5"><Tag tone="ai"><Sparkles size={12} aria-hidden />AI DRAFT</Tag><span className="text-[12px] text-ai">{children ?? "A person must confirm this"}</span></span>;
  return <span className="inline-flex items-center gap-1.5"><Tag tone="ink">HUMAN</Tag>{children && <span className="text-[12px] text-muted">{children}</span>}</span>;
}

export function Card({ children, className, as: As = "section", ...rest }: { children: ReactNode; className?: string; as?: "section" | "div" | "article"; [k: string]: unknown }) {
  return <As {...rest} className={cx("rounded border border-rule bg-sheet", className)}>{children}</As>;
}

export function Overline({ children, className }: { children: ReactNode; className?: string }) {
  return <p className={cx("text-[12px] font-semibold uppercase tracking-[0.06em] text-muted", className)}>{children}</p>;
}

export function Skeleton({ className }: { className?: string }) { return <div aria-hidden className={cx("skeleton animate-pulse", className)} />; }

export function ErrorState({ error, retry }: { error: ApiError | Error | null; retry?: () => void }) {
  const code = (error as ApiError)?.code;
  return (
    <div role="alert" className="flex flex-wrap items-center gap-3 rounded border border-rule bg-sheet p-4">
      <Tag tone="stop"><AlertTriangle size={12} aria-hidden />{code ?? "ERROR"}</Tag>
      <span className="text-ink">{error?.message ?? "Something went wrong."}</span>
      {retry && <Button size="sm" onClick={retry}>Retry</Button>}
    </div>
  );
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="rounded border border-dashed border-rule-strong bg-sheet-2 p-6 text-center">
      <p className="font-semibold text-ink">{title}</p>
      {children && <p className="mt-1 text-ink-2">{children}</p>}
    </div>
  );
}

export function LangTag({ lang }: { lang: string }) {
  return <span className="mono rounded-sm border border-rule px-1 text-[11px] leading-4 text-muted" aria-label={lang === "ar" ? "Arabic" : "English"}>{lang.toUpperCase()}</span>;
}

export function StallChip({ label, level }: { label: string; level: number }) {
  const tone: Tone = level >= 3 ? "stop" : "attn";
  return <Tag tone={tone} className={level === 2 ? "ring-1 ring-inset ring-current" : undefined}>{label}<span className="mono font-medium opacity-80">L{level}</span></Tag>;
}

/** The journey bar (DESIGN.md 5.5): reported (hatched) vs verified (done), gap outlined in attn. */
export function JourneyBar({ progress, compact = false, labels = false }: { progress: Progress; compact?: boolean; labels?: boolean }) {
  const of = progress.verified.of || 9;
  const v = progress.verified.step;
  const r = progress.reported.step;
  const stages = Object.keys(STAGE_SHORT);
  const cells = Array.from({ length: of }, (_, i) => {
    const n = i + 1;
    const state = n <= v ? "verified" : n <= r ? "reported" : "none";
    const name = STAGE_SHORT[stages[i]] ?? `Step ${n}`;
    const text = state === "verified" ? "verified" : state === "reported" ? "reported, not verified" : "not yet";
    return { n, state, name, text };
  });
  const h = compact ? "h-1.5" : "h-3";
  return (
    <div className="w-full">
      <div role="img" aria-label={`Verified to step ${v} of ${of}. Referral status implies step ${r}.`} className={cx("flex gap-[3px]", h)}>
        {cells.map((c) => (
          <span key={c.n} title={`${c.name}: ${c.text}`}
            className={cx("flex-1 rounded-[1px]", c.state === "verified" && "bg-done", c.state === "reported" && "hatch", c.state === "reported" && progress.gap && "outline outline-1 outline-attn", c.state === "none" && "bg-sheet-2 border border-rule")} />
        ))}
      </div>
      {labels && (
        <div className="mt-1.5 flex gap-[3px] text-[11px] text-muted">
          {cells.map((c) => <span key={c.n} className={cx("flex-1 truncate text-center", c.n === v && "font-semibold text-done")}>{c.name}</span>)}
        </div>
      )}
    </div>
  );
}

/** Two bars on one 9-step scale, the hero comparison. */
export function DualBars({ progress, verifiedLabel }: { progress: Progress; verifiedLabel?: string }) {
  const of = progress.verified.of || 9;
  return (
    <div className="space-y-3">
      <div>
        <div className="mb-1 flex items-baseline justify-between gap-2 text-[13px]"><span className="text-ink-2">Reported by referral status</span><span className="mono font-medium text-ink">{progress.reported.admin_status ?? "none"}</span></div>
        <div className="h-3 rounded-[2px] bg-sheet-2 border border-rule overflow-hidden"><div className="hatch h-full" style={{ width: `${(progress.reported.step / of) * 100}%` }} /></div>
      </div>
      <div>
        <div className="mb-1 flex items-baseline justify-between gap-2 text-[13px]"><span className="text-ink-2">Verified by clinical evidence</span><span className="font-semibold text-done">{verifiedLabel ?? progress.verified.stage}</span></div>
        <div className="relative h-3 rounded-[2px] bg-sheet-2 border border-rule overflow-hidden">
          <div className="h-full bg-done" style={{ width: `${(progress.verified.step / of) * 100}%` }} />
          {progress.gap && <div className="absolute inset-y-0 border-y-2 border-e-2 border-attn bg-attn-wash/60" style={{ insetInlineStart: `${(progress.verified.step / of) * 100}%`, width: `${((progress.reported.step - progress.verified.step) / of) * 100}%` }} />}
        </div>
      </div>
    </div>
  );
}

/* ---------- Dialog (Radix, styled per DESIGN.md 8.2) ---------- */
export function Dialog({ open, onOpenChange, title, description, children, wide }: { open: boolean; onOpenChange: (o: boolean) => void; title: string; description?: ReactNode; children: ReactNode; wide?: boolean }) {
  return (
    <RD.Root open={open} onOpenChange={onOpenChange}>
      <RD.Portal>
        <RD.Overlay className="scrim fixed inset-0 z-40 bg-ink/40" />
        <RD.Content className={cx("dlg fixed left-1/2 top-1/2 z-50 max-h-[90vh] w-[calc(100vw-32px)] -translate-x-1/2 -translate-y-1/2 overflow-y-auto rounded border border-rule-strong bg-sheet p-6", wide ? "max-w-2xl" : "max-w-lg")}>
          <div className="mb-4 flex items-start justify-between gap-4">
            <div>
              <RD.Title className="serif text-[22px] font-semibold leading-7">{title}</RD.Title>
              {description ? <RD.Description className="mt-1 text-ink-2">{description}</RD.Description> : <RD.Description className="sr-only">{title}</RD.Description>}
            </div>
            <RD.Close className="press -m-2 rounded p-2 text-ink-2 hover:bg-sheet-2" aria-label="Close dialog"><X size={18} /></RD.Close>
          </div>
          {children}
        </RD.Content>
      </RD.Portal>
    </RD.Root>
  );
}

/* ---------- Toasts ---------- */
type ToastTone = "done" | "stop" | "info";
interface ToastItem { id: number; tone: ToastTone; text: string; code?: string }
const ToastCtx = createContext<(t: Omit<ToastItem, "id">) => void>(() => {});
export const useToast = () => useContext(ToastCtx);

export function Toaster({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const push = useCallback((t: Omit<ToastItem, "id">) => {
    const id = Date.now() + Math.random();
    setItems((xs) => [...xs.slice(-2), { ...t, id }]);
    setTimeout(() => setItems((xs) => xs.filter((x) => x.id !== id)), 5200);
  }, []);
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div aria-live="polite" className="pointer-events-none fixed bottom-4 left-1/2 z-[60] flex w-[min(520px,calc(100vw-32px))] -translate-x-1/2 flex-col gap-2">
        {items.map((t) => (
          <div key={t.id} className="toast pointer-events-auto flex items-start gap-3 rounded border border-rule-strong bg-sheet px-4 py-3 text-[14px]">
            {t.tone === "done" && <Check size={18} className="mt-0.5 shrink-0 text-done" aria-hidden />}
            {t.tone === "stop" && <AlertTriangle size={18} className="mt-0.5 shrink-0 text-stop" aria-hidden />}
            {t.tone === "info" && <ShieldCheck size={18} className="mt-0.5 shrink-0 text-ink-2" aria-hidden />}
            <span className="flex-1">{t.text}{t.code && <span className="mono ms-2 text-[12px] text-muted">{t.code}</span>}</span>
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  );
}

/** Turn an ApiError into a toast with the right tone: not-recorded is neutral info. */
export function toastError(push: (t: Omit<ToastItem, "id">) => void, e: ApiError) {
  push({ tone: e.code === "DEMO_NOT_RECORDED" ? "info" : "stop", text: e.message, code: e.code });
}

export function Field({ label, htmlFor, children, hint, required }: { label: string; htmlFor: string; children: ReactNode; hint?: ReactNode; required?: boolean }) {
  return (
    <div className="space-y-1.5">
      <label htmlFor={htmlFor} className="block text-[14px] font-medium text-ink">{label}{required && <span className="ms-1 text-[12px] font-normal text-muted">(required)</span>}</label>
      {children}
      {hint && <p className="text-[13px] text-muted">{hint}</p>}
    </div>
  );
}

export const inputCls = "w-full rounded border border-rule-strong bg-sheet px-3 py-2 text-[15px] text-ink placeholder:text-muted focus-visible:outline-2 focus-visible:outline-biro";

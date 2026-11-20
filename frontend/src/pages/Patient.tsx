/* Patient companion, in the Dose system (DESIGN.md). One next step, one big button, one question at a time, an
   instant human reply, and "call me" always one tap away. No results, ever. The phone frame fits the window, so
   the page itself never scrolls; only the phone's content does. */
import { useEffect, useState, type ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";
import { CalendarDays, Check, ChevronLeft, ChevronRight, ClipboardList, Phone, MessageCircleQuestion } from "lucide-react";
import { useCommand, useDirectory, usePatientCases, usePrepCheck } from "../lib/api";
import { usePersona } from "../lib/persona";
import { dateOnly } from "../lib/labels";
import type { PatientCase } from "../lib/types";
import { Skeleton, cx, toastError, useToast } from "../components/ui";
import Tour from "../components/Tour";
import { AppointmentHelpers, ListenButton } from "../components/PatientExtras";

const T = {
  en: {
    hello: (n: string) => `Hello, ${n}`, next: "Your next step", prep: (n: number) => `Get ready: ${n} quick questions`,
    tell: "Tell us what got in the way", inWay: "Something is in the way", callMe: "I want someone to call me",
    consentTitle: "Let your care team follow up with you here", consentBody: "Only about your next step. You can turn this off at any time.",
    whatStopped: "What is in the way?", pickAll: "Choose all that fit.", words: "Tell us in your own words (optional)", send: "Send",
    q: (i: number, n: number) => `Question ${i} of ${n}`, nextBtn: "Next", notSure: "I'm not sure, please call me", back: "Back",
    thanks: (n: string) => `Thank you, ${n}.`, willContact: "Someone from your care team will contact you.",
    willCall: "Someone from your care team will call you.", distress: "A clinician has been told and will call you today.",
    nothingElse: "You don't need to do anything else now.", home: "Back to my steps", received: "Received by your care team",
    none: "You have no open steps right now. Your care team will let you know when there is something to do.", on: "On", off: "Off",
    appt: "Your appointment", more: "Other reasons", sahatna: "Sahatna", screening: "Bowel screening follow-up",
  },
  ar: {
    hello: (n: string) => `مرحباً ${n}`, next: "خطوتك التالية", prep: (n: number) => `استعد: ${n} أسئلة سريعة`,
    tell: "أخبرنا بما منعك", inWay: "هناك ما يمنعني", callMe: "أريد أن يتصل بي أحد",
    consentTitle: "السماح لفريق رعايتك بمتابعتك هنا", consentBody: "لخطوتك التالية فقط. يمكنك إيقاف ذلك في أي وقت.",
    whatStopped: "ما الذي يمنعك؟", pickAll: "اختر كل ما ينطبق عليك.", words: "أخبرنا بكلماتك (اختياري)", send: "إرسال",
    q: (i: number, n: number) => `السؤال ${i} من ${n}`, nextBtn: "التالي", notSure: "لست متأكداً، اتصلوا بي", back: "رجوع",
    thanks: (n: string) => `شكراً لك يا ${n}.`, willContact: "سيتواصل معك أحد أعضاء فريق رعايتك.",
    willCall: "سيتصل بك أحد أعضاء فريق رعايتك.", distress: "تم إبلاغ طبيب وسيتصل بك اليوم.",
    nothingElse: "لا تحتاج إلى فعل أي شيء آخر الآن.", home: "العودة إلى خطواتي", received: "استلمها فريق رعايتك",
    none: "لا توجد لديك خطوات مفتوحة الآن. سيخبرك فريق رعايتك عندما يكون هناك ما تفعله.", on: "تشغيل", off: "إيقاف",
    appt: "موعدك", more: "أسباب أخرى", sahatna: "صحتنا", screening: "متابعة فحص الأمعاء",
  },
};
const FIRST_AR: Record<string, string> = { Noura: "نورة", Ahmed: "أحمد", Fatma: "فاطمة", Hamad: "حمد", Khalfan: "خلفان", Salem: "سالم", Yousef: "يوسف", Mariam: "مريم" };

type View = { kind: "home" } | { kind: "barrier" } | { kind: "prep"; i: number; answers: Record<string, string> } | { kind: "reply"; text: string; sub?: string };

function BigButton({ children, onClick, disabled }: { children: ReactNode; onClick?: () => void; disabled?: boolean }) {
  return <button type="button" onClick={onClick} disabled={disabled} className="mould mould-primary min-h-[56px] w-full rounded-[10px] px-5 text-[18px] font-semibold disabled:cursor-not-allowed disabled:opacity-55">{children}</button>;
}
function Row({ icon, children, onClick }: { icon: ReactNode; children: ReactNode; onClick: () => void }) {
  return (
    <button type="button" onClick={onClick} className="mould flex min-h-[64px] w-full items-center gap-3.5 rounded-[12px] bg-sheet px-4 text-start text-[17px] font-medium">
      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[10px] bg-[var(--color-paper-3)] text-[var(--color-accent-deep)]">{icon}</span>
      <span className="flex-1">{children}</span>
      <ChevronRight size={20} className="text-muted rtl:rotate-180" aria-hidden />
    </button>
  );
}
/** A choice as a plastic key: mint and ringed in green when picked (Dose). */
function Key({ on, children }: { on: boolean; children: ReactNode }) {
  return <span className={cx("flex min-h-[58px] items-center gap-3.5 rounded-[12px] px-4 text-[17px] transition-[background-color,box-shadow] duration-150", on ? "bg-[color-mix(in_oklab,var(--color-accent-soft)_60%,var(--sheet))] font-semibold shadow-[inset_0_1px_0_var(--glint),0_0_0_1.5px_var(--color-accent),0_2px_0_var(--color-accent)]" : "bg-sheet shadow-[inset_0_1px_0_var(--glint),0_0_0_1px_var(--rule-strong),0_2px_0_var(--rule-strong)]")}>{children}</span>;
}

function CaseFlow({ item, lang, name }: { item: PatientCase; lang: "en" | "ar"; name: string }) {
  const t = T[lang];
  const [view, setView] = useState<View>({ kind: "home" });
  const [codes, setCodes] = useState<string[]>([]);
  const [text, setText] = useState("");
  const [more, setMore] = useState(false);
  const prep = usePrepCheck(item.case_id, lang);
  const cmd = useCommand();
  const toast = useToast();
  useEffect(() => setView({ kind: "home" }), [lang]);

  const report = (cs: string[], words: string | null, callback = false) =>
    cmd.mutate({ path: `/v1/cases/${item.case_id}/barriers`, body: { codes: cs, text: words || null } }, {
      onSuccess: (r: { distress_flagged?: boolean }) => setView({ kind: "reply", text: callback ? t.willCall : t.willContact, sub: r?.distress_flagged ? t.distress : undefined }),
      onError: (e) => toastError(toast, e),
    });
  const callMe = () => report(["WANTS_CALLBACK"], null, true);
  const back = (to: View) => (
    <button type="button" onClick={() => setView(to)} className="press -ms-2 flex min-h-[44px] items-center gap-1 rounded px-2 text-[16px] font-medium text-ink-2"><ChevronLeft size={20} className="rtl:rotate-180" aria-hidden />{t.back}</button>
  );

  if (view.kind === "reply") return (
    <div className="space-y-3.5">
      <section className="reveal ticket flex flex-col items-start gap-3 font-[inherit]" aria-live="polite">
        <span className="stamp stamp--given font-[inherit] text-[14px]"><Check size={14} strokeWidth={3} className="me-1 inline" aria-hidden />{t.received}</span>
        <p className="text-[23px] font-semibold leading-[1.45] text-ink">{t.thanks(name)}</p>
        <p className="text-[18px] leading-[1.6] text-ink">{view.text}</p>
        {view.sub && <p className="text-[18px] font-semibold leading-[1.6] text-stop">{view.sub}</p>}
        <p className="ticket-stub w-full text-[15px]">{t.nothingElse}</p>
      </section>
      <button type="button" onClick={() => setView({ kind: "home" })} className="press min-h-[48px] w-full text-[16px] font-medium text-ink-2 underline underline-offset-4">{t.home}</button>
    </div>
  );

  if (view.kind === "barrier") {
    // The reasons Abu Dhabi patients give most (BMC Cancer 2021), including a female doctor, come first.
    const FIRST = ["FEAR", "PREP_UNCLEAR", "NO_ESCORT", "FEMALE_CLINICIAN", "TRANSPORT", "COST_OR_INSURANCE"];
    const rank = (c: string) => (FIRST.includes(c) ? FIRST.indexOf(c) : FIRST.length);
    const all = item.barrier_options.filter((o) => o.code !== "WANTS_CALLBACK").sort((a, b) => rank(a.code) - rank(b.code));
    const opts = more ? all : all.slice(0, FIRST.length);
    return (
      <div className="space-y-2.5">
        {back({ kind: "home" })}
        <h2 className="font-[inherit] text-[24px] font-semibold leading-[1.4]">{t.whatStopped}</h2>
        <p className="text-[16px] text-ink-2">{t.pickAll}</p>
        <fieldset className="space-y-2.5">
          <legend className="sr-only">{t.whatStopped}</legend>
          {opts.map((o) => {
            const on = codes.includes(o.code);
            return (
              <label key={o.code} className="block cursor-pointer">
                <Key on={on}>
                  <input type="checkbox" checked={on} onChange={() => setCodes((xs) => (on ? xs.filter((x) => x !== o.code) : [...xs, o.code]))} className="h-[22px] w-[22px] accent-[var(--color-accent)]" />
                  {o.label}
                </Key>
              </label>
            );
          })}
        </fieldset>
        {!more && all.length > FIRST.length && <button type="button" onClick={() => setMore(true)} className="press min-h-[44px] text-[16px] font-medium text-ink-2 underline underline-offset-4">{t.more}</button>}
        <label htmlFor="words" className="block pt-2 text-[15px] font-semibold text-ink-2">{t.words}</label>
        <textarea id="words" rows={3} dir={lang === "ar" ? "rtl" : "ltr"} value={text} onChange={(e) => setText(e.target.value)} className="w-full resize-none rounded-[12px] border-[1.5px] border-rule-strong bg-sheet px-3.5 py-3 text-[16px] leading-[1.6]" />
        <div className="pt-2"><BigButton disabled={(!codes.length && !text.trim()) || cmd.isPending} onClick={() => report(codes, text)}>{t.send}</BigButton></div>
      </div>
    );
  }

  if (view.kind === "prep" && prep.data) {
    const qs = prep.data.questions;
    const q = qs[view.i];
    const chosen = view.answers[q.id];
    const last = view.i === qs.length - 1;
    const submit = () => cmd.mutate({ path: `/v1/me/cases/${item.case_id}/prep-check?lang=${lang}`, body: { answers: view.answers } }, {
      onSuccess: (r: { message: string }) => setView({ kind: "reply", text: r.message.replace(/^(Thank you\.|شكراً لك\.)\s*/, "") }),
      onError: (e) => toastError(toast, e),
    });
    return (
      <div className="space-y-3">
        {back(view.i === 0 ? { kind: "home" } : { ...view, i: view.i - 1 })}
        <p className="text-[14px] font-semibold text-ink-2">{t.q(view.i + 1, qs.length)}</p>
        {/* Progress as the Organiser's compartments: filled for answered questions. */}
        <div className="flex gap-1.5" aria-hidden>
          {qs.map((x, i) => <span key={x.id} className={cx("h-3 flex-1 rounded-[5px]", i <= view.i ? "cell--on" : "cell--off")} style={{ ["--t" as string]: `var(--p-${(i % 9) + 4})` }} />)}
        </div>
        <h2 className="pt-2 font-[inherit] text-[24px] font-semibold leading-[1.4]">{q.text}</h2>
        <fieldset className="space-y-2.5">
          <legend className="sr-only">{q.text}</legend>
          {q.options.map((o) => (
            <label key={o.id} className="block cursor-pointer">
              <Key on={chosen === o.id}>
                <input type="radio" name={q.id} checked={chosen === o.id} onChange={() => setView({ ...view, answers: { ...view.answers, [q.id]: o.id } })} className="h-[22px] w-[22px] accent-[var(--color-accent)]" />
                {o.text}
              </Key>
            </label>
          ))}
        </fieldset>
        <div className="pt-2"><BigButton disabled={!chosen || cmd.isPending} onClick={() => (last ? submit() : setView({ ...view, i: view.i + 1 }))}>{last ? t.send : t.nextBtn}</BigButton></div>
        <button type="button" onClick={callMe} className="press min-h-[48px] w-full text-[16px] font-medium text-ink-2 underline underline-offset-4">{t.notSure}</button>
      </div>
    );
  }

  const hasPrep = !!prep.data;
  // The one big button follows the message: a patient with an open request (e.g. a missed visit) is asked
  // what got in the way; otherwise, if a preparation check exists, it is the next step.
  const prepFirst = hasPrep && item.open_requests === 0;
  const startPrep = () => setView({ kind: "prep", i: 0, answers: {} });
  return (
    <div className="space-y-3.5">
      <section className="plastic flex flex-col gap-3.5 p-5">
        <p className="text-[14px] font-semibold text-[var(--color-accent-deep)]">{t.next}</p>
        <p className="text-[23px] font-semibold leading-[1.5] text-ink">{item.message}</p>
        <ListenButton text={item.message} lang={lang} />
        {item.appointment_at && (
          <div className="ticket !px-4 !py-3">
            <p className="flex items-center gap-2 font-[inherit] text-[13px] text-muted"><CalendarDays size={16} aria-hidden />{t.appt}</p>
            <p className="ticket-title !text-[17px]">{dateOnly(item.appointment_at, lang)}</p>
          </div>
        )}
        {prepFirst ? <BigButton onClick={startPrep}>{t.prep(prep.data!.questions.length)}</BigButton>
          : <BigButton onClick={() => setView({ kind: "barrier" })}>{t.tell}</BigButton>}
      </section>
      {item.appointment_at && <AppointmentHelpers caseId={item.case_id} at={item.appointment_at} when={dateOnly(item.appointment_at, lang)} lang={lang} />}
      <Row icon={<Phone size={22} aria-hidden />} onClick={callMe}>{t.callMe}</Row>
      {prepFirst && <Row icon={<MessageCircleQuestion size={22} aria-hidden />} onClick={() => setView({ kind: "barrier" })}>{t.inWay}</Row>}
      {hasPrep && !prepFirst && <Row icon={<ClipboardList size={22} aria-hidden />} onClick={startPrep}>{t.prep(prep.data!.questions.length)}</Row>}
      <Consent item={item} lang={lang} />
    </div>
  );
}

function Consent({ item, lang }: { item: PatientCase; lang: "en" | "ar" }) {
  const t = T[lang];
  const cmd = useCommand();
  const toast = useToast();
  const on = item.consent_given;
  return (
    <div className="flex items-center gap-3.5 rounded-[12px] bg-sheet px-[18px] py-4 shadow-[0_0_0_1px_var(--rule)]">
      <div className="flex-1">
        <p id={`cons-${item.case_id}`} className="text-[16px] font-semibold">{t.consentTitle}</p>
        <p className="text-[14px] leading-[1.6] text-ink-2">{t.consentBody}</p>
      </div>
      <button type="button" role="switch" aria-checked={on} aria-labelledby={`cons-${item.case_id}`} disabled={on || cmd.isPending}
        onClick={() => cmd.mutate({ path: `/v1/me/cases/${item.case_id}/consent`, body: {} }, { onError: (e) => toastError(toast, e) })}
        className={cx("relative h-8 w-[52px] shrink-0 rounded-full transition-[background-color] duration-150", on ? "bg-[var(--color-accent)]" : "bg-rule-strong")}>
        <span className={cx("absolute top-[3px] h-[26px] w-[26px] rounded-full bg-sheet shadow-sm transition-[inset-inline-start] duration-150", on ? "start-[23px]" : "start-[3px]")} />
        <span className="sr-only">{on ? t.on : t.off}</span>
      </button>
    </div>
  );
}

export default function Patient() {
  const { persona, setPersona } = usePersona();
  const dir = useDirectory();
  const me = dir.data?.patients.find((p) => p.id === persona);
  const [lang, setLang] = useState<"en" | "ar">(() => {
    try { const s = localStorage.getItem(`tasleem.lang.${persona}`); if (s === "en" || s === "ar") return s; } catch { /* */ }
    return "en";
  });
  useEffect(() => {
    if (!me) return;
    try { if (!localStorage.getItem(`tasleem.lang.${persona}`)) setLang(me.language === "ar" ? "ar" : "en"); } catch { setLang(me.language === "ar" ? "ar" : "en"); }
  }, [me, persona]);
  const pickLang = (l: "en" | "ar") => { setLang(l); try { localStorage.setItem(`tasleem.lang.${persona}`, l); } catch { /* */ } };
  const cases = usePatientCases(lang);
  const nav = useNavigate();
  const t = T[lang];
  const first = (me?.name ?? "").split(" ")[0];
  const name = lang === "ar" ? FIRST_AR[first] ?? first : first;
  const items = (cases.data?.items ?? []).filter((i) => i.status === "open");
  const toCare = () => { setPersona("dr-fatima"); nav("/app/work"); };

  return (
    <div className="min-h-dvh bg-paper sm:flex sm:h-dvh sm:items-center sm:justify-center sm:gap-12 sm:overflow-hidden sm:px-6">
      {/* Beside the phone on a wide screen (above it on a phone): what this is and the way back. */}
      <aside dir="ltr" lang="en" className="mx-auto flex max-w-[440px] flex-col gap-3 px-4 pb-3 pt-4 font-sans sm:mx-0 sm:max-w-[300px] sm:px-0 sm:pb-0 sm:pt-0">
        <p className="hidden text-[13px] font-medium text-[var(--color-accent-deep)] sm:block">Patient companion</p>
        <h2 className="hidden text-[30px] font-semibold leading-[34px] sm:block">What {first || "the patient"} sees in Sahatna</h2>
        <p className="hidden text-[15px] leading-[23px] text-ink-2 sm:block">One next step at a time, in Arabic or English. Never a result by message. A call is always one tap away.</p>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-[14px]">
          <button type="button" className="press font-semibold text-[var(--color-accent-deep)] hover:underline" onClick={toCare}>← Care team view</button>
          <label className="inline-flex items-center gap-1.5 text-ink-2">Patient
            <select value={persona ?? ""} onChange={(e) => setPersona(e.target.value)} className="rounded-[8px] border border-rule-strong bg-sheet px-1.5 py-1 text-[13px]">
              {dir.data?.patients.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          </label>
          <Link to="/" className="text-ink-2 hover:underline">Site</Link>
        </div>
        <p className="hidden text-[12px] text-muted sm:block">Synthetic patients. In production this screen lives inside the Sahatna app.</p>
      </aside>

      <div dir={lang === "ar" ? "rtl" : "ltr"} lang={lang}
        className="mx-auto flex min-h-[calc(100dvh-120px)] w-full max-w-[440px] flex-col overflow-hidden bg-paper sm:mx-0 sm:h-[min(844px,calc(100dvh-48px))] sm:min-h-0 sm:w-[390px] sm:rounded-[28px] sm:shadow-[0_0_0_1px_var(--rule-strong),0_30px_60px_-30px_color-mix(in_oklab,var(--ink)_35%,transparent)]">
        <header className="shrink-0 border-b border-rule bg-sheet px-5 pb-4 pt-[18px]">
          <p className="mb-1 flex items-center gap-2 text-[12px] font-medium text-muted"><span className="inline-block h-4 w-4 rounded-[5px] bg-[var(--color-accent)]" aria-hidden /><b className="font-semibold text-ink-2">{t.sahatna}</b><span>{t.screening}</span></p>
          <div className="flex items-center justify-between gap-3">
            <h1 className="font-[inherit] text-[24px] font-semibold leading-8">{t.hello(name)}</h1>
            <div className="inline-flex rounded-[10px] bg-[var(--color-paper-2)] p-[3px] shadow-[inset_0_0_0_1px_var(--rule)]" role="group" aria-label={lang === "ar" ? "اللغة" : "Language"}>
              <button type="button" aria-pressed={lang === "en"} lang="en" onClick={() => pickLang("en")} className={cx("min-h-[38px] rounded-[8px] px-3.5 font-sans text-[14px] font-semibold transition-[background-color,box-shadow] duration-150", lang === "en" ? "bg-sheet text-ink shadow-[0_1px_2px_color-mix(in_oklab,var(--ink)_15%,transparent)]" : "text-ink-2")}>EN</button>
              <button type="button" aria-pressed={lang === "ar"} lang="ar" onClick={() => pickLang("ar")} className={cx("min-h-[38px] rounded-[8px] px-3.5 font-[family-name:var(--font-arabic)] text-[14px] font-semibold transition-[background-color,box-shadow] duration-150", lang === "ar" ? "bg-sheet text-ink shadow-[0_1px_2px_color-mix(in_oklab,var(--ink)_15%,transparent)]" : "text-ink-2")}>عربي</button>
            </div>
          </div>
        </header>
        <main className="flex-1 space-y-3.5 overflow-y-auto p-4">
          {cases.isLoading ? <><Skeleton className="h-52 rounded-[12px]" /><Skeleton className="h-16 rounded-[12px]" /></>
            : cases.error ? <p role="alert" className="rounded-[12px] bg-sheet p-5 text-[17px]">{cases.error.message}</p>
            : items.length === 0 ? <p className="rounded-[12px] bg-sheet p-5 text-[17px] leading-[1.6]">{t.none}</p>
            : items.map((it) => <CaseFlow key={it.case_id + lang} item={it} lang={lang} name={name} />)}
        </main>
      </div>
      <Tour />
    </div>
  );
}

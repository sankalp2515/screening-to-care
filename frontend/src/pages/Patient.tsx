/* Patient companion (DESIGN.md section 11). One next step, one big button, one question at a time,
   an instant human reply, and "call me" always one tap away. No results, ever. */
import { useEffect, useState, type ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";
import { CalendarDays, Check, ChevronLeft, ChevronRight, ClipboardList, Phone, MessageCircleQuestion } from "lucide-react";
import { useCommand, useDirectory, usePatientCases, usePrepCheck } from "../lib/api";
import { usePersona } from "../lib/persona";
import { dateOnly } from "../lib/labels";
import type { PatientCase } from "../lib/types";
import { Skeleton, cx, toastError, useToast } from "../components/ui";
import Tour from "../components/Tour";

const T = {
  en: {
    hello: (n: string) => `Hello, ${n}`, next: "Your next step", prep: (n: number) => `Get ready: ${n} quick questions`,
    tell: "Tell us what got in the way", inWay: "Something is in the way", callMe: "I want someone to call me",
    consentTitle: "Let your care team follow up with you here", consentBody: "Only about your next step. You can turn this off at any time.",
    whatStopped: "What is in the way?", pickAll: "Choose all that fit.", words: "Tell us in your own words (optional)", send: "Send",
    q: (i: number, n: number) => `Question ${i} of ${n}`, nextBtn: "Next", notSure: "I'm not sure, please call me", back: "Back",
    thanks: (n: string) => `Thank you, ${n}.`, willContact: "Someone from your care team will contact you.",
    willCall: "Someone from your care team will call you.", distress: "A clinician has been told and will call you today.",
    nothingElse: "You don't need to do anything else now.", home: "Back to my steps",
    sample: "Sample screen with synthetic data. In production this lives inside the Sahatna app.", careView: "Back to care team view",
    none: "You have no open steps right now. Your care team will let you know when there is something to do.", on: "On", off: "Off",
    appt: "Appointment", more: "Other reasons",
  },
  ar: {
    hello: (n: string) => `مرحباً ${n}`, next: "خطوتك التالية", prep: (n: number) => `استعد: ${n} أسئلة سريعة`,
    tell: "أخبرنا بما منعك", inWay: "هناك ما يمنعني", callMe: "أريد أن يتصل بي أحد",
    consentTitle: "السماح لفريق رعايتك بمتابعتك هنا", consentBody: "لخطوتك التالية فقط. يمكنك إيقاف ذلك في أي وقت.",
    whatStopped: "ما الذي يمنعك؟", pickAll: "اختر كل ما ينطبق عليك.", words: "أخبرنا بكلماتك (اختياري)", send: "إرسال",
    q: (i: number, n: number) => `السؤال ${i} من ${n}`, nextBtn: "التالي", notSure: "لست متأكداً، اتصلوا بي", back: "رجوع",
    thanks: (n: string) => `شكراً لك يا ${n}.`, willContact: "سيتواصل معك أحد أعضاء فريق رعايتك.",
    willCall: "سيتصل بك أحد أعضاء فريق رعايتك.", distress: "تم إبلاغ طبيب وسيتصل بك اليوم.",
    nothingElse: "لا تحتاج إلى فعل أي شيء آخر الآن.", home: "العودة إلى خطواتي",
    sample: "شاشة توضيحية ببيانات تجريبية. في الواقع ستكون داخل تطبيق صحتنا.", careView: "Back to care team view",
    none: "لا توجد لديك خطوات مفتوحة الآن. سيخبرك فريق رعايتك عندما يكون هناك ما تفعله.", on: "تشغيل", off: "إيقاف",
    appt: "الموعد", more: "أسباب أخرى",
  },
};
const FIRST_AR: Record<string, string> = { Noura: "نورة", Ahmed: "أحمد", Fatma: "فاطمة", Hamad: "حمد", Khalfan: "خلفان", Salem: "سالم", Yousef: "يوسف" };

type View = { kind: "home" } | { kind: "barrier" } | { kind: "prep"; i: number; answers: Record<string, string> } | { kind: "reply"; text: string; sub?: string };

function BigButton({ children, onClick, disabled }: { children: ReactNode; onClick?: () => void; disabled?: boolean }) {
  return <button type="button" onClick={onClick} disabled={disabled} className="press min-h-[56px] w-full rounded-lg bg-biro px-5 text-[18px] font-semibold text-white hover:bg-biro-ink disabled:bg-rule-strong disabled:text-muted">{children}</button>;
}
function Row({ icon, children, onClick }: { icon: ReactNode; children: ReactNode; onClick: () => void }) {
  return (
    <button type="button" onClick={onClick} className="press-wide flex min-h-[64px] w-full items-center gap-3.5 rounded-[10px] border border-rule bg-sheet px-4 text-start text-[17px] font-medium hover:border-rule-strong">
      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-[#F1EDE5]">{icon}</span>
      <span className="flex-1">{children}</span>
      <ChevronRight size={20} className="text-muted rtl:rotate-180" aria-hidden />
    </button>
  );
}

function CaseFlow({ item, lang, name }: { item: PatientCase; lang: "en" | "ar"; name: string }) {
  const t = T[lang];
  const [view, setView] = useState<View>({ kind: "home" });
  const [codes, setCodes] = useState<string[]>([]);
  const [text, setText] = useState("");
  const [more, setMore] = useState(false);
  const prep = usePrepCheck(item.case_id);
  const cmd = useCommand();
  const toast = useToast();
  useEffect(() => setView({ kind: "home" }), [lang]);

  const report = (cs: string[], words: string | null, callback = false) =>
    cmd.mutate({ path: `/v1/cases/${item.case_id}/barriers`, body: { codes: cs, text: words || null } }, {
      onSuccess: (r: { distress_flagged?: boolean }) => setView({ kind: "reply", text: callback ? t.willCall : t.willContact, sub: r?.distress_flagged ? t.distress : undefined }),
      onError: (e) => toastError(toast, e),
    });
  const callMe = () => report(["WANTS_CALLBACK"], null, true);

  if (view.kind === "reply") return (
    <div className="space-y-3.5">
      <section className="reveal flex flex-col items-start gap-4 rounded-[10px] border border-rule bg-sheet px-5 py-6" aria-live="polite">
        <span className="flex h-[52px] w-[52px] items-center justify-center rounded-full bg-done-wash"><Check size={26} strokeWidth={2.4} className="text-done" aria-hidden /></span>
        <p className="text-[23px] font-semibold leading-[1.45]">{t.thanks(name)}</p>
        <p className="text-[18px] leading-[1.6]">{view.text}</p>
        {view.sub && <p className="text-[18px] font-semibold leading-[1.6] text-stop">{view.sub}</p>}
        <p className="text-[16px] text-ink-2">{t.nothingElse}</p>
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
        <button type="button" onClick={() => setView({ kind: "home" })} className="press -ms-2 flex min-h-[44px] items-center gap-1 rounded px-2 text-[16px] font-medium text-ink-2"><ChevronLeft size={20} className="rtl:rotate-180" aria-hidden />{t.back}</button>
        <h2 className="font-[inherit] text-[23px] font-semibold leading-[1.45]">{t.whatStopped}</h2>
        <p className="text-[16px] text-ink-2">{t.pickAll}</p>
        <fieldset className="space-y-2.5">
          <legend className="sr-only">{t.whatStopped}</legend>
          {opts.map((o) => {
            const on = codes.includes(o.code);
            return (
              <label key={o.code} className={cx("press-wide flex min-h-[58px] cursor-pointer items-center gap-3.5 rounded-lg border-[1.5px] bg-sheet px-4 text-[17px]", on ? "border-biro bg-biro-wash font-semibold" : "border-rule-strong")}>
                <input type="checkbox" checked={on} onChange={() => setCodes((xs) => (on ? xs.filter((x) => x !== o.code) : [...xs, o.code]))} className="h-[22px] w-[22px] accent-[var(--biro)]" />
                {o.label}
              </label>
            );
          })}
        </fieldset>
        {!more && all.length > FIRST.length && <button type="button" onClick={() => setMore(true)} className="press min-h-[44px] text-[16px] font-medium text-ink-2 underline underline-offset-4">{t.more}</button>}
        <label htmlFor="words" className="block pt-2 text-[15px] font-semibold text-ink-2">{t.words}</label>
        <textarea id="words" rows={3} dir={lang === "ar" ? "rtl" : "ltr"} value={text} onChange={(e) => setText(e.target.value)} className="w-full resize-none rounded-lg border-[1.5px] border-rule-strong bg-sheet px-3.5 py-3 text-[16px] leading-[1.6]" />
        <div className="pt-2"><BigButton disabled={(!codes.length && !text.trim()) || cmd.isPending} onClick={() => report(codes, text)}>{t.send}</BigButton></div>
      </div>
    );
  }

  if (view.kind === "prep" && prep.data) {
    const qs = prep.data.questions;
    const q = qs[view.i];
    const chosen = view.answers[q.id];
    const last = view.i === qs.length - 1;
    const submit = () => cmd.mutate({ path: `/v1/me/cases/${item.case_id}/prep-check`, body: { answers: view.answers } }, {
      onSuccess: (r: { message: string }) => setView({ kind: "reply", text: r.message.replace(/^(Thank you\.|شكراً لك\.)\s*/, "") }),
      onError: (e) => toastError(toast, e),
    });
    return (
      <div className="space-y-3">
        <button type="button" onClick={() => setView(view.i === 0 ? { kind: "home" } : { ...view, i: view.i - 1 })} className="press -ms-2 flex min-h-[44px] items-center gap-1 rounded px-2 text-[16px] font-medium text-ink-2"><ChevronLeft size={20} className="rtl:rotate-180" aria-hidden />{t.back}</button>
        <p className="text-[14px] font-semibold text-ink-2">{t.q(view.i + 1, qs.length)}</p>
        <div className="flex gap-1.5" aria-hidden>{qs.map((x, i) => <span key={x.id} className={cx("h-1.5 flex-1 rounded-full", i <= view.i ? "bg-biro" : "bg-rule")} />)}</div>
        <h2 className="pt-2 font-[inherit] text-[23px] font-semibold leading-[1.45]">{q.text}</h2>
        <fieldset className="space-y-2.5">
          <legend className="sr-only">{q.text}</legend>
          {q.options.map((o) => (
            <label key={o.id} className={cx("press-wide flex min-h-[58px] cursor-pointer items-center gap-3.5 rounded-lg border-[1.5px] bg-sheet px-4 text-[17px]", chosen === o.id ? "border-biro bg-biro-wash font-semibold" : "border-rule-strong")}>
              <input type="radio" name={q.id} checked={chosen === o.id} onChange={() => setView({ ...view, answers: { ...view.answers, [q.id]: o.id } })} className="h-[22px] w-[22px] accent-[var(--biro)]" />
              {o.text}
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
      <section className="flex flex-col gap-3.5 rounded-[10px] border border-rule bg-sheet p-5">
        <p className="text-[14px] font-semibold text-ink-2">{t.next}</p>
        <p className="text-[23px] font-semibold leading-[1.5]">{item.message}</p>
        {item.appointment_at && <p className="flex items-center gap-2 text-[16px] text-ink-2"><CalendarDays size={18} aria-hidden /><span><span className="sr-only">{t.appt}: </span>{dateOnly(item.appointment_at, lang)}</span></p>}
        {prepFirst ? <BigButton onClick={startPrep}>{t.prep(prep.data!.questions.length)}</BigButton>
          : <BigButton onClick={() => setView({ kind: "barrier" })}>{t.tell}</BigButton>}
      </section>
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
    <div className="flex items-center gap-3.5 rounded-[10px] border border-rule bg-sheet px-[18px] py-4">
      <div className="flex-1">
        <p id={`cons-${item.case_id}`} className="text-[16px] font-semibold">{t.consentTitle}</p>
        <p className="text-[14px] leading-[1.6] text-ink-2">{t.consentBody}</p>
      </div>
      <button type="button" role="switch" aria-checked={on} aria-labelledby={`cons-${item.case_id}`} disabled={on || cmd.isPending}
        onClick={() => cmd.mutate({ path: `/v1/me/cases/${item.case_id}/consent`, body: {} }, { onError: (e) => toastError(toast, e) })}
        className={cx("relative h-8 w-[52px] shrink-0 rounded-full transition-[background-color] duration-150", on ? "bg-biro" : "bg-rule-strong")}>
        <span className={cx("absolute top-[3px] h-[26px] w-[26px] rounded-full bg-white transition-[inset-inline-start] duration-150", on ? "start-[23px]" : "start-[3px]")} />
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

  return (
    <div className="min-h-screen bg-[#EDEAE2] sm:py-8">
      <div dir={lang === "ar" ? "rtl" : "ltr"} lang={lang} className="mx-auto flex min-h-screen w-full max-w-[440px] flex-col bg-paper sm:min-h-[844px] sm:max-w-[390px] sm:overflow-hidden sm:rounded-[24px] sm:border sm:border-rule-strong">
        <header className="flex items-center justify-between gap-3 border-b border-rule bg-sheet px-5 pb-4 pt-[18px]">
          <h1 className="font-[inherit] text-[23px] font-semibold leading-8">{t.hello(name)}</h1>
          <div className="inline-flex overflow-hidden rounded-lg border border-rule-strong" role="group" aria-label={lang === "ar" ? "اللغة" : "Language"}>
            <button type="button" aria-pressed={lang === "en"} lang="en" onClick={() => pickLang("en")} className={cx("press min-h-[40px] px-3.5 font-sans text-[14px] font-semibold", lang === "en" ? "bg-ink text-white" : "bg-sheet text-ink-2")}>EN</button>
            <button type="button" aria-pressed={lang === "ar"} lang="ar" onClick={() => pickLang("ar")} className={cx("press min-h-[40px] px-3.5 font-[family-name:var(--font-arabic)] text-[14px] font-semibold", lang === "ar" ? "bg-ink text-white" : "bg-sheet text-ink-2")}>عربي</button>
          </div>
        </header>
        <main className="flex-1 space-y-3.5 p-4">
          {cases.isLoading ? <><Skeleton className="h-52 rounded-[10px]" /><Skeleton className="h-16 rounded-[10px]" /></>
            : cases.error ? <p role="alert" className="rounded-[10px] border border-rule bg-sheet p-5 text-[17px]">{cases.error.message}</p>
            : items.length === 0 ? <p className="rounded-[10px] border border-rule bg-sheet p-5 text-[17px] leading-[1.6]">{t.none}</p>
            : items.map((it) => <CaseFlow key={it.case_id + lang} item={it} lang={lang} name={name} />)}
        </main>
        <footer className="space-y-2 px-5 pb-5 text-center text-[12px] leading-[1.6] text-muted">
          <p>{t.sample}</p>
          <div dir="ltr" lang="en" className="flex flex-wrap items-center justify-center gap-x-3 gap-y-1 font-sans">
            <label className="inline-flex items-center gap-1">Patient:
              <select value={persona ?? ""} onChange={(e) => setPersona(e.target.value)} className="rounded border border-rule-strong bg-sheet px-1 py-0.5 text-[12px]">
                {dir.data?.patients.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
              </select>
            </label>
            <button type="button" className="text-biro underline underline-offset-2" onClick={() => { setPersona("dr-fatima"); nav("/app/work"); }}>{T.en.careView}</button>
            <Link to="/" className="text-biro underline underline-offset-2">Site</Link>
          </div>
        </footer>
      </div>
      <Tour />
    </div>
  );
}

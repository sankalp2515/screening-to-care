/* Small things that keep patients on track (TSL-183, TSL-178): hear the next step read aloud, put the
   appointment in their own calendar, and ask a family member to come along. Nothing here carries a result:
   the calendar entry says "hospital appointment", and the share text says only when and that they need a lift. */
import { CalendarPlus, Users, Volume2 } from "lucide-react";
import { useToast } from "./ui";

const T = {
  en: {
    listen: "Listen", calendar: "Add to my calendar", escort: "Ask someone to come with me",
    summary: "Hospital appointment", note: "Open Sahatna for details. Bring someone to take you home.",
    remind: "Hospital appointment tomorrow",
    share: (when: string) => `Could you come with me to a hospital appointment on ${when}? I will need someone to take me home afterwards.`,
    copied: "Message copied. Paste it to someone you trust.",
  },
  ar: {
    listen: "استمع", calendar: "أضف إلى تقويمي", escort: "اطلب من أحد أن يرافقني",
    summary: "موعد في المستشفى", note: "افتح تطبيق صحتنا لمعرفة التفاصيل. اصطحب من يوصلك إلى البيت.",
    remind: "موعد في المستشفى غداً",
    share: (when: string) => `هل يمكنك مرافقتي إلى موعد في المستشفى يوم ${when}؟ سأحتاج إلى من يوصلني إلى البيت بعده.`,
    copied: "تم نسخ الرسالة. أرسلها إلى شخص تثق به.",
  },
};

const ics = (d: Date) => d.toISOString().replace(/[-:]/g, "").replace(/\.\d{3}/, "");

/** An .ics file with a reminder the day before. Built in the browser; nothing is sent anywhere. */
export function calendarFile(caseId: string, at: string, lang: "en" | "ar"): string {
  const t = T[lang];
  return [
    "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Tasleem//Patient companion//EN", "BEGIN:VEVENT",
    `UID:${caseId}@tasleem.demo`, `DTSTAMP:${ics(new Date())}`, `DTSTART:${ics(new Date(at))}`, "DURATION:PT2H",
    `SUMMARY:${t.summary}`, `DESCRIPTION:${t.note}`,
    "BEGIN:VALARM", "TRIGGER:-P1D", "ACTION:DISPLAY", `DESCRIPTION:${t.remind}`, "END:VALARM",
    "END:VEVENT", "END:VCALENDAR", "",
  ].join("\r\n");
}

export function ListenButton({ text, lang }: { text: string; lang: "en" | "ar" }) {
  if (typeof window === "undefined" || !("speechSynthesis" in window)) return null;
  const speak = () => {
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text);
    u.lang = lang === "ar" ? "ar-AE" : "en-GB";
    u.rate = 0.9;
    window.speechSynthesis.speak(u);
  };
  return (
    <button type="button" onClick={speak} className="press inline-flex min-h-[44px] w-fit items-center gap-2 rounded-lg border border-rule-strong bg-sheet px-3 text-[15px] font-semibold text-ink-2">
      <Volume2 size={18} aria-hidden />{T[lang].listen}
    </button>
  );
}

export function AppointmentHelpers({ caseId, at, when, lang }: { caseId: string; at: string; when: string; lang: "en" | "ar" }) {
  const t = T[lang];
  const toast = useToast();
  if (new Date(at).getTime() < Date.now()) return null;
  const addToCalendar = () => {
    const url = URL.createObjectURL(new Blob([calendarFile(caseId, at, lang)], { type: "text/calendar" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = "appointment.ics";
    a.click();
    URL.revokeObjectURL(url);
  };
  const askSomeone = async () => {
    const text = t.share(when);
    try {
      if (navigator.share) { await navigator.share({ text }); return; }
    } catch { /* the patient closed the share sheet */ return; }
    try { await navigator.clipboard.writeText(text); toast({ tone: "done", text: t.copied }); } catch { /* ignore */ }
  };
  const row = "press-wide flex min-h-[60px] w-full items-center gap-3.5 rounded-[10px] border border-rule bg-sheet px-4 text-start text-[17px] font-medium";
  return (
    <>
      <button type="button" className={row} onClick={addToCalendar}>
        <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-sheet-2"><CalendarPlus size={22} aria-hidden /></span>{t.calendar}
      </button>
      <button type="button" className={row} onClick={askSomeone}>
        <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-sheet-2"><Users size={22} aria-hidden /></span>{t.escort}
      </button>
    </>
  );
}

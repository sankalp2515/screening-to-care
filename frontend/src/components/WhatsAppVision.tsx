/* WhatsApp as a patient channel: a vision, shown with synthetic data (backlog TSL-184).
   It is not live because UAE health data must stay in the UAE (Federal Law No. 2 of 2019, Article 13) and
   WhatsApp messages pass through servers abroad. So the design sends a content-free nudge only, on opt-in,
   and a reply goes through the same rules as every other channel. */
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { CheckCheck, MessageCircle } from "lucide-react";
import { caseIdForPatient, request } from "../lib/api";
import { messagePolicy } from "../lib/demo";
import { usePersona } from "../lib/persona";
import { Card, Tag, cx, toastError, useToast } from "./ui";
import type { ApiError } from "../lib/types";

export const NUDGE = {
  en: "Hello Noura, this is your care team. You have a next step in your care. Open Sahatna to see it, or tap Call me and we will phone you.",
  ar: "مرحباً نورة، هذا فريق رعايتك. لديك خطوة تالية في رعايتك. افتحي تطبيق صحتنا لرؤيتها، أو اضغطي اتصلوا بي وسنتصل بك.",
};
const REPLIES = { en: ["Open Sahatna", "Call me", "Not now"], ar: ["افتح صحتنا", "اتصلوا بي", "ليس الآن"] };

export default function WhatsAppVision({ compact = false }: { compact?: boolean }) {
  const [lang, setLang] = useState<"en" | "ar">("ar");
  const [reply, setReply] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const { setPersona } = usePersona();
  const toast = useToast();
  const nav = useNavigate();
  const policy = messagePolicy(NUDGE[lang]);

  const callMe = async () => {
    setBusy(true);
    try {
      const id = await caseIdForPatient("p-noura", "coord-sara");
      if (!id) throw new Error("Noura's case was not found");
      // The reply enters through the same barrier endpoint as the Sahatna "call me" button: a named
      // navigator gets the call-back task (R4); nothing about the case is decided by the channel.
      await request("core", "POST", `/v1/cases/${id}/barriers`,
        { codes: ["WANTS_CALLBACK"], text: "Replied 'Call me' to the WhatsApp nudge (simulated)" }, "p-noura");
      setReply(REPLIES[lang][1]);
      toast({ tone: "done", text: "Reply received. Aisha, the navigator, now has a call-back task for Noura." });
    } catch (e) { toastError(toast, e as ApiError); } finally { setBusy(false); }
  };

  return (
    <Card className="p-4">
      <div className="flex flex-wrap items-center gap-2">
        <MessageCircle size={18} aria-hidden className="text-ink-2" />
        <h2 className="text-[17px] font-semibold">WhatsApp nudge</h2>
        <Tag tone="attn">Vision · simulated</Tag>
        <div className="ms-auto inline-flex overflow-hidden rounded border border-rule-strong" role="group" aria-label="Message language">
          {(["ar", "en"] as const).map((l) => (
            <button key={l} type="button" aria-pressed={lang === l} onClick={() => { setLang(l); setReply(null); }}
              className={cx("press h-8 px-3 text-[13px] font-semibold", lang === l ? "bg-ink text-white" : "bg-sheet text-ink-2")}>{l === "ar" ? "عربي" : "EN"}</button>
          ))}
        </div>
      </div>
      <p className="mt-1 text-[14px] text-ink-2">
        For patients who opt in. The message carries no result, no diagnosis and no link to clinical content; a reply goes through the same rules as Sahatna.
      </p>

      <div className={cx("mt-3 grid gap-4", !compact && "md:grid-cols-[minmax(0,320px)_1fr]")}>
        <div className="rounded-[18px] border border-rule-strong bg-[#ECE5DD] p-3" aria-label="Simulated WhatsApp chat">
          <p className="mb-2 text-center text-[12px] font-semibold text-ink-2">Care team · business account (simulated)</p>
          <div dir={lang === "ar" ? "rtl" : "ltr"} lang={lang} className="max-w-[92%] rounded-lg rounded-ss-none bg-white px-3 py-2 text-[14px] leading-[1.55] text-ink shadow-[0_1px_0_rgba(0,0,0,0.08)]">
            {NUDGE[lang]}
            <span className="mt-1 flex items-center justify-end gap-1 text-[11px] text-muted">08:00 <CheckCheck size={13} aria-hidden /></span>
          </div>
          <div className="mt-2 grid gap-1.5" dir={lang === "ar" ? "rtl" : "ltr"}>
            {REPLIES[lang].map((r, i) => (
              <button key={r} type="button" disabled={busy || !!reply}
                onClick={() => (i === 1 ? callMe() : i === 0 ? (setPersona("p-noura"), nav("/patient")) : setReply(r))}
                className="press rounded-lg bg-white px-3 py-2 text-[14px] font-semibold text-[#0B7A5C] disabled:opacity-60">{r}</button>
            ))}
          </div>
          {reply && (
            <div dir={lang === "ar" ? "rtl" : "ltr"} className="ms-auto mt-2 w-fit max-w-[80%] rounded-lg rounded-se-none bg-[#D9FDD3] px-3 py-2 text-[14px]">{reply}</div>
          )}
        </div>

        <dl className="space-y-2 text-[14px]">
          <div className="flex flex-wrap items-center gap-2"><dt className="font-semibold">Message policy</dt>
            <dd>{policy.ok ? <Tag tone="done">Passed: no result, no advice, no link</Tag> : <Tag tone="stop">{policy.violations[0]?.code}</Tag>}</dd></div>
          <div><dt className="font-semibold">When it sends</dt><dd className="text-ink-2">Only with the patient's opt-in, after 08:00 Gulf time, as an approved template. Sahatna stays the main channel.</dd></div>
          <div><dt className="font-semibold">What a reply does</dt><dd className="text-ink-2">"Call me" creates the same call-back request as Sahatna, so a named navigator gets the task. Try it.</dd></div>
          <div><dt className="font-semibold">Why it is not live</dt><dd className="text-ink-2">UAE health data must stay in the UAE (Federal Law No. 2 of 2019, Article 13). It goes live only after a DoH data-residency ruling (roadmap TSL-184).</dd></div>
        </dl>
      </div>
    </Card>
  );
}

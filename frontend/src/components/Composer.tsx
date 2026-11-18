import { useEffect, useState } from "react";
import { Send } from "lucide-react";
import { request, useCommand } from "../lib/api";
import { usePersona } from "../lib/persona";
import { shortName } from "../lib/labels";
import type { PatientDraft } from "../lib/types";
import { Button, Source, cx, inputCls, toastError, useToast } from "./ui";

/** Patient-message composer (spec 5.4). Send stays disabled until the IFHAS policy check passes. */
export default function Composer({ caseId, draft, defaultLanguage, meName, onSent }: { caseId: string; draft?: PatientDraft | null; defaultLanguage: string; meName?: string; onSent?: () => void }) {
  const [text, setText] = useState(draft?.draft?.text ?? "");
  const [lang, setLang] = useState(draft?.draft?.language ?? defaultLanguage);
  const [check, setCheck] = useState<{ ok: boolean; violations: { code: string; detail: string }[] } | null>(null);
  const { persona } = usePersona();
  const send = useCommand();
  const toast = useToast();
  const edited = !!draft?.draft && text !== draft.draft.text;

  useEffect(() => {
    let live = true;
    const t = setTimeout(() => {
      request("core", "POST", "/v1/policy/patient-message-check", { text }, persona!).then((r) => live && setCheck(r)).catch(() => live && setCheck(null));
    }, 400);
    return () => { live = false; clearTimeout(t); };
  }, [text, persona]);

  const submit = () => {
    const viaDraft = draft?.send_with;
    const path = viaDraft ? viaDraft.path : `/v1/cases/${caseId}/patient-messages`;
    const body = viaDraft ? { ...viaDraft.body, text, language: lang } : { text, language: lang };
    send.mutate({ path, body }, {
      onSuccess: () => { toast({ tone: "done", text: `Sent to Sahatna by ${shortName(meName) || "you"}.` }); onSent?.(); },
      onError: (e) => toastError(toast, e),
    });
  };

  const rtl = lang === "ar";
  return (
    <div className="space-y-3">
      {draft?.draft && (
        <div className="flex flex-wrap items-center gap-2 text-[12px]">
          {draft.source === "template" ? <Source kind="rule">From the approved library · {draft.draft.template}</Source> : <Source kind="ai" />}
          {edited && <span className="text-muted">Edited by you</span>}
        </div>
      )}
      <div className="flex items-center justify-between gap-2">
        <label htmlFor={`msg-${caseId}`} className="text-[14px] font-medium">Message to the patient</label>
        <div className="inline-flex rounded border border-rule-strong p-0.5" role="group" aria-label="Message language">
          {(["en", "ar"] as const).map((l) => (
            <button key={l} type="button" aria-pressed={lang === l} onClick={() => setLang(l)} className={cx("press h-7 rounded-[3px] px-2.5 text-[13px] font-semibold", lang === l ? "bg-ink text-paper" : "text-ink-2")}>{l === "en" ? "EN" : "عربي"}</button>
          ))}
        </div>
      </div>
      <textarea id={`msg-${caseId}`} dir={rtl ? "rtl" : "ltr"} lang={lang} rows={4} value={text} onChange={(e) => { setText(e.target.value); setCheck(null); }}
        className={cx(inputCls, "resize-y leading-[24px]", draft?.draft && !edited && "border-dashed border-ai bg-ai-wash", check && !check.ok && text && "border-stop")}
        aria-describedby={`msg-help-${caseId}`} />
      {check && !check.ok && text.trim() && (
        <ul className="reveal space-y-1" aria-live="polite">
          {check.violations.map((v) => <li key={v.code} className="flex items-start gap-2 text-[13px] text-stop"><span className="mono shrink-0 text-[12px]">{v.code}</span><span>{v.detail}</span></li>)}
        </ul>
      )}
      <p id={`msg-help-${caseId}`} className="text-[13px] text-muted">Patients never receive results or advice by message. Invite them to talk instead.</p>
      <Button variant="primary" disabled={!check?.ok || send.isPending} onClick={submit}><Send size={16} aria-hidden />{send.isPending ? "Sending…" : "Send to patient"}</Button>
    </div>
  );
}

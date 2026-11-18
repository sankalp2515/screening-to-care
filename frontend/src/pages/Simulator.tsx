/* eslint-disable @typescript-eslint/no-explicit-any */
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Radio, Send } from "lucide-react";
import { request, useCommand, useScenarios } from "../lib/api";
import { bundle, demoSession } from "../lib/demo";
import { usePersona } from "../lib/persona";
import { shortName } from "../lib/labels";
import { Button, Card, ErrorState, JourneyBar, Skeleton, StallChip, Tag, cx, inputCls, toastError, useToast } from "../components/ui";

/** Synthetic lab result (positive FIT) used when no recorded sample is loaded, e.g. in live mode. */
const SAMPLE_HL7 = [
  String.raw`MSH|^~\&|LAB|SKMC|MALAFFI|DOH|20261117090000||ORU^R01|LAB-DEMO-0002|P|2.5.1`,
  "PID|1||p-demo-42acd3",
  "OBX|1|ST|29771-3^FIT^LN||Positive|||A|||F|||20261117090000",
].join(String.fromCharCode(10));

function Feed({ feed }: { feed: any[] }) {
  const [n, setN] = useState(0);
  useEffect(() => {
    setN(0);
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduce) { setN(feed.length); return; }
    const t = setInterval(() => setN((x) => (x >= feed.length ? x : x + 1)), 250);
    return () => clearInterval(t);
  }, [feed]);
  return (
    <ol className="space-y-1.5" aria-live="polite">
      {feed.slice(0, n).map((f, i) => (
        <li key={i} className="reveal flex flex-wrap items-center gap-2 rounded border border-rule bg-sheet px-3 py-2 text-[13px]">
          <span className="mono text-[12px] text-muted">{f.at.slice(5, 10)}</span>
          <span className="font-semibold">{f.source}</span>
          <span className="mono text-ink-2">{f.message}</span>
          {f.status && <Tag tone={f.status === "applied" ? "done" : "muted"} className="ms-auto">{f.status}</Tag>}
        </li>
      ))}
    </ol>
  );
}

function Ack({ text }: { text: string }) {
  return (
    <pre className="mono overflow-x-auto rounded border border-rule bg-sheet-2 p-3 text-[12px] leading-5">
      {text.split(/\r?\n|\r/).map((line, i) => {
        const aa = line.startsWith("MSA|AA");
        const bad = line.startsWith("MSA|AR") || line.startsWith("MSA|AE");
        return <div key={i} className={cx(aa && "font-semibold text-done", bad && "font-semibold text-stop")}>{line || " "}</div>;
      })}
    </pre>
  );
}

export default function Simulator() {
  const sc = useScenarios();
  const cmd = useCommand();
  const notifier = useCommand("notifier");
  const toast = useToast();
  const nav = useNavigate();
  const { persona, setPersona } = usePersona();
  const [run, setRun] = useState<{ sid: string; res: any } | null>(null);
  const [hl7, setHl7] = useState<string>(() => bundle()?.scenarios?.runs?.["new-positive-fit"]?.hl7_message ?? SAMPLE_HL7);
  const [ack, setAck] = useState<string | null>(null);
  const [, force] = useState(0);
  const sess = demoSession();

  const send = (sid: string) => cmd.mutate({ path: `/v1/demo/scenarios/${sid}`, body: {} }, {
    onSuccess: (res) => { setRun({ sid, res }); force((x) => x + 1); toast({ tone: "done", text: "Events sent. Tasleem reacted below." }); },
    onError: (e) => toastError(toast, e),
  });
  const sendHl7 = async (text: string) => {
    try { setAck(await request<string>("connector", "POST", "/v1/hl7", text, persona!)); }
    catch (e: any) { toastError(toast, e); }
  };

  const c = run?.res?.case;
  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <header>
        <h1 className="text-[32px] font-semibold leading-[38px]">Send real-world events and <em className="font-medium">watch</em> Tasleem react.</h1>
        <p className="mt-1 text-ink-2">Each scenario replays recorded Malaffi, lab and Sahatna events through the real rules. Synthetic patients only.</p>
      </header>
      <div className="grid gap-6 lg:grid-cols-[1fr_1fr]">
        <div className="space-y-3">
          {sc.isLoading ? <Skeleton className="h-80" /> : sc.error ? <ErrorState error={sc.error} /> : sc.data!.items.map((s) => {
            const locked = s.id === "report-arrives" && !sess.falseDoneRun;
            return (
              <Card key={s.id} className={cx("flex items-start gap-4 p-4", run?.sid === s.id && "border-biro")}>
                <div className="min-w-0 flex-1">
                  <p className="font-semibold">{s.title.replace(" (needs case_id)", "")}</p>
                  <p className="mt-0.5 text-[14px] text-ink-2">{s.why}</p>
                  {locked && <p className="mt-1 text-[12px] text-muted">Run “Malaffi says completed, colonoscopy never happened” first.</p>}
                </div>
                <Button size="sm" variant={run?.sid === s.id ? "secondary" : "primary"} disabled={locked || cmd.isPending} onClick={() => send(s.id)}><Send size={14} aria-hidden />Send to Tasleem</Button>
              </Card>
            );
          })}
          <Card className="p-4">
            <p className="font-semibold">Run the notifier now</p>
            <p className="mt-0.5 text-[14px] text-ink-2">Routine patient messages wait for 08:00 Gulf time (quiet hours). This runs the delivery chain immediately.</p>
            <Button className="mt-3" size="sm" disabled={notifier.isPending} onClick={() => notifier.mutate({ path: "/v1/run-once", body: {} }, {
              onSuccess: (r: any) => toast({ tone: r.pulled ? "done" : "info", text: r.pulled ? `Notifier ran: ${r.pulled} message(s) processed. Open Aisha's My work.` : "Nothing waiting to send." }),
              onError: (e) => toastError(toast, e),
            })}><Radio size={14} aria-hidden />Run the notifier now</Button>
          </Card>
        </div>

        <div className="space-y-4">
          {!run && <div className="rounded border border-dashed border-rule-strong p-6 text-ink-2">Choose a scenario. The events arrive here one by one, then the case Tasleem opened or changed.</div>}
          {run && (
            <>
              <Feed feed={run.res.feed ?? []} />
              {run.res.story && <p className="reveal rounded border-s-4 border border-biro bg-biro-wash p-3 text-[15px]">{run.res.story}</p>}
              {c && (
                <Card className="reveal space-y-3 p-4">
                  <div className="flex items-baseline justify-between gap-2"><p className="font-semibold">{c.patient.name}</p><span className="text-[13px] text-muted">Owner {shortName(c.owner.name)}</span></div>
                  <JourneyBar progress={c.progress} labels />
                  <div className="flex flex-wrap gap-1.5">{c.stalls.length ? c.stalls.map((s: any) => <StallChip key={s.reason} label={s.label} level={s.level} />) : <Tag tone="done">No stalls</Tag>}</div>
                  {c.next_step && <p className="text-[14px]"><span className="text-muted">Next step:</span> {c.next_step.text}</p>}
                  <div className="flex flex-wrap gap-2 pt-1">
                    <Button size="sm" variant="primary" onClick={() => { setPersona(c.owner.id); nav(`/app/cases/${c.id}`); }}>Open case</Button>
                    <Button size="sm" onClick={() => { setPersona(c.owner.id); nav("/app/work"); }}>See it in {shortName(c.owner.name)}'s My work</Button>
                  </div>
                </Card>
              )}
            </>
          )}
        </div>
      </div>

      <Card className="p-4">
        <h2 className="text-[22px] font-semibold leading-7">HL7 v2 from the lab</h2>
        <p className="mt-1 text-[14px] text-ink-2">A lab result message (ORU^R01) posted to the connector. A positive FIT opens a case with a named owner.</p>
        <textarea aria-label="HL7 message" rows={4} value={hl7} onChange={(e) => setHl7(e.target.value)} className={cx(inputCls, "mono mt-3 text-[12px] leading-5")} spellCheck={false} />
        <div className="mt-3 flex flex-wrap gap-2">
          <Button variant="primary" size="sm" onClick={() => sendHl7(hl7)}>Send</Button>
          <Button size="sm" onClick={() => sendHl7("not an hl7 message")}>Send a broken message</Button>
        </div>
        {ack && <div className="reveal mt-3"><Ack text={ack} /></div>}
      </Card>
    </div>
  );
}

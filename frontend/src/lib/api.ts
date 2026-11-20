/* eslint-disable @typescript-eslint/no-explicit-any */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { bundle, demoRequest, demoNow } from "./demo";
import { ApiError, type Assist, type Case, type CaseRow, type Me, type PatientCase, type PrepCheck, type Service, type Work } from "./types";
import { usePersona } from "./persona";

const env = import.meta.env;
export const MODE: "live" | "demo" = env.VITE_API_BASE_URL && env.VITE_DEMO_MODE !== "true" ? "live" : "demo";

const BASES: Record<Service, string | undefined> = {
  core: env.VITE_API_BASE_URL,
  agent: env.VITE_AGENT_URL,
  notifier: env.VITE_NOTIFIER_URL,
  connector: env.VITE_CONNECTOR_URL,
};

export function now(): Date { return MODE === "demo" ? demoNow() : new Date(); }

export async function request<T = any>(service: Service, method: string, path: string, body: any, persona: string): Promise<T> {
  if (MODE === "demo") {
    // A short, honest delay so loading states are real and toasts don't flash.
    await new Promise((r) => setTimeout(r, method === "GET" ? 60 : 180));
    const r = demoRequest(service, method, path, body, persona);
    if (r.status >= 400) throw new ApiError(r.status, r.data?.error?.code ?? "ERROR", r.data?.error?.message ?? "Request failed", r.data?.error?.details);
    return r.data as T;
  }
  const base = BASES[service];
  if (!base) throw new ApiError(0, "NO_BASE_URL", `No base URL configured for the ${service} service.`);
  const headers: Record<string, string> = { "X-Demo-User": persona };
  let payload: BodyInit | undefined;
  if (service === "connector") { headers["Content-Type"] = "text/plain"; payload = String(body ?? ""); }
  else if (body !== undefined) { headers["Content-Type"] = "application/json"; payload = JSON.stringify(body); }
  if (service === "notifier" && env.VITE_NOTIFIER_OPS_KEY) headers["X-Ops-Key"] = env.VITE_NOTIFIER_OPS_KEY;
  let res: Response;
  try { res = await fetch(base + path, { method, headers, body: payload }); }
  catch { throw new ApiError(0, "NETWORK", `Could not reach the ${service} service.`); }
  const text = await res.text();
  let data: any = text;
  try { data = JSON.parse(text); } catch { /* plain text, e.g. HL7 ACK */ }
  if (!res.ok) throw new ApiError(res.status, data?.error?.code ?? `HTTP_${res.status}`, data?.error?.message ?? res.statusText, data?.error?.details);
  return data as T;
}

function useGet<T>(service: Service, path: string | null, opts: { enabled?: boolean } = {}) {
  const { persona } = usePersona();
  return useQuery<T, ApiError>({
    queryKey: [service, path, persona],
    queryFn: () => request<T>(service, "GET", path!, undefined, persona!),
    enabled: !!persona && !!path && opts.enabled !== false,
    retry: false,
  });
}

type People = { staff: { id: string; name: string; role: string }[]; patients: { id: string; name: string; role: string }[] };
let LIVE_PEOPLE: People | null = null;
/** Everyone in the directory, for name lookups. Demo: the bundle. Live: the last /v1/directory/people answer. */
export const knownPeople = (): People | null => (MODE === "demo" ? bundle()?.directory ?? null : LIVE_PEOPLE);

/** The role picker needs the directory before anyone is signed in, so it does not go through useGet. */
export function usePeople() {
  return useQuery<People, ApiError>({
    queryKey: ["people", MODE],
    staleTime: Infinity,
    retry: false,
    queryFn: async () => {
      if (MODE === "demo") return bundle()?.directory ?? { staff: [], patients: [] };
      let res: Response;
      try { res = await fetch(`${BASES.core}/v1/directory/people`); }
      catch { throw new ApiError(0, "NETWORK", "Could not reach the case service."); }
      if (!res.ok) throw new ApiError(res.status, `HTTP_${res.status}`, res.statusText);
      LIVE_PEOPLE = (await res.json()) as People;
      return LIVE_PEOPLE;
    },
  });
}

const LIVE_CASE_IDS: Record<string, string> = {};
/** A patient's open case id. Demo: from the bundle. Live: from the case list as that persona sees it. */
export async function caseIdForPatient(patientId: string, persona: string): Promise<string | null> {
  if (MODE === "demo") {
    const b = bundle();
    for (const [id, c] of Object.entries<{ detail_by_persona: Record<string, { patient: { id: string } }> }>(b?.cases ?? {})) {
      if (Object.values(c.detail_by_persona).some((d) => d.patient.id === patientId)) return id;
    }
    return null;
  }
  if (LIVE_CASE_IDS[patientId]) return LIVE_CASE_IDS[patientId];
  const r = await request<{ items: CaseRow[] }>("core", "GET", "/v1/cases", undefined, persona);
  for (const c of r.items) LIVE_CASE_IDS[c.patient.id] ??= c.id;
  return LIVE_CASE_IDS[patientId] ?? null;
}

export const useMe = () => useGet<Me>("core", "/v1/me");
export const useDirectory = () => useGet<{ staff: any[]; patients: any[] }>("core", "/v1/directory/people");
export const useWork = () => useGet<Work>("core", "/v1/me/work");
export const useCases = (params: Record<string, string>) => {
  const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v)).toString();
  return useGet<{ items: CaseRow[] }>("core", `/v1/cases${qs ? "?" + qs : ""}`);
};
export const useCase = (id: string) => useGet<Case>("core", `/v1/cases/${id}`);
export const useAudit = (id: string) => useGet<any>("core", `/v1/cases/${id}/audit`);
export const useReferralOptions = (id: string) => useGet<any>("core", `/v1/cases/${id}/referral-options`);
export const useAssist = (id: string) => useGet<Assist>("agent", `/v1/cases/${id}/assist`);
export const useTrail = (id: string) => useGet<any>("notifier", `/v1/notifications?case_id=${id}`);
export const useChannels = () => useGet<any>("notifier", "/v1/policy");
export const useMetrics = (filter: string) => useGet<any>("core", `/v1/program/metrics${filter ? "?" + filter : ""}`);
const thisMonth = () => { const d = now(); return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, "0")}`; };
export const useUsage = () => useGet<any>("core", `/v1/program/usage?month=${thisMonth()}`);
export const useAiOversight = () => useGet<any>("core", "/v1/program/ai-oversight");
export const useUnmatched = () => useGet<any>("core", MODE === "live" ? "/v1/integration/unmatched" : null);
export const useScenarios = () => useGet<{ items: { id: string; title: string; why: string }[] }>("core", "/v1/demo/scenarios");
export const usePatientCases = (lang: string) => useGet<{ items: PatientCase[] }>("core", `/v1/me/cases?lang=${lang}`);
export const usePrepCheck = (caseId: string | null, lang: "en" | "ar" = "en") => useGet<PrepCheck>("core", caseId ? `/v1/me/cases/${caseId}/prep-check?lang=${lang}` : null);

/** One mutation hook for every command. Invalidates everything afterwards so all screens agree. */
export function useCommand<T = any>(service: Service = "core") {
  const { persona } = usePersona();
  const qc = useQueryClient();
  return useMutation<T, ApiError, { path: string; body?: any; method?: string }>({
    mutationFn: ({ path, body, method = "POST" }) => request<T>(service, method, path, body, persona!),
    onSettled: () => qc.invalidateQueries(),
  });
}

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

const KEY = "tasleem.persona";
const TOUR_KEY = "tasleem.tour";

function read(key: string): string | null { try { return localStorage.getItem(key); } catch { return null; } }
function write(key: string, v: string | null) { try { if (v === null) localStorage.removeItem(key); else localStorage.setItem(key, v); } catch { /* private mode */ } }

export interface TourState { open: boolean; step: number }

interface Ctx {
  persona: string | null;
  setPersona: (p: string | null) => void;
  tour: TourState;
  setTour: (t: TourState) => void;
}
const PersonaCtx = createContext<Ctx | null>(null);

export function PersonaProvider({ children }: { children: ReactNode }) {
  const [persona, setP] = useState<string | null>(() => read(KEY));
  const [tour, setT] = useState<TourState>(() => {
    try { return JSON.parse(read(TOUR_KEY) ?? "") as TourState; } catch { return { open: false, step: 0 }; }
  });
  const setPersona = useCallback((p: string | null) => { write(KEY, p); setP(p); }, []);
  const setTour = useCallback((t: TourState) => { write(TOUR_KEY, JSON.stringify(t)); setT(t); }, []);
  useEffect(() => { document.documentElement.dataset.persona = persona ?? ""; }, [persona]);
  const value = useMemo(() => ({ persona, setPersona, tour, setTour }), [persona, setPersona, tour, setTour]);
  return <PersonaCtx.Provider value={value}>{children}</PersonaCtx.Provider>;
}

export function usePersona() {
  const c = useContext(PersonaCtx);
  if (!c) throw new Error("PersonaProvider missing");
  return c;
}

export const isPatient = (id: string | null) => !!id && id.startsWith("p-");

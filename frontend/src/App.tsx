import { Component, lazy, Suspense, useEffect, useState, type ReactNode } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { MODE } from "./lib/api";
import { loadBundle } from "./lib/demo";
import { isPatient, usePersona } from "./lib/persona";
import { Button, Skeleton } from "./components/ui";
import Landing from "./pages/Landing";
import DemoPicker from "./pages/DemoPicker";
const AppShell = lazy(() => import("./components/AppShell"));
const MyWork = lazy(() => import("./pages/MyWork"));
const AllCases = lazy(() => import("./pages/AllCases"));
const CaseView = lazy(() => import("./pages/CaseView"));
const Programme = lazy(() => import("./pages/Programme"));
const Simulator = lazy(() => import("./pages/Simulator"));
const Patient = lazy(() => import("./pages/Patient"));

/** A crash shows a message and a way back, never a blank page. */
class ErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state = { error: null as Error | null };
  static getDerivedStateFromError(error: Error) { return { error }; }
  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div role="alert" className="mx-auto mt-24 max-w-md rounded border border-rule bg-sheet p-6">
        <p className="font-semibold">Something broke on this screen.</p>
        <p className="mt-1 text-ink-2">{this.state.error.message}</p>
        <div className="mt-4 flex gap-2"><Button onClick={() => location.reload()}>Reload</Button><Button variant="quiet" onClick={() => { location.href = "/demo"; }}>Back to the demo start</Button></div>
      </div>
    );
  }
}

/** Loads the synthetic demo bundle once (demo mode only). */
export function BundleGate({ children }: { children: ReactNode }) {
  const [state, setState] = useState<"loading" | "ready" | "error">(MODE === "demo" ? "loading" : "ready");
  const [err, setErr] = useState("");
  useEffect(() => {
    if (MODE !== "demo") return;
    loadBundle().then(() => setState("ready")).catch((e: Error) => { setErr(e.message); setState("error"); });
  }, []);
  if (state === "ready") return <>{children}</>;
  if (state === "error") return (
    <div className="mx-auto mt-24 max-w-md rounded border border-rule bg-sheet p-6" role="alert">
      <p className="font-semibold">Could not load the synthetic demo.</p>
      <p className="mt-1 text-ink-2">{err}</p>
      <Button className="mt-4" onClick={() => location.reload()}>Retry</Button>
    </div>
  );
  return (
    <div className="mx-auto mt-24 max-w-md space-y-3 px-4" aria-busy="true">
      <p className="text-ink-2">Loading the synthetic demo…</p>
      <Skeleton className="h-6 w-2/3" /><Skeleton className="h-24" /><Skeleton className="h-24" />
    </div>
  );
}

function RequireStaff({ children }: { children: ReactNode }) {
  const { persona } = usePersona();
  // A switch to a patient while inside the care-team app (the tour's last step) lands on the patient screen.
  if (!persona) return <Navigate to="/demo" replace />;
  if (isPatient(persona)) return <Navigate to="/patient" replace />;
  return <>{children}</>;
}
function RequirePatient({ children }: { children: ReactNode }) {
  const { persona } = usePersona();
  if (!persona) return <Navigate to="/demo" replace />;
  if (!isPatient(persona)) return <Navigate to="/app/work" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <ErrorBoundary>
    <Suspense fallback={<div className="mx-auto mt-24 max-w-md space-y-3 px-4" aria-busy="true"><Skeleton className="h-6 w-2/3" /><Skeleton className="h-24" /></div>}>
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/demo" element={<BundleGate><DemoPicker /></BundleGate>} />
      <Route path="/app" element={<BundleGate><RequireStaff><AppShell /></RequireStaff></BundleGate>}>
        <Route index element={<Navigate to="work" replace />} />
        <Route path="work" element={<MyWork />} />
        <Route path="cases" element={<AllCases />} />
        <Route path="cases/:id" element={<CaseView />} />
        <Route path="programme" element={<Programme />} />
        <Route path="simulator" element={<Simulator />} />
      </Route>
      <Route path="/patient" element={<BundleGate><RequirePatient><Patient /></RequirePatient></BundleGate>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
    </Suspense>
    </ErrorBoundary>
  );
}

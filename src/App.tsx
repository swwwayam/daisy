import { useEffect, useState } from "react";
import Landing from "./experience/Experience";
import Workspace from "./workspace/Workspace";
import AuthScreen from "./auth/AuthScreen";
import CustomCursor from "./components/CustomCursor";
import { authClient } from "./services/auth";
import { useMutation } from "convex/react";
import { api } from "../convex/_generated/api";

export default function App() {
  const [view, setView] = useState<"landing" | "auth" | "workspace">(() => window.location.hash === "#login" ? "auth" : ["#workspace", "#visualization-studio", "#pipeline-stage"].includes(window.location.hash) ? "workspace" : "landing");
  const { data: session, isPending: sessionPending } = authClient.useSession();
  const sessionReady = !sessionPending;
  const [slowSession, setSlowSession] = useState(false);
  const [browsePublic, setBrowsePublic] = useState(false);
  const ensurePersonalWorkspace = useMutation(api.accounts.ensurePersonalWorkspace);

  useEffect(() => {
    if (!session?.user) return;
    if (!window.location.hash || window.location.hash === "#login") {
      window.history.replaceState(null, "", "#workspace");
      setView("workspace");
    }
    void ensurePersonalWorkspace().catch(() => undefined);
  }, [ensurePersonalWorkspace, session?.user?.id]);

  useEffect(() => {
    const navigate = () => setView(window.location.hash === "#login" ? "auth" : ["#workspace", "#visualization-studio", "#pipeline-stage"].includes(window.location.hash) ? "workspace" : "landing");
    window.addEventListener("hashchange", navigate);
    return () => window.removeEventListener("hashchange", navigate);
  }, []);

  useEffect(() => {
    if (sessionReady && !session && view === "workspace") {
      window.history.replaceState(null, "", "#login");
      setView("auth");
    }
  }, [sessionReady, session, view]);

  useEffect(() => {
    if (!sessionPending) { setSlowSession(false); return; }
    const timer = window.setTimeout(() => setSlowSession(true), 12000);
    return () => window.clearTimeout(timer);
  }, [sessionPending]);

  function show(next: "landing" | "auth" | "workspace") {
    window.location.hash = next === "auth" ? "login" : next === "workspace" ? "workspace" : "hero";
    setView(next);
    window.scrollTo({ top: 0, behavior: "instant" });
  }

  function start() {
    show(session ? "workspace" : "auth");
  }

  async function signOut() {
    const result = await authClient.signOut();
    if (result.error) throw new Error(result.error.message || "Sign out failed. Try again.");
    show("landing");
  }

  return <>
    <CustomCursor />
    {!sessionReady && !browsePublic && (slowSession ? <div className="app-recovery"><h1>Sign-in is taking longer than expected</h1><p>You can retry the connection or explore DAISY while authentication recovers.</p><button className="pill pill-solid" onClick={() => window.location.reload()}>Retry connection</button><button className="pill pill-ghost" onClick={() => { setBrowsePublic(true); setView("landing"); }}>Explore DAISY</button></div> : <div className="app-session-loading" role="status"><span className="cosmic-mark" /><span>Connecting your workspace…</span></div>)}
    {!sessionReady && browsePublic && <Landing onStart={() => { setBrowsePublic(false); show("auth"); }} />}
    {sessionReady && view === "workspace" && session
      ? <div className="ws-enter"><Workspace onExit={() => show("landing")} onSignOut={signOut} /></div>
      : sessionReady && view === "auth"
        ? <AuthScreen onBack={() => show("landing")} />
        : sessionReady && <Landing onStart={start} />}
  </>;
}

import { useEffect, useState } from "react";
import type { Session } from "@supabase/supabase-js";
import Landing from "./experience/Experience";
import Workspace from "./workspace/Workspace";
import AuthScreen from "./auth/AuthScreen";
import CustomCursor from "./components/CustomCursor";
import { supabase } from "./services/supabase";

export default function App() {
  const [view, setView] = useState<"landing" | "auth" | "workspace">("landing");
  const [session, setSession] = useState<Session | null>(null);
  const [sessionReady, setSessionReady] = useState(false);

  useEffect(() => {
    let mounted = true;
    supabase.auth.getSession().then(({ data }) => {
      if (!mounted) return;
      setSession(data.session);
      setSessionReady(true);
    });
    const { data: listener } = supabase.auth.onAuthStateChange((event, nextSession) => {
      setSession(nextSession);
      setSessionReady(true);
      if (event === "SIGNED_IN") setView("workspace");
      if (event === "SIGNED_OUT") setView("landing");
    });
    return () => {
      mounted = false;
      listener.subscription.unsubscribe();
    };
  }, []);

  function show(next: "landing" | "auth" | "workspace") {
    setView(next);
    window.scrollTo({ top: 0, behavior: "instant" });
  }

  function start() {
    show(session ? "workspace" : "auth");
  }

  async function signOut() {
    await supabase.auth.signOut();
  }

  return <>
    <CustomCursor />
    {!sessionReady && <div className="app-session-loading"><span className="cosmic-mark" /><span>Connecting your workspace</span></div>}
    {sessionReady && view === "workspace" && session
      ? <div className="ws-enter"><Workspace onExit={() => show("landing")} onSignOut={signOut} /></div>
      : sessionReady && view === "auth"
        ? <AuthScreen onBack={() => show("landing")} />
        : sessionReady && <Landing onStart={start} />}
  </>;
}

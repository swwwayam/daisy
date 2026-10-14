import { useEffect, useState } from "react";
import Landing from "./experience/Experience";
import Workspace from "./workspace/Workspace";
import AuthScreen from "./auth/AuthScreen";
import CustomCursor from "./components/CustomCursor";
import { authClient } from "./services/auth";
import { useMutation } from "convex/react";
import { api } from "../convex/_generated/api";

export default function App() {
  const [view, setView] = useState<"landing" | "auth" | "workspace">("landing");
  const { data: session, isPending: sessionPending } = authClient.useSession();
  const sessionReady = !sessionPending;
  const ensurePersonalWorkspace = useMutation(api.accounts.ensurePersonalWorkspace);

  useEffect(() => {
    if (!session?.user) return;
    setView("workspace");
    void ensurePersonalWorkspace().catch(() => undefined);
  }, [ensurePersonalWorkspace, session?.user]);

  function show(next: "landing" | "auth" | "workspace") {
    setView(next);
    window.scrollTo({ top: 0, behavior: "instant" });
  }

  function start() {
    show(session ? "workspace" : "auth");
  }

  async function signOut() {
    await authClient.signOut();
    show("landing");
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

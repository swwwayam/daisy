import { useState } from "react";
import Landing from "./experience/Experience";
import Workspace from "./workspace/Workspace";

export default function App() {
  const [view, setView] = useState<"landing" | "workspace">("landing");
  function show(next: "landing" | "workspace") {
    setView(next);
    window.scrollTo({ top: 0, behavior: "instant" });
  }
  return view === "workspace"
    ? <div className="ws-enter"><Workspace onExit={() => show("landing")} /></div>
    : <Landing onStart={() => show("workspace")} />;
}

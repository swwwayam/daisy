import { Component, type ErrorInfo, type ReactNode } from "react";

export default class AppBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  componentDidCatch(_error: Error, info: ErrorInfo) { console.error("DAISY interface error", info.componentStack); }
  render() {
    if (this.state.failed) return <main className="app-recovery"><h1>The interface needs to reload</h1><p>Your saved work stays in your account. Reload DAISY to reconnect to your workspace.</p><button className="pill pill-solid" onClick={() => window.location.reload()}>Reload DAISY</button></main>;
    return this.props.children;
  }
}

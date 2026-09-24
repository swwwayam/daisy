import { useEffect, useRef, useState, type FormEvent } from "react";
import { ArrowLeft, ArrowRight, Eye, EyeSlash, GoogleLogo } from "@phosphor-icons/react";
import ParticleScene, { type ScenePose } from "../experience/ParticleScene";
import { supabase } from "../services/supabase";

type Mode = "signin" | "signup";

export default function AuthScreen({ onBack }: { onBack: () => void }) {
  const [mode, setMode] = useState<Mode>("signin");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const pose = useRef<ScenePose>({ morph: 0, spread: 0, x: 2.15, y: 0, scale: 1.28, rotation: -.3, opacity: .92 });

  useEffect(() => {
    const mobile = window.matchMedia("(max-width: 820px)").matches;
    Object.assign(pose.current, mobile
      ? { x: 0, y: 1.75, scale: .8, opacity: .5 }
      : { x: 2.15, y: 0, scale: 1.28, opacity: .92 });
  }, []);

  function changeMode(next: Mode) {
    setMode(next);
    setError("");
    setNotice("");
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      if (mode === "signup") {
        const { data, error: authError } = await supabase.auth.signUp({
          email,
          password,
          options: {
            data: { display_name: name.trim() },
            emailRedirectTo: window.location.origin,
          },
        });
        if (authError) throw authError;
        if (!data.session) setNotice("Check your inbox to confirm your account, then return here to sign in.");
      } else {
        const { error: authError } = await supabase.auth.signInWithPassword({ email, password });
        if (authError) throw authError;
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Authentication failed. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  async function continueWithGoogle() {
    setBusy(true);
    setError("");
    const { error: authError } = await supabase.auth.signInWithOAuth({
      provider: "google",
      options: { redirectTo: window.location.origin },
    });
    if (authError) {
      setError(authError.message);
      setBusy(false);
    }
  }

  return <div className="auth-shell">
    <ParticleScene pose={pose} paused={false} />
    <header className="auth-nav">
      <button className="cosmic-brand auth-brand" onClick={onBack} aria-label="Back to DAISY home">
        <span className="cosmic-mark" aria-hidden="true" />D.A.I.S.Y
      </button>
      <button className="auth-back" onClick={onBack}><ArrowLeft size={16} /> Back to the experience</button>
    </header>

    <main className="auth-main">
      <section className="auth-copy" aria-hidden="true">
        <p className="auth-kicker">Your models. Your workspace.</p>
        <h1>Continue the<br /><span>discovery.</span></h1>
        <p>Return to your datasets, experiments and trained models from one private workspace.</p>
      </section>

      <section className="auth-panel" aria-labelledby="auth-title">
        <div className="auth-switch" role="tablist" aria-label="Authentication mode">
          <button role="tab" aria-selected={mode === "signin"} onClick={() => changeMode("signin")}>Sign in</button>
          <button role="tab" aria-selected={mode === "signup"} onClick={() => changeMode("signup")}>Create account</button>
        </div>

        <div className="auth-heading">
          <p>{mode === "signin" ? "Welcome back" : "Begin a new workspace"}</p>
          <h2 id="auth-title">{mode === "signin" ? "Pick up where you left off." : "Build with your own data."}</h2>
        </div>

        <button className="auth-google" type="button" onClick={continueWithGoogle} disabled={busy}>
          <GoogleLogo size={20} weight="bold" /> Continue with Google
        </button>
        <div className="auth-divider"><span>or use email</span></div>

        <form className="auth-form" onSubmit={submit}>
          {mode === "signup" && <label>
            <span>Name</span>
            <input autoComplete="name" value={name} onChange={(event) => setName(event.target.value)} required placeholder="How should DAISY address you?" />
          </label>}
          <label>
            <span>Email</span>
            <input type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} required placeholder="you@example.com" />
          </label>
          <label>
            <span>Password</span>
            <span className="password-field">
              <input type={showPassword ? "text" : "password"} autoComplete={mode === "signup" ? "new-password" : "current-password"} value={password} onChange={(event) => setPassword(event.target.value)} required minLength={8} placeholder="At least 8 characters" />
              <button type="button" onClick={() => setShowPassword((value) => !value)} aria-label={showPassword ? "Hide password" : "Show password"}>
                {showPassword ? <EyeSlash size={18} /> : <Eye size={18} />}
              </button>
            </span>
          </label>

          {error && <p className="auth-message error" role="alert">{error}</p>}
          {notice && <p className="auth-message success" role="status">{notice}</p>}

          <button className="auth-submit" disabled={busy}>
            <span>{busy ? "Connecting" : mode === "signin" ? "Enter workspace" : "Create workspace"}</span>
            <ArrowRight size={18} />
          </button>
        </form>
        <p className="auth-terms">By continuing, you agree to keep access to uploaded data within your authorised workspace.</p>
      </section>
    </main>
  </div>;
}

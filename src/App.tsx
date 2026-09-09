import { useEffect, useRef, useState } from "react";
import Workspace from "./workspace/Workspace";

/* ─── scroll reveal ─── */
function useReveal() {
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => entries.forEach((e) => { if (e.isIntersecting) e.target.classList.add("in"); }),
      { threshold: 0.15 }
    );
    document.querySelectorAll(".reveal, .reveal-3d").forEach((el) => observer.observe(el));
    return () => observer.disconnect();
  }, []);
}

/* ─── animate bars/donuts on mount ─── */
function useAnimateHero() {
  useEffect(() => {
    const t = setTimeout(() => {
      document.querySelectorAll<HTMLElement>(".fc-bar-fill").forEach((el) => {
        el.style.width = el.dataset.w || "0%";
      });
      document.querySelectorAll<SVGCircleElement>("circle.progress").forEach((el) => {
        el.style.strokeDashoffset = el.dataset.offset || "0";
      });
    }, 250);
    return () => clearTimeout(t);
  }, []);
}

/* ─── NAV ─── */
function Nav({ go, onStart }: { go: (id: string) => void; onStart: () => void }) {
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const h = () => setScrolled(window.scrollY > 24);
    window.addEventListener("scroll", h);
    return () => window.removeEventListener("scroll", h);
  }, []);
  return (
    <nav className={scrolled ? "scrolled" : ""}>
      <div className="nav-inner">
        <button className="logo" onClick={() => go("hero")}>
          <span className="logo-mark" />D.A.I.S.Y
        </button>
        <div className="nav-right">
          <div className="nav-links">
            <button onClick={() => go("statement")}>Platform</button>
            <button onClick={() => go("workflow")}>Pipelines</button>
            <button onClick={() => go("showcase")}>Agents</button>
          </div>
          <button className="nav-cta" onClick={onStart}>Get demo</button>
        </div>
      </div>
    </nav>
  );
}

/* ─── hero sparks ─── */
function Sparks() {
  const sparks = Array.from({ length: 14 }, (_, i) => ({
    left: `${8 + (i * 6.3) % 84}%`,
    top: `${30 + (i * 13) % 55}%`,
    dur: `${4 + (i % 5)}s`,
    delay: `${(i % 7) * 0.7}s`,
  }));
  return (
    <>
      {sparks.map((s, i) => (
        <span key={i} className="spark" style={{ left: s.left, top: s.top, animationDuration: s.dur, animationDelay: s.delay }} />
      ))}
    </>
  );
}

/* ─── floating card with cursor parallax ─── */
function FloatCard({ className, children }: { className: string; children: React.ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  function move(e: React.MouseEvent) {
    const el = ref.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    const px = (e.clientX - r.left) / r.width - 0.5;
    const py = (e.clientY - r.top) / r.height - 0.5;
    el.style.transform = `perspective(700px) rotateY(${px * 12}deg) rotateX(${-py * 12}deg) translateY(-6px)`;
  }
  function leave() {
    if (ref.current) ref.current.style.transform = "";
  }
  return (
    <div ref={ref} className={`float-card ${className}`} onMouseMove={move} onMouseLeave={leave}>
      {children}
    </div>
  );
}

/* ─── HERO ─── */
function Hero({ go, onStart }: { go: (id: string) => void; onStart: () => void }) {
  return (
    <section id="hero" className="hero">
      <Sparks />

      <FloatCard className="fc-1">
        <div className="fc-k"><span>Dataset health</span><span>●</span></div>
        <div className="fc-v gold">98.2%</div>
        <div className="fc-bar"><div className="fc-bar-fill" data-w="98%" /></div>
        <div className="fc-note">4,894 rows · 0 nulls remaining</div>
      </FloatCard>

      <FloatCard className="fc-2">
        <div className="fc-k"><span>Model accuracy</span><span>↑</span></div>
        <div className="fc-donut">
          <svg width="88" height="88" viewBox="0 0 88 88">
            <circle cx="44" cy="44" r="37" fill="none" stroke="rgba(255,255,255,0.10)" strokeWidth="9" />
            <circle className="progress" cx="44" cy="44" r="37" fill="none" stroke="#E8A857" strokeWidth="9"
              strokeDasharray="232.5" data-offset="21" strokeLinecap="round" transform="rotate(-90 44 44)" />
          </svg>
          <div className="center-label"><div className="big">91%</div><div className="small">accuracy</div></div>
        </div>
        <div className="fc-note">XGBoost · beat baseline by 12pts</div>
      </FloatCard>

      <FloatCard className="fc-3">
        <div className="fc-k"><span>Active agent</span><span className="mono">03</span></div>
        <div className="fc-v" style={{ fontSize: 16 }}>Feature engineering</div>
        <div className="fc-bar"><div className="fc-bar-fill" data-w="41%" /></div>
        <div className="fc-note">Encoding 6 categoricals</div>
      </FloatCard>

      <FloatCard className="fc-4">
        <div className="fc-k"><span>Time to train</span><span>~</span></div>
        <div className="fc-v gold">2m 14s</div>
        <div className="fc-note">vs. 3hrs by hand</div>
      </FloatCard>

      <div className="badge-ring badge-1">
        <div className="big">69%</div>
        <div className="small">automated</div>
      </div>

      <div className="hero-inner">
        <div className="eyebrow"><span className="dot" />Now training on autopilot</div>
        <h1 className="hero-title">
          Build <span className="accent">models</span>,<br />
          <span className="fade">not pipelines.</span>
        </h1>
        <p className="hero-sub">
          Describe your problem, drop in a dataset, and DAISY cleans, engineers, trains, and evaluates the full ML pipeline for you — no notebooks required.
        </p>
        <div className="hero-cta-row">
          <button className="btn-primary" onClick={onStart}>Start a run →</button>
          <button className="btn-ghost" onClick={() => go("showcase")}>Watch it think</button>
        </div>
        <button className="scroll-cue" onClick={() => go("statement")}>SCROLL<span className="line" /></button>
      </div>
    </section>
  );
}

/* ─── STATEMENT ─── */
function Statement() {
  return (
    <section id="statement" className="statement reveal">
      <div className="tag">Why DAISY</div>
      <h2>
        Every model starts the same way — <span className="muted">a messy dataset and a vague idea.</span> DAISY turns that into a <span className="gold">trained, evaluated pipeline</span> before you'd finish setting up your notebook.
      </h2>
    </section>
  );
}

/* ─── SHOWCASE ─── */
function Showcase() {
  function tilt(e: React.MouseEvent) {
    const el = e.currentTarget as HTMLElement;
    const r = el.getBoundingClientRect();
    const rx = ((e.clientY - r.top) / r.height - 0.5) * -12;
    const ry = ((e.clientX - r.left) / r.width - 0.5) * 12;
    el.style.transform = `rotateX(${rx}deg) rotateY(${ry}deg)`;
  }
  function reset(e: React.MouseEvent) {
    (e.currentTarget as HTMLElement).style.transform = "";
  }
  return (
    <section id="showcase" className="showcase">
      <div className="showcase-frame reveal-3d">
        <div className="showcase-visual" onMouseMove={tilt} onMouseLeave={reset}>
          <div className="ring" />
          <div className="ring r2" />
          <div className="orb" />
          <div className="glass-glare" />
        </div>
      </div>
      <div className="showcase-text reveal">
        <h3>One conversation replaces the whole pipeline.</h3>
        <p>
          Tell DAISY what you're trying to predict. It profiles your data, picks a cleaning strategy, engineers features, tries several models, and hands you the one that actually works — with the reasoning behind every step.
        </p>
        <div className="stat-row">
          <div><div className="stat-num">12+</div><div className="stat-label">Agents orchestrated</div></div>
          <div><div className="stat-num">40x</div><div className="stat-label">Faster than manual</div></div>
          <div><div className="stat-num">0</div><div className="stat-label">Lines of code needed</div></div>
        </div>
      </div>
    </section>
  );
}

/* ─── WORKFLOW ─── */
const WF = [
  { icon: "◆", title: "Clean and understand", desc: "DAISY profiles your dataset, flags anomalies, and repairs nulls, duplicates, and skew automatically." },
  { icon: "▦", title: "Engineer features", desc: "Encoding, scaling, interaction terms, and correlation pruning — reasoned about, not just applied." },
  { icon: "◈", title: "Train and evaluate", desc: "Multiple models trained in parallel, benchmarked, and explained in plain language." },
];
function Workflow() {
  function track(e: React.MouseEvent) {
    const el = e.currentTarget as HTMLElement;
    const r = el.getBoundingClientRect();
    const mx = e.clientX - r.left;
    const my = e.clientY - r.top;
    el.style.setProperty("--mx", `${mx}px`);
    el.style.setProperty("--my", `${my}px`);
    const rx = (my / r.height - 0.5) * -10;
    const ry = (mx / r.width - 0.5) * 12;
    el.style.transform = `rotateX(${rx}deg) rotateY(${ry}deg) translateZ(14px)`;
  }
  function reset(e: React.MouseEvent) {
    (e.currentTarget as HTMLElement).style.transform = "";
  }
  return (
    <section id="workflow" className="workflow">
      <div className="workflow-head reveal">
        <div className="tag">The pipeline</div>
        <h2>One intelligent layer for every stage of the model lifecycle.</h2>
      </div>
      <div className="workflow-grid">
        {WF.map((w, i) => (
          <div key={w.title} className="wf-frame reveal-3d" style={{ transitionDelay: `${i * 0.12}s` }}>
            <div className="wf-card" onMouseMove={track} onMouseLeave={reset}>
              <div className="wf-inner">
                <div className="wf-icon">{w.icon}</div>
                <div>
                  <h4>{w.title}</h4>
                  <p>{w.desc}</p>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

/* ─── ASK BAR (landing) — hands off into the live workspace where the real chat lives ─── */
function AskBar({ onStart }: { onStart: () => void }) {
  const [query, setQuery] = useState("");
  return (
    <section id="ask" className="ask-section reveal">
      <div className="ask-bar">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && onStart()}
          placeholder="Ask DAISY to build something..."
        />
        <button onClick={onStart}>Ask agent →</button>
      </div>
    </section>
  );
}

/* ─── WORDMARK + FOOTER ─── */
function Footer({ go }: { go: (id: string) => void }) {
  return (
    <>
      <div className="wordmark-wrap">
        <div className="wordmark">D A I S Y</div>
      </div>
      <footer>
        <span>© 2026 D.A.I.S.Y — no-code ML orchestration</span>
        <div style={{ display: "flex", gap: 24 }}>
          <button onClick={() => go("hero")}>Top</button>
          <button onClick={() => go("workflow")}>Pipeline</button>
          <button onClick={() => go("ask")}>Demo</button>
        </div>
        <span>Made for builders</span>
      </footer>
    </>
  );
}

/* ─── landing ─── */
function Landing({ onStart }: { onStart: () => void }) {
  useReveal();
  useAnimateHero();
  function go(id: string) {
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth" });
  }
  return (
    <>
      <Nav go={go} onStart={onStart} />
      <Hero go={go} onStart={onStart} />
      <Statement />
      <Showcase />
      <Workflow />
      <AskBar onStart={onStart} />
      <Footer go={go} />
    </>
  );
}

/* ─── APP ─── */
export default function App() {
  const [view, setView] = useState<"landing" | "workspace">("landing");
  const [entering, setEntering] = useState(false);

  function start() {
    setEntering(true);
    window.setTimeout(() => {
      setView("workspace");
      setEntering(false);
      window.scrollTo(0, 0);
    }, 620);
  }
  function exit() {
    setView("landing");
    window.scrollTo(0, 0);
  }

  if (view === "workspace") {
    return (
      <div className="ws-enter">
        <Workspace onExit={exit} />
      </div>
    );
  }
  return (
    <div className={entering ? "landing-exit" : ""}>
      <Landing onStart={start} />
    </div>
  );
}

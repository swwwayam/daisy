import { useEffect, useRef, useState } from "react";
import { ArrowDown, ArrowRight, ArrowUpRight, Check, Database, List, X } from "@phosphor-icons/react";

const stages = [
  { name: "Clean your data", short: "Data cleaning", title: "A better starting point.", copy: "Find missing values, duplicates, and inconsistent formats. DAISY proposes a cleaning plan and records every transformation.", details: ["Missing-value treatment", "Duplicate detection", "An action-by-action record"] },
  { name: "Understand the patterns", short: "Exploration", title: "Make the patterns visible.", copy: "Explore distributions, correlations, and data quality with computed statistics and explanations grounded in your dataset.", details: ["Statistical summaries", "Feature relationships", "Plain-language interpretation"] },
  { name: "Shape your features", short: "Feature engineering", title: "Give your model the right inputs.", copy: "Choose your target, then prepare the remaining columns with categorical encoding, scaling, and date features.", details: ["Target-aware transformations", "Categorical encoding", "Numeric scaling"] },
  { name: "Find the right models", short: "Model selection", title: "A considered shortlist.", copy: "DAISY identifies classification or regression and recommends compatible candidates from its supported model library.", details: ["Problem-type detection", "Supported model guardrails", "Reasoned recommendations"] },
  { name: "Train and compare", short: "Model training", title: "Let the results decide.", copy: "Train real machine-learning models and compare their measured performance. Weighted F1 or RMSE determines the winner.", details: ["Real scikit-learn training", "Consistent train/test split", "Measured model comparison"] },
  { name: "Evaluate the outcome", short: "Evaluation", title: "Know how your model performs.", copy: "Inspect train and test metrics, classification confusion matrices, or regression residuals. Get a clear interpretation of the results.", details: ["Train/test diagnostics", "Task-specific metrics", "Grounded explanations"] },
];

function Brand() {
  return <><span className="logo-mark" aria-hidden="true" />D.A.I.S.Y</>;
}

export default function Landing({ onStart }: { onStart: () => void }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [selectedStage, setSelectedStage] = useState(0);
  const root = useRef<HTMLDivElement>(null);
  const current = stages[selectedStage];

  useEffect(() => {
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) { entry.target.classList.add("is-visible"); observer.unobserve(entry.target); }
      });
    }, { threshold: 0.12 });
    root.current?.querySelectorAll("[data-reveal]").forEach((node) => observer.observe(node));
    return () => observer.disconnect();
  }, []);

  function navigate() { setMenuOpen(false); }

  return (
    <div className="landing" ref={root}>
      <a href="#main" className="skip-link">Skip to content</a>
      <header className="site-header">
        <a className="logo" href="#hero" aria-label="DAISY home" onClick={navigate}><Brand /></a>
        <nav className={menuOpen ? "site-links is-open" : "site-links"} id="site-navigation" aria-label="Main navigation">
          <a href="#statement" onClick={navigate}>Platform</a>
          <a href="#workflow" onClick={navigate}>Pipelines</a>
          <a href="#showcase" onClick={navigate}>Agents</a>
        </nav>
        <div className="header-actions">
          <button className="cta cta-small" onClick={onStart}>Start a run <ArrowUpRight size={17} aria-hidden="true" /></button>
          <button className="menu-toggle" aria-label={menuOpen ? "Close navigation" : "Open navigation"} aria-expanded={menuOpen} aria-controls="site-navigation" onClick={() => setMenuOpen(!menuOpen)}>{menuOpen ? <X size={23} /> : <List size={23} />}</button>
        </div>
      </header>

      <main id="main">
        <section id="hero" className="hero-section">
          <div className="hero-art" aria-hidden="true"><img src="/images/daisy-data-orb.png" alt="" width="1536" height="1024" fetchPriority="high" /></div>
          <div className="hero-content">
            <p className="eyebrow">Your data. A new perspective.</p>
            <h1>Intelligence,<br /><span>from your data.</span></h1>
            <p className="hero-description">Turn a dataset into a trained, evaluated model.<br className="desktop-break" /> A guided ML workflow, with reasoning at every step.</p>
            <div className="hero-actions">
              <button className="cta" onClick={onStart}>Start a run <ArrowUpRight size={19} aria-hidden="true" /></button>
              <a className="text-link" href="#workflow">Explore the pipeline <ArrowDown size={17} aria-hidden="true" /></a>
            </div>
          </div>
        </section>

        <section id="statement" className="platform-section section-shell" data-reveal>
          <div className="platform-copy"><h2>Less setup.<br /><span>More discovery.</span></h2><p>Move from raw data to measured results in one workspace. DAISY brings the pieces together so you can focus on what you want to predict.</p></div>
          <div className="platform-facts">
            <div><span className="fact-number">06</span><h3>Connected stages</h3><p>From cleaning to evaluation.</p></div>
            <div><span className="fact-number">10</span><h3>Supported models</h3><p>Classification and regression.</p></div>
          </div>
        </section>

        <section id="workflow" className="workflow-section section-shell" data-reveal>
          <p className="eyebrow">From possibility to prediction</p>
          <h2>One pipeline.<br /><span>Every step, understood.</span></h2>
          <div className="pipeline-explorer">
            <div className="pipeline-tabs" role="tablist" aria-label="Explore pipeline stages" aria-orientation="vertical">
              {stages.map((stage, index) => <button key={stage.short} id={`pipeline-tab-${index}`} role="tab" aria-selected={selectedStage === index} aria-controls="pipeline-detail" tabIndex={selectedStage === index ? 0 : -1} className={selectedStage === index ? "pipeline-tab selected" : "pipeline-tab"} onClick={() => setSelectedStage(index)} onKeyDown={(event) => {
                const next = event.key === "ArrowDown" || event.key === "ArrowRight" ? (index + 1) % stages.length : event.key === "ArrowUp" || event.key === "ArrowLeft" ? (index + stages.length - 1) % stages.length : event.key === "Home" ? 0 : event.key === "End" ? stages.length - 1 : null;
                if (next !== null) { event.preventDefault(); setSelectedStage(next); document.getElementById(`pipeline-tab-${next}`)?.focus(); }
              }}><span className="tab-number">{String(index + 1).padStart(2, "0")}</span><span>{stage.name}</span><ArrowUpRight size={19} aria-hidden="true" /></button>)}
            </div>
            <div id="pipeline-detail" className="pipeline-detail" role="tabpanel" aria-labelledby={`pipeline-tab-${selectedStage}`} tabIndex={0}>
              <div className="pipeline-detail-top"><span>{current.short}</span><Database size={24} weight="light" aria-hidden="true" /></div>
              <div key={selectedStage} className="pipeline-detail-content"><h3>{current.title}</h3><p>{current.copy}</p><ul>{current.details.map((detail) => <li key={detail}><Check size={16} aria-hidden="true" />{detail}</li>)}</ul></div>
              <button className="text-link" onClick={onStart}>Start a run <ArrowRight size={18} aria-hidden="true" /></button>
            </div>
          </div>
        </section>

        <section id="showcase" className="agents-section section-shell" data-reveal>
          <div className="agent-visual" aria-hidden="true"><img src="/images/daisy-data-orb.png" alt="" width="1536" height="1024" loading="lazy" /><div className="agent-orbit" /></div>
          <div className="agents-copy"><h2>Intelligence you<br />can follow.</h2><p>AI proposes the plan. Python does the work. You see the actions, the results, and the reasoning behind them.</p><div className="agent-principles"><div><h3>Sense</h3><p>Start with facts from your dataset.</p></div><div><h3>Reason</h3><p>Build a structured, supported plan.</p></div><div><h3>Act</h3><p>Execute it and record the outcome.</p></div></div><a href="#ask" className="text-link">Get to know DAISY <ArrowDown size={17} aria-hidden="true" /></a></div>
        </section>

        <section id="ask" className="questions-section section-shell" data-reveal>
          <h2>A little more clarity.</h2>
          <div className="questions">
            <details><summary>What can I build with DAISY?<span aria-hidden="true">+</span></summary><p>Build classification models for outcomes such as customer churn, or regression models for values such as house prices. Upload a CSV and choose the column you want to predict.</p></details>
            <details><summary>Do I need to write code?<span aria-hidden="true">+</span></summary><p>No. The workspace guides you through uploading, cleaning, exploring, feature engineering, training, and evaluation. You choose the target and control when each stage runs.</p></details>
            <details><summary>How does DAISY explain its decisions?<span aria-hidden="true">+</span></summary><p>Each stage exposes its available actions and results. Ask DAISY questions in the workspace to get explanations grounded in the dataset profile and completed pipeline stages.</p></details>
            <details><summary>What can I download today?<span aria-hidden="true">+</span></summary><p>You can download the processed dataset as a CSV. Downloadable trained model packages are planned; they are not available in this version yet.</p></details>
          </div>
        </section>

        <section className="closing-section section-shell" data-reveal><h2>Your next discovery<br /><span>starts with a dataset.</span></h2><button className="cta" onClick={onStart}>Start a run <ArrowUpRight size={20} aria-hidden="true" /></button></section>
      </main>
      <footer className="site-footer"><div className="footer-top"><a className="logo" href="#hero" aria-label="DAISY home"><Brand /></a><p>Data Analysis & Intelligent System for You</p><a className="text-link" href="#hero">Back to top <ArrowUpRight size={16} aria-hidden="true" /></a></div><div className="footer-wordmark" aria-hidden="true">D.A.I.S.Y</div><div className="footer-bottom"><span>© {new Date().getFullYear()} D.A.I.S.Y</span><span>Built for curious minds.</span></div></footer>
    </div>
  );
}

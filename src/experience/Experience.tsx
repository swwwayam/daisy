import { useLayoutEffect, useEffect, useRef, useState } from "react";
import { ArrowDown, ArrowUpRight, List, Pause, Play, X } from "@phosphor-icons/react";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import ParticleScene, { type ScenePose } from "./ParticleScene";

gsap.registerPlugin(ScrollTrigger);

const chapters = [
  { title: <>Find the signal.<br /><em>Clear the noise.</em></>, label: "Clean & understand", body: "Every dataset has a story. DAISY finds missing values, cleans inconsistencies, and reveals the patterns worth exploring.", tags: ["Data cleaning", "Exploratory analysis"], number: "01" },
  { title: <>Shape the data.<br /><em>Train the possibility.</em></>, label: "Engineer & train", body: "Choose what you want to predict. DAISY prepares your features, recommends models, and measures how each one performs.", tags: ["Feature engineering", "Model selection", "Model training"], number: "02" },
  { title: <>See the outcome.<br /><em>Understand the why.</em></>, label: "Evaluate & explain", body: "Compare real metrics. Inspect the result. Ask questions grounded in what the pipeline actually did, all in one workspace.", tags: ["Model evaluation", "Grounded chat"], number: "03" },
];

export default function Experience({ onStart }: { onStart: () => void }) {
  const root = useRef<HTMLDivElement>(null);
  const journey = useRef<HTMLElement>(null);
  const [menu, setMenu] = useState(false);
  const [paused, setPaused] = useState(false);
  const [reduced, setReduced] = useState(() => window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  const [chapter, setChapter] = useState(0);
  const pose = useRef<ScenePose>({ morph: 0, spread: 0, x: 2.25, y: 0, scale: 1.2, rotation: -.35, opacity: 1 });
  const motionOff = paused || reduced;

  useEffect(() => {
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReduced(query.matches);
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);

  useEffect(() => {
    if (!menu) return;
    const close = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setMenu(false);
        root.current?.querySelector<HTMLButtonElement>(".cosmic-menu")?.focus();
      }
    };
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [menu]);

  useLayoutEffect(() => {
    const scope = root.current;
    if (!scope) return;
    const media = gsap.matchMedia();
    const ctx = gsap.context(() => {
      media.add({ desktop: "(min-width: 900px)", mobile: "(max-width: 899px)" }, (context) => {
        const desktop = !!context.conditions?.desktop;
        Object.assign(pose.current, { morph: 0, spread: 0, x: desktop ? 2.2 : 0, y: 0, scale: desktop ? 1.2 : 1.05, rotation: -.35, opacity: 1 });
        if (motionOff) {
          gsap.set(".reveal-line, .reveal-copy, .story-panel, .closing-word", { clearProps: "all" });
          return;
        }
        gsap.from(".hero-line > span", { yPercent: 110, rotateX: -35, duration: 1.25, stagger: .1, ease: "power3.out" });
        gsap.from(".hero-intro, .hero-cta", { opacity: 0, y: 18, duration: 1, stagger: .12, delay: .45 });

        if (desktop) {
          gsap.fromTo(".manifesto-word", { opacity: .16 }, { opacity: 1, stagger: .15, ease: "none", scrollTrigger: { trigger: "#statement", start: "top 65%", end: "bottom 70%", scrub: .6 } });
          const panels = gsap.utils.toArray<HTMLElement>(".story-panel");
          gsap.set(panels.slice(1), { autoAlpha: 0, y: 60, rotateX: -12 });
          const timeline = gsap.timeline({ scrollTrigger: {
            trigger: journey.current, start: "top top", end: () => `+=${window.innerHeight * 2.6}`,
            pin: true, scrub: 1, invalidateOnRefresh: true,
            onUpdate: (self) => { const next = self.progress < .34 ? 0 : self.progress < .67 ? 1 : 2; setChapter(previous => previous === next ? previous : next); },
          } });
          timeline.to({}, { duration: 1.4 });
          timeline.to(panels[0], { autoAlpha: 0, y: -70, rotateX: 12, duration: .4 }, 1.4);
          timeline.to(panels[1], { autoAlpha: 1, y: 0, rotateX: 0, duration: .5 }, 1.7);
          timeline.to({}, { duration: .6 });
          timeline.to(panels[1], { autoAlpha: 0, y: -70, rotateX: 12, duration: .4 }, 2.85);
          timeline.to(panels[2], { autoAlpha: 1, y: 0, rotateX: 0, duration: .5 }, 3.1);
          timeline.to({}, { duration: .65 }, 3.85);
          // A single controller owns the scene, including reverse scroll and refresh.
          const initial: ScenePose = { morph: 0, spread: 0, x: 2.2, y: 0, scale: 1.2, rotation: -.35, opacity: 1 };
          const center: ScenePose = { ...initial, x: 0, scale: 1, rotation: 0, spread: 1, opacity: .65 };
          const sphere: ScenePose = { ...initial, x: -2.35, scale: 1.1, rotation: .25, morph: 1 };
          const helix: ScenePose = { ...sphere, morph: 2, rotation: 1.1, scale: 1.05 };
          const ring: ScenePose = { ...sphere, morph: 3, rotation: .6, scale: 1.2 };
          const blend = (a: ScenePose, b: ScenePose, progress: number) => {
            const t = gsap.utils.clamp(0, 1, progress);
            for (const key of Object.keys(a) as (keyof ScenePose)[]) pose.current[key] = a[key] + (b[key] - a[key]) * t;
          };
          const updateScene = () => {
            const y = window.scrollY;
            const height = window.innerHeight;
            const start = timeline.scrollTrigger?.start ?? height * 1.95;
            const end = timeline.scrollTrigger?.end ?? start + height * 2.6;
            const progress = (y - start) / Math.max(1, end - start);
            if (y < start) blend(initial, center, (y - height * .12) / (height * .68));
            else if (progress < .31) blend(center, sphere, progress / .18);
            else if (progress < .63) blend(sphere, helix, (progress - .31) / .2);
            else blend(helix, ring, (progress - .63) / .22);
            if (y > end) blend(ring, { ...ring, opacity: 0, spread: .75 }, (y - end) / (height * .65));
          };
          ScrollTrigger.create({ start: 0, end: "max", onUpdate: updateScene, onRefresh: updateScene });
          updateScene();
        } else {
          gsap.to(pose.current, { opacity: 0, rotation: .6, ease: "none", scrollTrigger: { trigger: "#hero", start: "bottom 85%", end: "bottom 20%", scrub: .5 } });
          gsap.utils.toArray<HTMLElement>(".story-panel").forEach((panel) => gsap.from(panel, { opacity: 0, y: 45, duration: .8, scrollTrigger: { trigger: panel, start: "top 86%", once: true } }));
        }
        gsap.utils.toArray<HTMLElement>(".reveal-copy").forEach((element) => gsap.from(element, { opacity: 0, y: 48, duration: 1, ease: "power2.out", scrollTrigger: { trigger: element, start: "top 87%", once: true } }));
        gsap.from(".closing-word", { yPercent: 100, rotateX: -55, stagger: .12, duration: 1.2, ease: "power3.out", scrollTrigger: { trigger: ".closing", start: "top 75%", once: true } });
      });
    }, scope);
    let alive = true;
    document.fonts.ready.then(() => { if (alive) ScrollTrigger.refresh(); });
    return () => { alive = false; media.revert(); ctx.revert(); };
  }, [motionOff]);

  function navigate() { setMenu(false); }

  return <div className={`constellation ${motionOff ? "motion-off" : "motion-on"}`} ref={root}>
    <ParticleScene pose={pose} paused={motionOff} />
    <a className="skip-link" href="#main">Skip to content</a>
    <header className="cosmic-header">
      <a className="cosmic-brand" href="#hero" aria-label="DAISY home"><span className="cosmic-mark" aria-hidden="true" />D.A.I.S.Y</a>
      <nav id="cosmic-navigation" className={menu ? "cosmic-nav open" : "cosmic-nav"} aria-label="Main navigation">
        <a href="#statement" onClick={navigate}>Platform</a><a href="#workflow" onClick={navigate}>Pipelines</a><a href="#showcase" onClick={navigate}>Agents</a>
      </nav>
      <div className="cosmic-header-actions"><button className="cosmic-header-cta" onClick={onStart}>Start a run <ArrowUpRight size={16} /></button><button className="cosmic-menu" onClick={() => setMenu(!menu)} aria-label={menu ? "Close navigation" : "Open navigation"} aria-expanded={menu} aria-controls="cosmic-navigation">{menu ? <X size={24} /> : <List size={24} />}</button></div>
    </header>
    <main id="main">
      <section id="hero" className="cosmic-hero">
        <div className="hero-type"><h1><span className="hero-line"><span>Your data.</span></span><span className="hero-line"><span>New dimensions.</span></span></h1><div className="hero-intro"><p className="cosmic-kicker">A little curiosity. A lot of possibility.</p><p>Turn raw data into real understanding.<br />Meet your intelligent machine-learning companion.</p></div><div className="hero-cta"><button className="cosmic-button" onClick={onStart}>Start a run <ArrowUpRight size={18} /></button><a href="#workflow" className="cosmic-text-link">Explore DAISY <ArrowDown size={16} /></a></div></div>
      </section>

      <section id="statement" className="manifesto cosmic-section">
        <h2>{"Somewhere in your data, there’s a discovery waiting to happen.".split(" ").map((word, index) => <span className="manifesto-word" key={index}>{word} </span>)}</h2><p className="reveal-copy">DAISY connects the steps between a question and a trained model.<br />Less time setting up. More room to explore.</p>
      </section>

      <section id="workflow" ref={journey} className="journey">
        <div className="journey-stage">
          <div className="journey-title"><span>The journey from data to discovery</span><span className="journey-count" aria-hidden="true">{chapters[chapter].number} / 03</span></div>
          <div className="story-copy">{chapters.map((item) => <article className="story-panel" key={item.number}><p className="cosmic-kicker">{item.label}</p><h2>{item.title}</h2><p className="story-description">{item.body}</p><div className="story-tags">{item.tags.map(tag => <span key={tag}>{tag}</span>)}</div></article>)}</div>
          <div className="journey-progress" aria-hidden="true">{chapters.map((item, i) => <span className={i === chapter ? "active" : ""} key={item.number}>{item.label}</span>)}</div>
        </div>
      </section>

      <section id="showcase" className="cosmic-section intelligence">
        <div className="reveal-copy"><p className="cosmic-kicker">Intelligence with a paper trail</p><h2>Watch it think.<br /><span>Know what it did.</span></h2></div>
        <div className="intelligence-body reveal-copy"><p>AI reasons about your data. Python carries out the plan. Every transformation and measured result stays visible in your workspace.</p><div className="agent-steps"><div><span>Sense</span><p>Compute the facts.</p></div><div><span>Reason</span><p>Choose supported actions.</p></div><div><span>Act</span><p>Execute. Measure. Explain.</p></div></div><button className="cosmic-text-link" onClick={onStart}>Start a run <ArrowUpRight size={18} /></button></div>
      </section>

      <section className="cosmic-section capabilities reveal-copy" aria-label="DAISY capabilities"><div><strong>06</strong><p>Connected pipeline stages</p></div><div><strong>10</strong><p>Supported ML models</p></div><div><strong>02</strong><p>Classification & regression</p></div></section>

      <section id="ask" className="cosmic-section cosmic-faq"><h2 className="reveal-copy">Good questions.<br />Clear answers.</h2><div className="cosmic-questions reveal-copy">
        <details><summary>What can I build with DAISY?<span>+</span></summary><p>Build classification models for outcomes such as customer churn, or regression models for values such as house prices. Upload a CSV and select the column to predict.</p></details>
        <details><summary>Do I need to write code?<span>+</span></summary><p>No. The workspace guides you from upload to evaluation. You choose the target and control when each stage runs.</p></details>
        <details><summary>Can I see how decisions are made?<span>+</span></summary><p>Yes. Inspect each stage’s actions and measured results, then ask DAISY questions grounded in the completed pipeline.</p></details>
        <details><summary>What can I download?<span>+</span></summary><p>Download your processed dataset as a CSV. After training, download the winning model as a ZIP with saved preprocessing, its input schema, and a Python script for predictions on new data.</p></details>
      </div></section>

      <section className="closing cosmic-section"><h2><span><span className="closing-word">A new perspective.</span></span><span><span className="closing-word">Already in your data.</span></span></h2><button className="cosmic-button" onClick={onStart}>Start a run <ArrowUpRight size={18} /></button></section>
    </main>
    <footer className="cosmic-footer"><a href="#hero" className="cosmic-brand" aria-label="DAISY home"><span className="cosmic-mark" aria-hidden="true" />D.A.I.S.Y</a><span>Data Analysis & Intelligent System for You</span><a href="#hero" className="cosmic-text-link">Back to top <ArrowUpRight size={16} /></a></footer>
    <button className="motion-toggle" aria-pressed={motionOff} onClick={() => setPaused(!paused)} disabled={reduced} aria-label={reduced ? "Reduced motion enabled" : paused ? "Resume motion" : "Pause motion"}>{motionOff ? <Play size={13} weight="fill" /> : <Pause size={13} weight="fill" />}<span>{reduced ? "Reduced motion" : paused ? "Resume motion" : "Pause motion"}</span></button>
  </div>;
}

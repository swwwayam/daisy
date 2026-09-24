import { useEffect, useRef } from "react";

export default function CustomCursor() {
  const root = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const cursor = root.current;
    const finePointer = window.matchMedia("(hover: hover) and (pointer: fine)");
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
    if (!cursor || !finePointer.matches || reducedMotion.matches) return;

    document.documentElement.classList.add("daisy-cursor-enabled");
    let frame = 0;
    let targetX = window.innerWidth / 2;
    let targetY = window.innerHeight / 2;
    let ringX = targetX;
    let ringY = targetY;

    const render = () => {
      ringX += (targetX - ringX) * .18;
      ringY += (targetY - ringY) * .18;
      cursor.style.setProperty("--cursor-x", `${targetX}px`);
      cursor.style.setProperty("--cursor-y", `${targetY}px`);
      cursor.style.setProperty("--ring-x", `${ringX}px`);
      cursor.style.setProperty("--ring-y", `${ringY}px`);
      frame = requestAnimationFrame(render);
    };
    const move = (event: PointerEvent) => {
      targetX = event.clientX;
      targetY = event.clientY;
      cursor.dataset.visible = "true";
      const interactive = (event.target as Element | null)?.closest("a, button, input, summary, label, [role='button']");
      cursor.dataset.active = interactive ? "true" : "false";
    };
    const leave = () => { cursor.dataset.visible = "false"; };
    window.addEventListener("pointermove", move, { passive: true });
    document.documentElement.addEventListener("mouseleave", leave);
    frame = requestAnimationFrame(render);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("pointermove", move);
      document.documentElement.removeEventListener("mouseleave", leave);
      document.documentElement.classList.remove("daisy-cursor-enabled");
    };
  }, []);

  return <div className="daisy-cursor" ref={root} aria-hidden="true">
    <span className="cursor-core" />
    <span className="cursor-ring"><i /><i /><i /></span>
  </div>;
}

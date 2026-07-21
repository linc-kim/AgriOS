/**
 * Greena — Line Waves background.
 *
 * A field of horizontal lines that ripple as travelling sine waves, tinted with
 * the Greena palette. Built natively rather than pulled from a component
 * library so it uses our exact brand colours and respects our motion rules.
 *
 * Canvas, not SVG or DOM: ~40 lines × ~90 points is thousands of segments per
 * frame, which as DOM nodes would thrash layout. One canvas draws it in a
 * single pass.
 *
 * Accessibility: honours prefers-reduced-motion by rendering one static frame —
 * the composition still reads, nothing moves. It is decorative, so it is hidden
 * from assistive tech.
 */
import { useEffect, useRef } from "react";

interface LineWavesProps {
  /** Line count. Fewer reads calmer; more reads denser. */
  lines?: number;
  /** Peak amplitude in px at the most-displaced line. */
  amplitude?: number;
  /** Travelling-wave speed multiplier. */
  speed?: number;
  className?: string;
}

export function LineWaves({
  lines = 38,
  amplitude = 26,
  speed = 1,
  className = "",
}: LineWavesProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const frameRef = useRef<number | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let width = 0;
    let height = 0;
    // Cap DPR at 2: beyond that the pixel cost doubles again for no visible gain.
    const dpr = Math.min(window.devicePixelRatio || 1, 2);

    const resize = () => {
      const parent = canvas.parentElement;
      if (!parent) return;
      width = parent.clientWidth;
      height = parent.clientHeight;
      canvas.width = width * dpr;
      canvas.height = height * dpr;
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };

    const draw = (time: number) => {
      ctx.clearRect(0, 0, width, height);
      const t = time * 0.0004 * speed;
      const spacing = height / (lines - 1);
      const step = Math.max(6, width / 90);

      for (let i = 0; i < lines; i++) {
        const y = i * spacing;
        // Lines nearest the vertical centre swing widest, so the field reads as
        // one wave rather than a stack of unrelated ripples.
        const centreBias = 1 - Math.abs(i / (lines - 1) - 0.5) * 2;
        const amp = amplitude * (0.25 + centreBias * 0.75);

        ctx.beginPath();
        for (let x = 0; x <= width + step; x += step) {
          const phase = x * 0.006 + i * 0.18;
          const offset =
            Math.sin(phase + t * 2) * amp +
            Math.sin(phase * 0.5 - t * 1.3) * amp * 0.4;
          const py = y + offset;
          if (x === 0) ctx.moveTo(x, py);
          else ctx.lineTo(x, py);
        }

        // Fade toward the edges so the field dissolves instead of ending in a
        // hard band against the section boundary.
        const edgeFade = Math.sin((i / (lines - 1)) * Math.PI);
        const alpha = 0.05 + edgeFade * 0.22;
        // Brand green shifting toward navy across the field.
        const mix = i / (lines - 1);
        const r = Math.round(7 + mix * -1);
        const g = Math.round(101 - mix * 49);
        const b = Math.round(36 + mix * 109);
        ctx.strokeStyle = `rgba(${r}, ${g}, ${b}, ${alpha})`;
        ctx.lineWidth = 1;
        ctx.stroke();
      }
    };

    const loop = (time: number) => {
      draw(time);
      frameRef.current = requestAnimationFrame(loop);
    };

    resize();
    if (reduced) {
      draw(0); // one static frame
    } else {
      frameRef.current = requestAnimationFrame(loop);
    }

    const observer = new ResizeObserver(() => {
      resize();
      if (reduced) draw(0);
    });
    if (canvas.parentElement) observer.observe(canvas.parentElement);

    return () => {
      if (frameRef.current !== null) cancelAnimationFrame(frameRef.current);
      observer.disconnect();
    };
  }, [lines, amplitude, speed]);

  return (
    <canvas
      ref={canvasRef}
      aria-hidden="true"
      className={`pointer-events-none absolute inset-0 h-full w-full ${className}`}
    />
  );
}

/**
 * Soft radial wash sitting behind content. Pairs with LineWaves to lift text
 * off the line field without needing an opaque panel.
 */
export function GlowField({ className = "" }: { className?: string }) {
  return (
    <div aria-hidden="true" className={`pointer-events-none absolute inset-0 overflow-hidden ${className}`}>
      <div className="absolute -top-32 left-1/2 h-[36rem] w-[36rem] -translate-x-1/2 rounded-full bg-brand-400/20 blur-[120px] dark:bg-brand-500/10" />
      <div className="absolute -bottom-40 -right-24 h-[30rem] w-[30rem] rounded-full bg-navy-400/15 blur-[120px] dark:bg-navy-500/10" />
    </div>
  );
}

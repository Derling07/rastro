import type { ReactNode } from "react";
import Link from "next/link";

const STEPS = [
  { n: "01", title: "Pick a module", text: "Camera trap, traffic, crowd, or a camera on the next page." },
  { n: "02", title: "Watch the video", text: "The clip sits in the dark frame, like a camera viewfinder." },
  { n: "03", title: "Read the count and the alerts", text: "The engine number stays fixed. You confirm or dismiss." },
] as const;

export function NotebookShell({
  current,
  children,
}: {
  current: "analyze" | "cameras";
  children: ReactNode;
}) {
  return (
    <div className="mx-auto max-w-6xl px-4 py-6 sm:px-8 sm:py-8">
      <header className="mb-6">
        <p className="font-facts text-[11px] uppercase tracking-[0.18em] text-pack">Field notebook</p>
        <div className="mt-1 flex flex-wrap items-end justify-between gap-3">
          <h1 className="font-note text-5xl font-semibold leading-none tracking-tight text-[var(--ink)]">Rastro</h1>
          <nav className="flex gap-4 text-sm" aria-label="Pages">
            <Link
              href="/"
              className="underline decoration-from-font"
              aria-current={current === "analyze" ? "page" : undefined}
            >
              Analyze a clip
            </Link>
            <Link
              href="/cameras"
              className="underline decoration-from-font"
              aria-current={current === "cameras" ? "page" : undefined}
            >
              Cameras
            </Link>
          </nav>
        </div>
        <p className="mt-3 max-w-2xl text-base leading-relaxed">
          Rastro connects a count to a decision. SAM 3.1 marks what is in the frame. Muse Spark writes
          one field note. A person confirms it before anything leaves the notebook.
        </p>
        <ol className="guide mt-5" aria-label="How to use Rastro">
          {STEPS.map((step) => (
            <li key={step.n}>
              <p className="num">{step.n}</p>
              <p className="mt-1 font-note text-xl leading-tight">{step.title}</p>
              <p className="mt-1 text-sm text-muted">{step.text}</p>
            </li>
          ))}
        </ol>
      </header>
      {children}
    </div>
  );
}

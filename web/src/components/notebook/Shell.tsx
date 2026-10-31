import type { ReactNode } from "react";
import Link from "next/link";

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
      </header>
      {children}
    </div>
  );
}

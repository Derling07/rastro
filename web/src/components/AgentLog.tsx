"use client";

import { useState } from "react";
import type { AgentStep } from "@/lib/result";

type Props = { steps: AgentStep[] };

export function AgentLog({ steps }: Props) {
  const [open, setOpen] = useState(false);
  if (!steps.length) {
    return <p className="text-sm text-muted">No agent log.</p>;
  }
  return (
    <div>
      <button
        type="button"
        className="flex w-full items-center justify-between rounded border border-line bg-panel px-3 py-2 text-sm"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <span className="font-bold text-muted">
          Agent log · {steps.length} steps
        </span>
        <span aria-hidden>{open ? "▾" : "▸"}</span>
      </button>
      {open && (
        <ol className="mt-2 space-y-1.5 border-l-2 border-line pl-3">
          {steps.map((s, i) => (
            <li key={i} className="text-sm">
              <span className="font-display text-pack">{s.step}</span>
              {s.tool && (
                <code className="ml-2 text-[11px] text-muted">{s.tool}</code>
              )}
              {s.ok === false && (
                <span className="ml-2 text-xs text-alta">failed</span>
              )}
              {s.detail && (
                <p className="text-xs text-muted">{s.detail}</p>
              )}
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

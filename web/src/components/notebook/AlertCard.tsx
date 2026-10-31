"use client";

import { useEffect, useRef, useState } from "react";

export type FieldNote = {
  id: string;
  module: string;
  title: string;
  paid_call: boolean;
  recorded: boolean;
  source: string;
  model?: string | null;
  sam_saw: string;
  crop?: {
    class?: string;
    bbox: number[];
    width: number;
    height: number;
    t_s?: number;
    pixels?: boolean;
    blurred?: boolean;
  } | null;
  engine_count: string;
  context: { example_data: boolean; label: string; lines: string[] };
  summary: string;
  summary_label: string;
  why: { sam: string; rule: string };
  severity: string;
  not_sure: boolean;
  camera_id?: string;
  status: string;
  actions: string[];
};

function Crop({ crop }: { crop: NonNullable<FieldNote["crop"]> }) {
  const [x1, y1, x2, y2] = crop.bbox;
  const blurred = crop.blurred || crop.class === "person";
  const boxW = Math.max(8, x2 - x1);
  const boxH = Math.max(8, y2 - y1);
  const pad = Math.max(boxW, boxH) * 0.45;
  const vx = Math.max(0, x1 - pad);
  const vy = Math.max(0, y1 - pad);
  const vw = Math.max(boxW + pad * 2, 32);
  const vh = Math.max(boxH + pad * 2, 32);
  return (
    <svg
      viewBox={`${vx} ${vy} ${vw} ${vh}`}
      className="mt-2 aspect-video w-full bg-[var(--viewfinder)]"
      role="img"
      aria-label={blurred ? "Blurred detection box" : `Detection box for ${crop.class || "object"}`}
    >
      <rect x={vx} y={vy} width={vw} height={vh} fill="#121816" />
      {blurred && (
        <defs>
          <filter id="soft-box">
            <feGaussianBlur stdDeviation={Math.max(2, boxW / 30)} />
          </filter>
        </defs>
      )}
      <rect
        x={x1}
        y={y1}
        width={boxW}
        height={boxH}
        fill={blurred ? "#c9c2b2" : "none"}
        fillOpacity={blurred ? 0.9 : 0}
        stroke="#e7d3a1"
        strokeWidth={Math.max(2, vw / 80)}
        filter={blurred ? "url(#soft-box)" : undefined}
      />
      <text x={vx + 4} y={vy + Math.max(14, vh / 10)} fill="#e7d3a1" fontSize={Math.max(12, vh / 10)} fontFamily="var(--font-facts)">
        {crop.class || "object"}
      </text>
    </svg>
  );
}

export function AlertCard({
  note,
  onAction,
}: {
  note: FieldNote;
  onAction?: (action: "confirm" | "dismiss" | "review") => void;
}) {
  const confirm = note.actions.includes("confirm");
  const dismiss = note.actions.includes("dismiss");
  const review = note.actions.includes("review");
  const statusRef = useRef<HTMLParagraphElement>(null);
  const [pending, setPending] = useState(false);
  const decided = useRef(false);

  useEffect(() => {
    if (!decided.current || pending) return;
    decided.current = false;
    statusRef.current?.focus();
  }, [note.status, pending]);

  async function act(action: "confirm" | "dismiss" | "review") {
    if (pending || !onAction) return;
    setPending(true);
    decided.current = true;
    try {
      await onAction(action);
    } finally {
      setPending(false);
    }
  }

  return (
    <article className="alert-card" data-module={note.module} aria-labelledby={`note-${note.id}`} aria-busy={pending}>
      <div className="alert-card-grid">
        <div>
          <p className="font-facts text-[11px] uppercase tracking-[0.14em] text-muted">What SAM saw</p>
          <p className="mt-1 text-sm">{note.sam_saw}</p>
          {note.crop ? <Crop crop={note.crop} /> : <p className="mt-2 text-sm text-muted">No detection box in this note.</p>}
          <p className="mt-3 font-facts text-[11px] uppercase tracking-[0.14em] text-muted">Engine count</p>
          <p className="font-facts text-lg leading-snug text-[var(--ink)]">{note.engine_count}</p>
          <p className="mt-1 text-xs text-muted">The summary cannot change this number.</p>
          <p className="mt-3 font-facts text-[11px] uppercase tracking-[0.14em] text-muted">Why · SAM</p>
          <p className="text-sm">{note.why.sam}</p>
          <p className="mt-2 font-facts text-[11px] uppercase tracking-[0.14em] text-muted">Why · rule</p>
          <p className="text-sm">{note.why.rule}</p>
        </div>
        <div>
          <h2 id={`note-${note.id}`} className="font-note text-2xl leading-tight">
            {note.title}
          </h2>
          <p className="mt-2 font-facts text-[11px] uppercase tracking-[0.14em] text-muted">
            Context · {note.context.example_data ? "Example data" : note.context.label}
          </p>
          <ul className="mt-1 list-disc space-y-1 pl-4 text-sm text-muted">
            {note.context.lines.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
          <h3 className="mt-4 font-note text-lg italic">{note.summary_label}</h3>
          <p className="line-clamp-3 font-note text-lg leading-snug">{note.summary}</p>
          <p className="mt-2 text-xs text-muted">
            {note.recorded
              ? `Recorded reply from ${note.model || "Muse Spark"}. This page did not call the model.`
              : "Local rules. Muse Spark was not called."}
          </p>
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <p className="stamp" data-unsure={note.not_sure ? "true" : "false"}>
              {note.severity}
            </p>
            <p ref={statusRef} tabIndex={-1} role="status" className="text-sm text-muted">
              Status: {note.status}
            </p>
          </div>
          <p className="mt-2 text-sm text-muted">Saved in this demo session only. No message sent.</p>
          {note.status === "open" && (
            <div className="flex flex-wrap gap-2">
              {confirm && (
                <button type="button" className="demo-primary" disabled={pending} aria-busy={pending} onClick={() => void act("confirm")}>
                  Confirm
                </button>
              )}
              {review && (
                <button type="button" className="demo-secondary" disabled={pending} aria-busy={pending} onClick={() => void act("review")}>
                  Review
                </button>
              )}
              {dismiss && (
                <button type="button" className="demo-secondary" disabled={pending} aria-busy={pending} onClick={() => void act("dismiss")}>
                  Dismiss
                </button>
              )}
            </div>
          )}
          {review && (
            <p className="mt-2 text-sm text-muted">
              Possible intrusion — needs review. Review means a person looked. Rastro does not notify authorities.
            </p>
          )}
        </div>
      </div>
    </article>
  );
}

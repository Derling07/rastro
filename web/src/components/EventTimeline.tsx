"use client";

import type { RastroEvent } from "@/lib/result";

type Props = {
  events: RastroEvent[];
  onSeek?: (t: number) => void;
  empty?: boolean;
  /**
   * Instantes t_s (segundos) donde el motor tocó el tope de objetos.
   * Opcional — marca en la lista.
   */
  maxObjectsHit?: number[];
};

function fmt(t: number): string {
  const m = Math.floor(t / 60);
  const s = Math.floor(t % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export function EventTimeline({
  events,
  onSeek,
  empty,
  maxObjectsHit,
}: Props) {
  const hits = (maxObjectsHit ?? [])
    .filter((t) => Number.isFinite(t))
    .slice()
    .sort((a, b) => a - b);

  if (empty || (!events.length && !hits.length)) {
    return <p className="text-sm text-muted">Sin eventos.</p>;
  }

  return (
    <div className="space-y-3">
      {hits.length > 0 && (
        <div>
          <p className="mb-1 text-[11px] font-bold uppercase tracking-wide text-muted">
            Tope de objetos
          </p>
          <ol className="flex flex-wrap gap-1.5">
            {hits.map((t, i) => (
              <li key={`hit-${i}-${t}`}>
                <button
                  type="button"
                  className="rounded-full border border-amber-500/50 bg-amber-500/10 px-2.5 py-0.5 text-xs text-amber-200 hover:border-amber-400"
                  onClick={() => onSeek?.(t)}
                  title="Conteo parcial en este instante"
                >
                  {fmt(t)}
                </button>
              </li>
            ))}
          </ol>
        </div>
      )}
      {events.length > 0 && (
        <ol className="space-y-1.5">
          {events.map((ev, i) => (
            <li key={i}>
              <button
                type="button"
                className="flex w-full items-baseline gap-2 rounded border border-line bg-panel px-3 py-1.5 text-left text-sm hover:border-pack"
                onClick={() => onSeek?.(ev.t_s)}
              >
                <span className="font-display text-pack">{fmt(ev.t_s)}</span>
                <span className="text-muted">{ev.kind ?? "evento"}</span>
                {ev.track_id && (
                  <span className="ml-auto text-xs text-muted">
                    {ev.track_id}
                  </span>
                )}
                {ev.class && <span className="text-xs">{ev.class}</span>}
              </button>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

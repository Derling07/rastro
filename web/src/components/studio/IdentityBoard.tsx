"use client";

import { colorForTrack } from "@/lib/result";

export type Sighting = {
  object_id: number | string | null;
  start_s: number;
  end_s: number;
  n: number;
};

export type Identity = {
  track_id: string;
  class: string;
  start_s: number;
  end_s: number;
  sightings: Sighting[];
  reidentified: boolean;
};

type Props = {
  identities: Identity[];
  naive: number;
  unique: number;
  noun: string;
  onSeek?: (t: number) => void;
};

export function IdentityBoard({ identities, naive, unique, noun, onSeek }: Props) {
  const merged = naive > unique;
  const span = Math.max(0.1, ...identities.map((row) => row.end_s), 1);

  const sentence =
    merged
      ? `${naive} sightings, ${unique} unique ${noun}`
      : `${unique} unique ${noun}. No repeat sighting was merged.`;

  return (
    <section className="rounded-lg border border-line bg-panel p-4" aria-label="Individuals">
      <p className="font-display text-3xl leading-tight text-[var(--text)] sm:text-4xl" aria-live="polite">
        {sentence}
      </p>
      <p className="mt-1 text-sm text-muted">
        {merged
          ? "Same individual, new tracker id. The bars that share a color were stitched."
          : "Each bar is one tracked individual."}
      </p>

      {merged && (
        <ul className="merge-source" aria-hidden>
          {identities.flatMap((row) =>
            row.sightings.map((sighting, index) => (
              <li
                key={`${row.track_id}-${index}`}
                className="merge-chip"
                style={{ borderColor: colorForTrack(row.track_id), color: colorForTrack(row.track_id) }}
              >
                {row.class} · id {String(sighting.object_id)}
              </li>
            )),
          )}
        </ul>
      )}

      <ol className="identity-lanes">
        {identities.map((row) => {
          const color = colorForTrack(row.track_id);
          return (
            <li key={row.track_id}>
              <button
                type="button"
                className="identity-label"
                onClick={() => onSeek?.(row.start_s)}
                title={`${row.track_id}. ${row.sightings.length} sighting${row.sightings.length === 1 ? "" : "s"}. Jump to first appearance.`}
              >
                <span className="identity-swatch" style={{ background: color }} />
                <span className="font-display text-lg">{row.track_id}</span>
                {row.reidentified && (
                  <span className="text-xs text-muted">
                    {row.sightings.length} sightings merged
                  </span>
                )}
              </button>
              <div className="identity-track" aria-hidden>
                {row.sightings.map((sighting, index) => {
                  const left = (sighting.start_s / span) * 100;
                  const width = Math.max(1.5, ((sighting.end_s - sighting.start_s) / span) * 100);
                  return (
                    <span
                      key={index}
                      className="identity-bar"
                      style={{
                        left: `${left}%`,
                        width: `${width}%`,
                        background: color,
                        animationDelay: `${index * 90}ms`,
                      }}
                      title={`Sighting ${index + 1}, tracker id ${String(sighting.object_id)}, ${sighting.start_s.toFixed(1)}s–${sighting.end_s.toFixed(1)}s`}
                    />
                  );
                })}
              </div>
            </li>
          );
        })}
      </ol>
    </section>
  );
}

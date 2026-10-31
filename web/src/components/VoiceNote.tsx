"use client";

import { clipLabel } from "@/lib/labels";
import type { ReportSection, VoiceNote as Voice } from "@/lib/result";

type Props = {
  voice: Voice | null;
  report: ReportSection;
};

/**
 * Nota de voz.
 * Schema v1.1: voice.is_public aún no existe → si falta, false (privada).
 * Solo con is_public === true se muestran los turnos literales;
 * si no, solo el resumen del report.
 */
export function VoiceNotePanel({ voice, report }: Props) {
  const isPublic = voice?.is_public === true;
  const turns = voice?.turns ?? [];
  const agentSummary =
    (typeof report.notas_campo === "string" && report.notas_campo) ||
    report.resumen ||
    "The agent processed the field note; the literal text is not public.";

  return (
    <section
      className="rounded-lg border border-line bg-panel p-3"
      aria-labelledby="voice-heading"
    >
      <h2 id="voice-heading" className="mb-2 text-sm font-bold text-muted">
        Voice note
      </h2>
      {isPublic && turns.length > 0 ? (
        <ul className="space-y-2">
          {turns.map((t, i) => (
            <li key={t.turn_id ?? i} className="text-sm">
              <span className="font-display font-semibold text-pack">
                {t.speaker}
              </span>
              <span className="ml-2 text-xs text-muted">
                {t.start_s.toFixed(1)}s–{t.end_s.toFixed(1)}s
              </span>
              <p className="leading-relaxed">{clipLabel(t.transcript)}</p>
            </li>
          ))}
        </ul>
      ) : (
        <div>
          <p className="mb-1 text-[11px] uppercase tracking-wide text-muted">
            {voice
              ? "Agent summary · private note"
              : "No voice note on this run"}
          </p>
          <p className="text-sm leading-relaxed">{clipLabel(agentSummary)}</p>
          {turns.length > 0 && (
            <p className="mt-2 text-xs text-muted">
              {turns.length} transcribed turn(s), hidden because the note is not public.
            </p>
          )}
        </div>
      )}
    </section>
  );
}

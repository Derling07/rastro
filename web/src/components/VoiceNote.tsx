"use client";

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
    "El agente procesó la nota de campo; el texto literal no es público.";

  return (
    <section
      className="rounded-lg border border-line bg-panel p-3"
      aria-labelledby="voice-heading"
    >
      <h2 id="voice-heading" className="mb-2 text-sm font-bold text-muted">
        Nota de voz
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
              <p className="leading-relaxed">{t.transcript}</p>
            </li>
          ))}
        </ul>
      ) : (
        <div>
          <p className="mb-1 text-[11px] uppercase tracking-wide text-muted">
            {voice
              ? "Resumen del agente · nota privada"
              : "Sin nota de voz en esta corrida"}
          </p>
          <p className="text-sm leading-relaxed">{agentSummary}</p>
          {turns.length > 0 && (
            <p className="mt-2 text-xs text-muted">
              {turns.length} turno(s) transcrito(s), ocultos por privacidad
              (is_public ≠ true).
            </p>
          )}
        </div>
      )}
    </section>
  );
}

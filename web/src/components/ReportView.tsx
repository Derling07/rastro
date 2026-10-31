"use client";

import { clipLabel } from "@/lib/labels";
import type { ReportSection } from "@/lib/result";

type Props = { report: ReportSection; empty?: boolean };

export function ReportView({ report, empty }: Props) {
  if (empty) {
    return (
      <p className="text-sm text-muted">No report yet.</p>
    );
  }
  return (
    <article
      className="rounded-lg border border-line bg-panel p-4"
      aria-labelledby="report-title"
    >
      <h2
        id="report-title"
        className="font-display text-2xl font-semibold text-pack"
      >
        {clipLabel(report.titulo || "Report")}
      </h2>
      {report.gancho_demo && (
        <p className="mt-1 font-display text-lg text-[var(--text)]">
          {clipLabel(report.gancho_demo)}
        </p>
      )}
      <p className="mt-2 text-sm leading-relaxed">{clipLabel(report.resumen || "")}</p>

      {report.especies && report.especies.length > 0 && (
        <ul className="mt-3 flex flex-wrap gap-2">
          {report.especies.map((e) => (
            <li
              key={e.clase}
              className="rounded-full border border-line px-2.5 py-0.5 text-xs"
            >
              <span className="text-pack">{e.clase}</span> · {e.individuos}
            </li>
          ))}
        </ul>
      )}

      {report.recomendaciones && report.recomendaciones.length > 0 && (
        <div className="mt-3">
          <h3 className="text-[11px] font-bold uppercase tracking-wide text-muted">
            Recommendations
          </h3>
          <ul className="mt-1 list-inside list-disc text-sm">
            {report.recomendaciones.map((r, i) => (
              <li key={i}>{r}</li>
            ))}
          </ul>
        </div>
      )}
    </article>
  );
}

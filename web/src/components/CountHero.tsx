"use client";

import { useEffect, useRef, useState } from "react";

type Props = {
  /** unique_count — número grande. */
  unique: number;
  /**
   * detections_total del result.json (opcional, flat).
   * Si falta → no mostrar el número tachado (no caer a naive_count).
   */
  detectionsTotal?: number | null;
  byClass: Record<string, number>;
  isMock: boolean;
  /** Índice cargado y pack sin corrida. */
  empty?: boolean;
  /** Mientras carga el índice / la corrida. */
  loading?: boolean;
};

function prefersReducedMotion(): boolean {
  if (typeof window === "undefined") return false;
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function useOdometer(target: number, enabled: boolean): number {
  const [value, setValue] = useState(target);
  const fromRef = useRef(target);

  useEffect(() => {
    if (!enabled) {
      setValue(target);
      fromRef.current = target;
      return;
    }
    if (prefersReducedMotion()) {
      setValue(target);
      fromRef.current = target;
      return;
    }
    const from = fromRef.current;
    const t0 = performance.now();
    let raf = 0;
    const tick = (t: number) => {
      const k = Math.min(1, (t - t0) / 600);
      setValue(Math.round(from + (target - from) * k));
      if (k < 1) raf = requestAnimationFrame(tick);
      else fromRef.current = target;
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target, enabled]);

  return value;
}

/**
 * Contador NOVA: tachado = detections_total («detecciones»);
 * grande = unique_count. Sin detections_total → ocultar tachado.
 * loading → «Cargando corrida»; empty → «Sin corrida…» solo tras índice.
 */
export function CountHero({
  unique,
  detectionsTotal,
  byClass,
  isMock,
  empty,
  loading,
}: Props) {
  const shown = useOdometer(empty || loading ? 0 : unique, !empty && !loading);
  const classes = Object.entries(byClass)
    .map(([k, v]) => `${k} ${v}`)
    .join(" · ");
  const hasDetections =
    typeof detectionsTotal === "number" && Number.isFinite(detectionsTotal);

  if (loading) {
    return (
      <div className="rounded-lg border border-line bg-panel p-4" role="status" aria-live="polite">
        <p className="text-sm text-muted">Cargando corrida</p>
        <p className="font-display text-hero text-pack/40">—</p>
      </div>
    );
  }

  if (empty) {
    return (
      <div className="rounded-lg border border-line bg-panel p-4">
        <p className="text-sm text-muted">Sin corrida para este video</p>
        <p className="font-display text-hero text-pack/40">—</p>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-line bg-panel p-4">
      <div className="flex items-center justify-between gap-2">
        <p className="font-display text-[28px] font-semibold text-muted">
          {hasDetections ? (
            <>
              <span className="sr-only">Detecciones </span>
              <s className="decoration-[3px]">{detectionsTotal}</s>
              <span className="ml-1 text-sm font-sans font-normal normal-case tracking-normal text-muted">
                detecciones
              </span>
              <span className="mx-2 text-pack">→</span>
              <span className="sr-only">individuos únicos Rastro </span>
            </>
          ) : (
            <span className="sr-only">Individuos únicos Rastro </span>
          )}
        </p>
        <span
          className={
            "rounded-full px-2 py-0.5 text-[11px] font-bold uppercase tracking-wide " +
            (isMock ? "bg-[var(--line)] text-muted" : "bg-pack text-ink")
          }
          title={
            isMock ? "Datos de ejemplo (mock)" : "Corrida medida con la API"
          }
        >
          {isMock ? "ejemplo" : "medido"}
        </span>
      </div>
      <p
        className="font-display text-hero text-pack"
        aria-live="polite"
        aria-label={
          hasDetections
            ? `Únicos Rastro: ${shown}, detecciones ${detectionsTotal}`
            : `Únicos Rastro: ${shown}`
        }
      >
        {shown}
      </p>
      <p className="mt-1 text-sm text-muted">
        {classes || "sin clases"} · Rastro cuenta individuos, no fotos
      </p>
    </div>
  );
}

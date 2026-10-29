"use client";

import { useEffect, useMemo, useState } from "react";
import {
  getMockJobsAdapter,
  PIPELINE_STAGES,
  QUEUED_STALL_MS,
  stageIndex,
  type Job,
  type JobsAdapter,
} from "@/lib/jobs";

type Props = {
  jobId: string | null;
  /** Adapter (default: mock compartido). */
  adapter?: JobsAdapter;
  onDone?: (runId: string | null, job: Job) => void;
  onTryAnother?: () => void;
  /** Ancla a ejemplos guardados del panel. */
  examplesHref?: string;
};

function prefersReducedMotion(): boolean {
  if (typeof window === "undefined") return false;
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/**
 * Progreso de un job. Sin porcentajes inventados.
 * Etapas solo si job.stage ∈ descargando|motor|guardando.
 */
export function JobProgress({
  jobId,
  adapter,
  onDone,
  onTryAnother,
  examplesHref = "#ejemplos",
}: Props) {
  const ads = adapter ?? getMockJobsAdapter();
  const [job, setJob] = useState<Job | null>(null);
  const [queuedMs, setQueuedMs] = useState(0);
  const [reduceMotion, setReduceMotion] = useState(false);

  useEffect(() => {
    setReduceMotion(prefersReducedMotion());
  }, []);

  useEffect(() => {
    if (!jobId) {
      setJob(null);
      return;
    }
    return ads.watchJob(jobId, setJob);
  }, [jobId, ads]);

  // Reloj de cola (aviso a los 60s)
  const jobStatus = job?.status;
  const jobAttempts = job?.attempts;
  const jobKey = job?.id;
  useEffect(() => {
    if (!jobKey || jobStatus !== "queued") {
      setQueuedMs(0);
      return;
    }
    const t0 = Date.now();
    const id = setInterval(() => setQueuedMs(Date.now() - t0), 1000);
    return () => clearInterval(id);
  }, [jobKey, jobStatus, jobAttempts]);

  useEffect(() => {
    if (job?.status === "done") {
      onDone?.(job.run_id, job);
    }
  }, [job?.status, job?.run_id]); // eslint-disable-line react-hooks/exhaustive-deps

  const idx = stageIndex(job?.stage ?? null);
  const showStages = Boolean(job?.stage);
  const stalled = job?.status === "queued" && queuedMs >= QUEUED_STALL_MS;
  const retrying =
    job?.status === "queued" && (job.attempts ?? 0) > 1;

  const statusLabel = useMemo(() => {
    if (!job) return "";
    if (retrying) return `Reintentando (${job.attempts} de 3)`;
    if (job.status === "queued") return "En cola";
    if (job.status === "processing") return "Procesando";
    if (job.status === "done") return "Listo";
    if (job.status === "failed") return "Falló";
    return job.status;
  }, [job, retrying]);

  if (!jobId || !job) return null;

  const valuemax = showStages ? PIPELINE_STAGES.length : 3;
  const valuenow =
    job.status === "done"
      ? valuemax
      : job.status === "failed"
        ? 0
        : showStages
          ? Math.max(0, idx + 1)
          : job.status === "processing"
            ? 2
            : 1;

  return (
    <section
      className="rounded-lg border border-line bg-panel p-4"
      aria-labelledby="job-progress-title"
    >
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <h2
          id="job-progress-title"
          className="font-display text-xl font-semibold text-pack"
        >
          {statusLabel}
        </h2>
        <span className="rounded-full bg-[var(--line)] px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-muted">
          simulado
        </span>
      </div>

      <div
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={valuemax}
        aria-valuenow={valuenow}
        aria-valuetext={statusLabel}
        aria-label="Progreso del trabajo"
        className="mb-3 h-2 overflow-hidden rounded-full bg-[var(--line)]"
      >
        <div
          className={
            "h-full bg-pack " +
            (reduceMotion ? "" : "transition-[width] duration-500 ease-out")
          }
          style={{
            width: `${Math.round((valuenow / valuemax) * 100)}%`,
          }}
        />
      </div>

      <div className="text-sm" aria-live="polite" aria-atomic="true">
        {job.status === "queued" && (
          <div>
            <p>En cola{retrying ? ` · intento ${job.attempts} de 3` : ""}.</p>
            {stalled && (
              <p className="mt-2 text-muted">
                El procesador no está conectado.{" "}
                <a
                  href={examplesHref}
                  className="text-pack underline underline-offset-2"
                >
                  Ver ejemplos guardados
                </a>
                .
              </p>
            )}
          </div>
        )}

        {job.status === "processing" && showStages && (
          <ol className="space-y-1">
            {PIPELINE_STAGES.map((s, i) => {
              const done = i < idx;
              const current = i === idx;
              return (
                <li
                  key={s.id}
                  className={
                    current
                      ? "font-semibold text-pack"
                      : done
                        ? "text-[var(--text)]"
                        : "text-muted"
                  }
                >
                  <span aria-hidden className="mr-2">
                    {done ? "✓" : current ? "●" : "○"}
                  </span>
                  {s.label}
                  {done && <span className="sr-only"> (hecho)</span>}
                  {current && <span className="sr-only"> (en curso)</span>}
                  {!done && !current && (
                    <span className="sr-only"> (pendiente)</span>
                  )}
                </li>
              );
            })}
          </ol>
        )}

        {job.status === "processing" && !showStages && (
          <p>Procesando…</p>
        )}

        {job.status === "failed" && (
          <div>
            <p className="text-alta">
              {job.error?.split("\n")[0] || "El trabajo falló."}
            </p>
            <button
              type="button"
              className="mt-3 rounded-full border border-line px-4 py-1.5 text-sm hover:border-pack"
              onClick={onTryAnother}
            >
              Probar con otro clip
            </button>
          </div>
        )}

        {job.status === "done" && (
          <p>
            Listo
            {job.run_id ? (
              <>
                {" "}
                · abriendo resultado <code>{job.run_id}</code>
              </>
            ) : null}
            .
          </p>
        )}
      </div>

      <p className="mt-3 text-[11px] text-muted">
        job <code>{job.id.slice(0, 8)}</code>
        {job.attempts > 0 ? ` · attempts ${job.attempts}` : ""} · sin
        porcentajes inventados
      </p>
    </section>
  );
}

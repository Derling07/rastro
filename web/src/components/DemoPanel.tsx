"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  fetchRun,
  fetchRunsIndex,
  packByKey,
  type PackKey,
  type RastroResult,
  type RunIndexEntry,
  type RunsIndex,
} from "@/lib/result";
import { getMockJobsAdapter } from "@/lib/jobs";
import { PackSwitcher } from "./PackSwitcher";
import { CountHero } from "./CountHero";
import {
  AnnotatedPlayer,
  type AnnotatedPlayerHandle,
} from "./AnnotatedPlayer";
import { AlertList } from "./AlertList";
import { VoiceNotePanel } from "./VoiceNote";
import { AgentLog } from "./AgentLog";
import { ReportView } from "./ReportView";
import { UploadDrop } from "./UploadDrop";
import { EventTimeline } from "./EventTimeline";
import { JobProgress } from "./JobProgress";
import { TurnMatrix } from "./TurnMatrix";
import { MultitudesPanel } from "./MultitudesPanel";
import { PartialBanner } from "./PartialBanner";
import { buildTurnMatrix } from "@/lib/transito";
import { resolveZones } from "@/lib/multitudes";

const ACCENT: Record<PackKey, string> = {
  fauna: "#F2A93B",
  transito: "#C8E34A",
  multitudes: "#5CC8E0",
};

const DEFAULT_RUN = "demo-real-coyote-0112";

type LoadState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; result: RastroResult | null; sinCorrida: boolean };

export function DemoPanel() {
  const [index, setIndex] = useState<RunsIndex | null>(null);
  const [pack, setPack] = useState<PackKey>("fauna");
  const [runId, setRunId] = useState<string>(DEFAULT_RUN);
  const [load, setLoad] = useState<LoadState>({ status: "loading" });
  const [jobId, setJobId] = useState<string | null>(null);
  const playerRef = useRef<AnnotatedPlayerHandle>(null);
  const jobs = getMockJobsAdapter();

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const idx = await fetchRunsIndex();
        if (cancelled) return;
        setIndex(idx);
        const def = idx.default_run_id ?? idx.runs[0]?.id ?? DEFAULT_RUN;
        setRunId(def);
      } catch (e) {
        if (!cancelled) {
          setLoad({
            status: "error",
            message: e instanceof Error ? e.message : "Error de índice",
          });
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    document.documentElement.style.setProperty("--pack", ACCENT[pack]);
  }, [pack]);

  useEffect(() => {
    if (!index) return;
    const packMeta = index.packs[pack];
    const hasRun = Boolean(packMeta?.has_run) && !packMeta?._sin_corrida;
    if (!hasRun) {
      setLoad({ status: "ready", result: null, sinCorrida: true });
      return;
    }
    let cancelled = false;
    setLoad({ status: "loading" });
    (async () => {
      try {
        const result = await fetchRun(runId);
        if (cancelled) return;
        setLoad({ status: "ready", result, sinCorrida: false });
      } catch (e) {
        if (!cancelled) {
          setLoad({
            status: "error",
            message: e instanceof Error ? e.message : "Error al cargar",
          });
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [index, pack, runId]);

  const onPack = useCallback((key: PackKey) => {
    setPack(key);
  }, []);

  const seek = useCallback((t: number) => {
    playerRef.current?.seek(t);
  }, []);

  const onJobDone = useCallback((doneRunId: string | null) => {
    if (doneRunId) {
      setPack("fauna");
      setRunId(doneRunId);
    }
  }, []);

  const onTryAnother = useCallback(() => {
    setJobId(null);
  }, []);

  const startSimulatedJob = useCallback(() => {
    const job = jobs.startMockJob({
      packId: packByKey(pack).id,
      scenario: "success",
      doneRunId: DEFAULT_RUN,
    });
    setJobId(job.id);
  }, [jobs, pack]);

  const faunaRuns: RunIndexEntry[] =
    index?.runs.filter((r) => (r.pack as string) === "fauna" || !r.pack) ?? [];

  const indexLoading = !index && load.status !== "error";
  const result = load.status === "ready" ? load.result : null;
  // «sin corrida» solo tras índice cargado y pack sin run
  const empty = Boolean(index) && load.status === "ready" && load.sinCorrida;
  const counterLoading =
    indexLoading || (Boolean(index) && load.status === "loading" && !empty);
  const packMeta = packByKey(pack);

  return (
    <div className="mx-auto max-w-6xl px-4 py-6 sm:px-6">
      <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-muted">
            Meta hackathon · panel demo
          </p>
          <h1 className="font-display text-4xl font-bold tracking-tight sm:text-5xl">
            Rastro
          </h1>
          <p className="mt-1 max-w-xl text-sm text-muted">
            Motor que sigue y cuenta en video sin duplicar. Acento del pack:{" "}
            <span className="text-pack">{packMeta.label}</span>.
          </p>
        </div>
        <PackSwitcher
          active={pack}
          packStatus={index ? index.packs : null}
          onChange={onPack}
        />
      </header>

      <div id="ejemplos" className="scroll-mt-4" />

      {!empty && faunaRuns.length > 0 && pack === "fauna" && (
        <div className="mb-4 flex flex-wrap items-center gap-2">
          <span className="text-[11px] uppercase tracking-wide text-muted">
            Corrida
          </span>
          {faunaRuns.map((r) => (
            <button
              key={r.id}
              type="button"
              className={
                "rounded-full border px-3 py-1 text-xs " +
                (r.id === runId
                  ? "border-pack bg-pack text-ink"
                  : "border-line text-muted hover:border-pack")
              }
              aria-pressed={r.id === runId}
              onClick={() => setRunId(r.id)}
            >
              {r.label}
              {r.is_mock ? (
                <span className="ml-1 opacity-70">· ejemplo</span>
              ) : (
                <span className="ml-1 opacity-70">· medido</span>
              )}
            </button>
          ))}
        </div>
      )}

      {load.status === "error" && (
        <div
          className="mb-4 rounded-lg border border-alta/40 bg-panel p-4 text-sm"
          role="alert"
        >
          <p className="font-bold text-alta">No se pudo cargar</p>
          <p className="text-muted">{load.message}</p>
        </div>
      )}

      {!empty && !counterLoading && result?.partial === true && (
        <div className="mb-4">
          <PartialBanner partial={result.partial} />
        </div>
      )}

      <div className="stagger-in grid gap-4 lg:grid-cols-[1.4fr_1fr]">
        <div className="space-y-4">
          <AnnotatedPlayer
            ref={playerRef}
            src={empty || counterLoading ? null : result?.video.annotated_url}
            poster={result?.video.poster}
            frames={result?.frames ?? []}
            tracks={result?.tracks ?? []}
            isMock={result?.is_mock}
            empty={empty}
            heatZones={
              pack === "multitudes" && result && !empty && !counterLoading
                ? resolveZones(result.zones)
                : undefined
            }
            heatDensity={
              pack === "multitudes" && result && !empty && !counterLoading
                ? result.density
                : undefined
            }
          />
          <CountHero
            unique={result?.unique_count ?? 0}
            detectionsTotal={result?.detections_total ?? null}
            byClass={result?.by_class ?? {}}
            isMock={Boolean(result?.is_mock)}
            empty={empty}
            loading={counterLoading}
          />
          {pack === "transito" && (
            <TurnMatrix
              matrix={
                empty || counterLoading
                  ? {}
                  : buildTurnMatrix({
                      matriz: result?.report?.matriz_giros,
                      events: result?.events,
                    })
              }
              empty={empty}
              isMock={Boolean(result?.is_mock)}
            />
          )}
          {pack === "multitudes" && (
            <MultitudesPanel
              density={empty || counterLoading ? [] : result?.density ?? []}
              peak_density={
                empty || counterLoading ? null : result?.peak_density ?? null
              }
              persons_per_zone={
                empty || counterLoading
                  ? {}
                  : result?.persons_per_zone ?? {}
              }
              zones={
                empty || counterLoading ? [] : result?.zones ?? []
              }
              empty={empty}
              isMock={Boolean(result?.is_mock)}
              sampling_mode={result?.sampling_mode}
              onSeek={seek}
            />
          )}
          <UploadDrop
            packId={packMeta.id}
            onJobId={(id) => setJobId(id)}
          />
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              className="rounded-full border border-line px-3 py-1 text-xs text-muted hover:border-pack hover:text-[var(--text)]"
              onClick={startSimulatedJob}
            >
              Simular cola (demo)
            </button>
          </div>
          <JobProgress
            jobId={jobId}
            adapter={jobs}
            onDone={onJobDone}
            onTryAnother={onTryAnother}
            examplesHref="#ejemplos"
          />
        </div>

        <div className="space-y-4">
          <section aria-labelledby="alerts-h">
            <h2 id="alerts-h" className="mb-2 text-sm font-bold text-muted">
              Alertas
            </h2>
            {empty ? (
              <p className="text-sm text-muted">Sin corrida.</p>
            ) : counterLoading ? (
              <p className="text-sm text-muted">Cargando…</p>
            ) : (
              <AlertList alerts={result?.alerts ?? []} onSeek={seek} />
            )}
          </section>

          <section aria-labelledby="events-h">
            <h2 id="events-h" className="mb-2 text-sm font-bold text-muted">
              Eventos
            </h2>
            <EventTimeline
              events={result?.events ?? []}
              onSeek={seek}
              empty={empty}
              maxObjectsHit={
                empty || counterLoading
                  ? undefined
                  : result?.max_objects_hit
              }
            />
          </section>

          <VoiceNotePanel
            voice={empty || counterLoading ? null : result?.voice ?? null}
            report={result?.report ?? { titulo: "Sin reporte", resumen: "" }}
          />

          <ReportView
            report={result?.report ?? { titulo: "Sin reporte", resumen: "" }}
            empty={empty}
          />

          <AgentLog
            steps={empty || counterLoading ? [] : result?.agent_log ?? []}
          />

          {result && !empty && !counterLoading && (
            <p className="text-[11px] text-muted">
              run <code>{result.run_id}</code> · schema {result.schema_version}{" "}
              · costo ≈ ${result.cost_usd.toFixed(4)} ·{" "}
              {result.is_mock ? "ejemplo" : "medido"}
            </p>
          )}
        </div>
      </div>

      <footer className="mt-10 border-t border-line pt-4 text-xs text-muted">
        FRONT only · outputs vía <code>/runs/*/result.json</code> · packs
        tránsito/multitudes sin corrida (honesto).
      </footer>
    </div>
  );
}

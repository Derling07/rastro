"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertList } from "@/components/AlertList";
import { PartialBanner } from "@/components/PartialBanner";
import { MultitudesPanel } from "@/components/MultitudesPanel";
import { ReportView } from "@/components/ReportView";
import { TurnMatrix } from "@/components/TurnMatrix";
import { VoiceNotePanel } from "@/components/VoiceNote";
import { AgentLog } from "@/components/AgentLog";
import {
  PACKS,
  parseResult,
  type PackKey,
  type RastroResult,
} from "@/lib/result";
import { buildTurnMatrix } from "@/lib/transito";
import { AlertCard, type FieldNote } from "@/components/notebook/AlertCard";
import { DENSITY_MARK, clipLabel, finishSentence, moduleLabel, zoneLabel } from "@/lib/labels";
import { saveFieldNote } from "@/lib/saveNote";
import { NotebookShell } from "@/components/notebook/Shell";
import { Viewfinder } from "@/components/notebook/Viewfinder";
import { FrameStage } from "./FrameStage";
import { IdentityBoard, type Identity } from "./IdentityBoard";

type Sample = {
  id: string;
  pack: PackKey;
  title: string;
  hint: string;
};

type Job = {
  id: string;
  status: "queued" | "processing" | "done" | "failed" | string;
  stage: "descargando" | "motor" | "guardando" | null;
  pack?: string;
  title?: string;
  original_name?: string;
  naive_count?: number | null;
  unique_count?: number | null;
  detections_total?: number | null;
  is_mock?: boolean | null;
  error?: string | null;
  sampling_mode?: string | null;
  peak_persons?: number | null;
  peak_density_per_m2?: number | null;
  vehicle_count?: number | null;
};

type Envelope = {
  mock_mode: boolean;
  server_mock: boolean;
  hint: string;
  reidentifies: boolean;
  empty?: boolean;
  uncomputed?: boolean;
  identities: Identity[];
  pack: string;
  result: unknown;
};

const STAGES = [
  { id: "descargando", label: "Read" },
  { id: "motor", label: "Track" },
  { id: "guardando", label: "Save" },
] as const;

const ACCENT: Record<PackKey, string> = {
  fauna: "#8C4A16",
  transito: "#1B4F72",
  multitudes: "#7A3040",
};

const MODULE_HINT: Record<PackKey, string> = {
  fauna: "Camera traps. Counts animals, not every time one walks through.",
  transito: "Intersection. Counts vehicles and the turns they take.",
  multitudes: "Crowd density. How many people, never who.",
};

function busiestTime(frames: { t_s: number; objects: unknown[] }[]): number {
  let best = frames[0];
  for (const frame of frames) {
    if ((frame.objects?.length ?? 0) > (best?.objects?.length ?? 0)) best = frame;
  }
  return best?.t_s ?? 0;
}

function friendlyError(raw: string | null | undefined): string {
  if (!raw || raw.toLowerCase().includes("mock failure")) {
    return "This run failed. Nothing was counted.";
  }
  return raw;
}

function densityText(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(2).replace(/\.?0+$/, "");
}

function transitHeadline(result: RastroResult): string {
  if (typeof result.naive_count !== "number") return "No verified vehicle count";
  return `${result.naive_count} sightings in this clip. No verified vehicle count.`;
}

function historyCount(item: Job): string {
  if (item.pack === "multitudes") {
    if (typeof item.peak_density_per_m2 === "number") {
      return ` · Peak density ${item.peak_density_per_m2} people/m² ${DENSITY_MARK}`;
    }
    return "";
  }
  if (item.pack === "transito") {
    if (typeof item.naive_count === "number") {
      return ` · ${item.naive_count} sightings in this clip. No verified vehicle count.`;
    }
    return " · No verified vehicle count";
  }
  if (typeof item.unique_count !== "number") {
    return "";
  }
  const left =
    item.pack !== "transito" &&
    typeof item.detections_total === "number" &&
    item.detections_total !== item.naive_count
      ? item.detections_total
      : item.naive_count;
  if (typeof left !== "number") {
    return item.pack === "transito" ? " · not verified" : "";
  }
  return ` · ${left} → ${item.unique_count}`;
}

function crowdHeadline(result: RastroResult): string {
  const density = result.peak_density?.density_per_m2;
  if (typeof density !== "number") return "No verified person count";
  const zone = zoneLabel(result.peak_density?.zone);
  const line = finishSentence(
    `Peak density ${densityText(density)} people/m² ${DENSITY_MARK}`,
  );
  return zone ? `${line} ${finishSentence(zone)}` : line;
}

function nounFor(pack: PackKey, byClass?: Record<string, number>): string {
  if (pack === "transito") return "vehicles";
  if (pack === "multitudes") return "people";
  const names = Object.entries(byClass ?? {}).filter(([, count]) => count > 0);
  if (names.length === 1) {
    const name = names[0][0];
    return names[0][1] === 1 || name.endsWith("s") ? name : `${name}s`;
  }
  return "individuals";
}

export function Studio() {
  const [pack, setPack] = useState<PackKey>("fauna");
  const [samples, setSamples] = useState<Sample[] | null>(null);
  const [serverMock, setServerMock] = useState(true);
  const [offline, setOffline] = useState(false);
  const [history, setHistory] = useState<Job[]>([]);
  const [job, setJob] = useState<Job | null>(null);
  const [envelope, setEnvelope] = useState<Envelope | null>(null);
  const [parsed, setParsed] = useState<RastroResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [voice, setVoice] = useState<File | null>(null);
  const [voicePublic, setVoicePublic] = useState(false);
  const [time, setTime] = useState(0);
  const [note, setNote] = useState<FieldNote | null>(null);

  const refreshHistory = useCallback(async () => {
    const res = await fetch("/engine/api/jobs", { cache: "no-store" });
    if (!res.ok) return;
    const body = (await res.json()) as { jobs: Job[] };
    setHistory(body.jobs);
  }, []);

  useEffect(() => {
    document.documentElement.style.setProperty("--pack", ACCENT[pack]);
  }, [pack]);

  useEffect(() => {
    if (!job || job.status !== "done") {
      setNote(null);
      return;
    }
    let cancel = false;
    const runId = job.id;
    fetch(`/engine/api/field-note?run=${encodeURIComponent(runId)}`, { cache: "no-store" })
      .then(async (res) => {
        if (res.status === 404) return null;
        if (!res.ok) throw new Error("note");
        return (await res.json()) as { note: FieldNote };
      })
      .then((body) => {
        if (!cancel) setNote(body?.note ?? null);
      })
      .catch(() => {
        if (!cancel) setNote(null);
      });
    return () => {
      cancel = true;
    };
  }, [job]);

  async function decideNote(action: "confirm" | "dismiss" | "review") {
    if (!note) return;
    setError(null);
    setNote(await saveFieldNote(note.id, action));
  }

  useEffect(() => {
    let cancel = false;
    (async () => {
      try {
        const [sampleRes, healthRes] = await Promise.all([
          fetch("/engine/api/samples", { cache: "no-store" }),
          fetch("/engine/health", { cache: "no-store" }),
        ]);
        if (!sampleRes.ok || !healthRes.ok) throw new Error("offline");
        const sampleBody = (await sampleRes.json()) as { samples: Sample[]; mock_mode: boolean };
        const health = (await healthRes.json()) as { mock_mode: boolean };
        if (cancel) return;
        setSamples(sampleBody.samples);
        setServerMock(health.mock_mode);
        setOffline(false);
        await refreshHistory();
      } catch {
        if (!cancel) setOffline(true);
      }
    })();
    return () => {
      cancel = true;
    };
  }, [refreshHistory]);

  const jobId = job?.id;
  const jobStatus = job?.status;
  useEffect(() => {
    if (!jobId || jobStatus === "done" || jobStatus === "failed") return;
    let cancel = false;
    const tick = async () => {
      try {
        const res = await fetch(`/engine/api/jobs/${jobId}`, { cache: "no-store" });
        if (!res.ok || cancel) return;
        const next = (await res.json()) as Job;
        if (cancel) return;
        if (next.status === "done") {
          const resultRes = await fetch(`/engine/api/jobs/${jobId}/result`, { cache: "no-store" });
          if (!resultRes.ok) throw new Error("result");
          const env = (await resultRes.json()) as Envelope;
          if (cancel) return;
          setEnvelope(env);
          const parsedNext = parseResult(env.result, jobId);
          setParsed(parsedNext);
          setTime(busiestTime(parsedNext.frames));
          setJob(next);
          setBusy(false);
          void refreshHistory();
          return;
        }
        if (next.status === "failed") {
          setJob(next);
          setError(next.error || "The run failed.");
          setBusy(false);
          void refreshHistory();
          return;
        }
        setJob(next);
      } catch {
        if (!cancel) {
          setError("Lost contact with the worker.");
          setBusy(false);
        }
      }
    };
    const id = window.setInterval(() => void tick(), 400);
    void tick();
    return () => {
      cancel = true;
      window.clearInterval(id);
    };
  }, [jobId, jobStatus, refreshHistory]);

  useEffect(() => {
    if (job) return;
    const active = history.find((item) => item.status === "queued" || item.status === "processing");
    if (!active) return;
    setBusy(true);
    setError(null);
    setJob(active);
    if (active.pack === "fauna" || active.pack === "transito" || active.pack === "multitudes") {
      setPack(active.pack);
    }
  }, [history, job]);

  const packSamples = useMemo(
    () => (samples ?? []).filter((sample) => sample.pack === pack),
    [samples, pack],
  );

  async function openJob(next: Job) {
    setError(null);
    setJob(next);
    if (next.pack === "fauna" || next.pack === "transito" || next.pack === "multitudes") {
      setPack(next.pack);
    }
    if (next.status !== "done") {
      setEnvelope(null);
      setParsed(null);
      setBusy(next.status === "queued" || next.status === "processing");
      return;
    }
    setBusy(true);
    try {
      const res = await fetch(`/engine/api/jobs/${next.id}/result`, { cache: "no-store" });
      if (!res.ok) throw new Error("result");
      const env = (await res.json()) as Envelope;
      const parsedNext = parseResult(env.result, next.id);
      setEnvelope(env);
      setParsed(parsedNext);
      setTime(busiestTime(parsedNext.frames));
    } catch {
      setError("Could not open that run.");
    } finally {
      setBusy(false);
    }
  }

  async function runSample(sampleId: string) {
    setError(null);
    setEnvelope(null);
    setParsed(null);
    setBusy(true);
    try {
      const res = await fetch("/engine/api/jobs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sample_id: sampleId }),
      });
      const body = (await res.json()) as Job & { error?: string };
      if (!res.ok) throw new Error(body.error || "Could not start the run.");
      setJob(body);
    } catch (err) {
      setBusy(false);
      setError(err instanceof Error ? err.message : "Could not start the run.");
    }
  }

  async function runUpload() {
    setError(null);
    if (!file) {
      setError("Choose an MP4 or MOV first.");
      return;
    }
    const name = file.name.toLowerCase();
    const okExt = name.endsWith(".mp4") || name.endsWith(".mov");
    if (!okExt) {
      setError("Only .mp4 or .mov files are accepted.");
      return;
    }
    const header = new Uint8Array(await file.slice(0, 64).arrayBuffer());
    const headerText = new TextDecoder("latin1").decode(header);
    if (!headerText.includes("ftyp")) {
      setError("That file is not an MP4 or MOV.");
      return;
    }
    if (file.size > 50 * 1024 * 1024) {
      setError("That file is over 50 MB.");
      return;
    }
    setEnvelope(null);
    setParsed(null);
    setBusy(true);
    try {
      const form = new FormData();
      form.set("pack", pack);
      form.set("video", file);
      if (voice) form.set("voice", voice);
      if (voicePublic) form.set("voice_public", "true");
      const res = await fetch("/engine/api/jobs", { method: "POST", body: form });
      const body = (await res.json()) as Job & { error?: string };
      if (!res.ok) throw new Error(body.error || "Could not start the run.");
      setJob(body);
    } catch (err) {
      setBusy(false);
      setError(err instanceof Error ? err.message : "Could not start the run.");
    }
  }

  const showFrames = Boolean(parsed && envelope && !envelope.empty && envelope.reidentifies);
  const seek = useCallback((t: number) => setTime(t), []);

  return (
    <NotebookShell current="analyze">
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_240px]" data-module={pack}>
      <div>
        <p className="mb-4 text-sm text-muted">
          {serverMock
            ? "Mock mode. Set RASTRO_LIVE=1 before a key can call a model. Samples stay on the mock tracker."
            : "Live keys. RASTRO_LIVE=1 is set, so uploads can call SAM and Muse Spark. Samples stay on the mock tracker."}
        </p>

        {offline && (
          <p className="mb-4 rounded-lg border border-alta/50 bg-panel p-3 text-sm" role="alert">
            Can{"'"}t reach the analysis server, try again
          </p>
        )}

        <section aria-labelledby="sector-h" className="mb-6">
          <h2 id="sector-h" className="text-xs font-bold uppercase tracking-[0.16em] text-muted">
            1 · Module
          </h2>
          <div className="mt-2 flex flex-wrap gap-2" role="group" aria-label="Module">
            {PACKS.map((item) => (
              <button
                key={item.key}
                type="button"
                className={
                  "chip max-w-xs px-3 py-2 text-sm " +
                  (item.key === pack ? "" : "text-[var(--ink)]")
                }
                aria-pressed={item.key === pack}
                onClick={() => setPack(item.key)}
              >
                <span className="block font-bold">{item.label}</span>
                <span className="mt-0.5 block text-[11px] font-normal leading-snug opacity-80">
                  {MODULE_HINT[item.key]}
                </span>
              </button>
            ))}
          </div>
        </section>

        {!showFrames && (
          <Viewfinder label="Simulated camera">
            <div className="flex aspect-video items-center justify-center px-6 text-center text-sm text-[#d7e0d8]">
              Pick a module, then run a sample. The clip plays in this frame.
            </div>
          </Viewfinder>
        )}

        <section aria-labelledby="video-h" className="mb-6 mt-6">
          <h2 id="video-h" className="text-xs font-bold uppercase tracking-[0.16em] text-muted">
            2 · Video
          </h2>
          <p className="mt-1 text-sm text-muted">Try a sample in one click, or add your own clip.</p>
          <div className="mt-3 grid gap-2 sm:grid-cols-2">
            {packSamples.map((sample) => (
              <button
                key={sample.id}
                type="button"
                className="sample-card text-left"
                disabled={busy}
                title={sample.hint}
                onClick={() => void runSample(sample.id)}
              >
                <span className="font-display text-2xl leading-none">{sample.title}</span>
                <span className="mt-1 block text-sm text-muted">{sample.hint}</span>
                <span className="mt-2 inline-block text-xs font-bold uppercase tracking-wide text-pack">
                  Run
                </span>
              </button>
            ))}
            {!samples && !offline && <p className="text-sm text-muted">Loading samples…</p>}
          </div>

          <div
            className="mt-3 rounded-lg border border-dashed border-line bg-panel/60 p-3"
            onDragOver={(event) => event.preventDefault()}
            onDrop={(event) => {
              event.preventDefault();
              const next = event.dataTransfer.files?.[0];
              if (next) setFile(next);
            }}
          >
            <label className="block text-sm">
              MP4 or MOV, up to 50 MB
              <input
                className="mt-2 block w-full text-sm text-muted file:mr-3 file:cursor-pointer file:rounded-full file:border file:border-line file:bg-panel file:px-3 file:py-1 file:text-sm file:font-bold file:text-[var(--text)]"
                type="file"
                accept="video/mp4,video/quicktime,.mp4,.mov"
                onChange={(event) => setFile(event.target.files?.[0] ?? null)}
              />
            </label>
            <label className="mt-3 block text-sm" title="Optional. Off by default, the transcript stays private.">
              Voice note, optional
              <input
                className="mt-2 block w-full text-sm text-muted file:mr-3 file:cursor-pointer file:rounded-full file:border file:border-line file:bg-panel file:px-3 file:py-1 file:text-sm file:font-bold file:text-[var(--text)]"
                type="file"
                accept="audio/wav,audio/mpeg,.wav,.mp3"
                onChange={(event) => setVoice(event.target.files?.[0] ?? null)}
              />
            </label>
            <label className="mt-3 flex items-center gap-2 text-sm" title="Leave off unless this note can be shown.">
              <input
                type="checkbox"
                checked={voicePublic}
                onChange={(event) => setVoicePublic(event.target.checked)}
              />
              Show the transcript
            </label>
            <button
              type="button"
              className="demo-primary"
              disabled={busy || !file}
              title={file ? "Track this file with the selected module." : "Choose a video first."}
              onClick={() => void runUpload()}
            >
              Run this file
            </button>
          </div>
        </section>

        <section aria-labelledby="run-h" className="mb-6" aria-live="polite">
          <h2 id="run-h" className="text-xs font-bold uppercase tracking-[0.16em] text-muted">
            3 · Run
          </h2>
          {!job && !error && (
            <p className="mt-2 text-sm text-muted">Waiting for a sample or a file.</p>
          )}
          {job && (
            <ol className="stage-list mt-2">
              {STAGES.map((stage) => {
                const idx = STAGES.findIndex((item) => item.id === stage.id);
                const current = STAGES.findIndex((item) => item.id === job.stage);
                const state =
                  job.status === "done"
                    ? "done"
                    : job.status === "failed"
                      ? "failed"
                      : idx < current
                        ? "done"
                        : idx === current && job.status === "processing"
                          ? "now"
                          : "wait";
                return (
                  <li key={stage.id} data-state={state}>
                    {stage.label}
                  </li>
                );
              })}
            </ol>
          )}
          {busy && job?.status !== "done" && <p className="mt-2 text-sm">Tracking…</p>}
          {error && job?.status !== "failed" && (
            <p className="mt-2 text-sm text-alta" role="alert">
              {friendlyError(error)}
            </p>
          )}
        </section>

        <section id="results" aria-labelledby="results-h">
          <h2 id="results-h" className="text-xs font-bold uppercase tracking-[0.16em] text-muted">
            4 · Results
          </h2>
          {job?.status === "failed" && (
            <div
              className="mt-2 rounded-lg border border-alta/50 bg-panel p-4"
              role="alert"
            >
              <p className="font-bold text-alta">This run failed</p>
              <p className="mt-1 text-sm text-muted">{friendlyError(error || job.error)}</p>
            </div>
          )}
          {job?.status !== "failed" && (!parsed || envelope?.empty) && (
            <p className="mt-2 rounded-lg border border-dashed border-line p-4 text-sm text-muted">
              {envelope?.empty
                ? "Empty result. This mock path finished with no counts."
                : pack === "multitudes"
                  ? "Nothing yet. A run reports how many people are in view at once. This module does not re-identify them."
                  : pack === "transito"
                    ? "Nothing yet. A run counts vehicles and the turns they take. Traffic counts are not verified."
                    : "Nothing yet. After a run, repeat appearances of the same individual collapse into one count."}
            </p>
          )}
          {parsed && envelope && !envelope.empty && (
            <div className="mt-3 space-y-4">
              <PartialBanner partial={parsed.partial} />
              <div className="flex flex-wrap items-center gap-2">
                <p className="text-xs font-bold uppercase tracking-[0.16em] text-muted">
                  {envelope.hint}
                </p>
                {pack === "transito" && (
                  <span className="rounded-full border border-alta px-2 py-0.5 text-[11px] font-bold uppercase tracking-wide text-alta">
                    Not verified
                  </span>
                )}
              </div>
              {envelope.uncomputed ? (
                <p className="rounded-lg border border-pack bg-panel p-4 font-display text-3xl leading-tight">
                  Sample result, not from your video
                </p>
              ) : envelope.reidentifies ? (
                <IdentityBoard
                  identities={envelope.identities}
                  naive={parsed.naive_count}
                  unique={parsed.unique_count}
                  detectionsTotal={parsed.detections_total}
                  noun={nounFor(pack, parsed.by_class)}
                  headline={pack === "transito" ? transitHeadline(parsed) : undefined}
                  unverified={false}
                  onSeek={seek}
                />
              ) : (
                <p className="rounded-lg border border-line bg-panel p-4 font-display text-3xl">
                  {crowdHeadline(parsed)}
                </p>
              )}
              {note && <AlertCard note={note} onAction={(action) => decideNote(action)} />}
              {envelope.reidentifies && (
                <FrameStage frames={parsed.frames} time={time} onTime={setTime} isMock={parsed.is_mock} />
              )}
              {pack === "transito" && (
                <TurnMatrix
                  matrix={buildTurnMatrix({
                    matriz: parsed.report?.matriz_giros,
                    events: parsed.events,
                  })}
                  isMock={parsed.is_mock}
                />
              )}
              {pack === "multitudes" && (
                <MultitudesPanel
                  density={parsed.density}
                  peak_density={parsed.peak_density}
                  persons_per_zone={parsed.persons_per_zone}
                  zones={parsed.zones}
                  isMock={parsed.is_mock}
                  sampling_mode={parsed.sampling_mode}
                  onSeek={seek}
                />
              )}
              <div>
                <h3 className="mb-2 text-sm font-bold text-muted">Alerts</h3>
                <AlertList alerts={parsed.alerts} onSeek={seek} />
              </div>
              <VoiceNotePanel voice={parsed.voice} report={parsed.report} />
              <ReportView report={parsed.report} />
              <AgentLog steps={parsed.agent_log} />
            </div>
          )}
        </section>
      </div>

      <aside aria-labelledby="history-h" className="lg:pt-16">
        <h2 id="history-h" className="text-xs font-bold uppercase tracking-[0.16em] text-muted">
          Runs
        </h2>
        {history.length === 0 ? (
          <p className="mt-2 text-sm text-muted">No runs yet.</p>
        ) : (
          <ul className="mt-2 max-h-[60vh] space-y-2 overflow-auto">
            {history.slice(0, 8).map((item) => (
              <li key={item.id}>
                <button
                  type="button"
                  className="w-full rounded-lg border border-line bg-panel px-3 py-2 text-left hover:border-pack"
                  onClick={() => void openJob(item)}
                >
                  <span className="block text-sm">{clipLabel(item.title || item.original_name || "Run")}</span>
                  <span className="text-xs text-muted">
                    {moduleLabel(item.pack)} · {item.status}
                    {item.is_mock ? " · mock" : ""}
                    {historyCount(item)}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </aside>
      <footer className="border-t border-line pt-4 text-xs leading-relaxed text-muted lg:col-span-2">
        <h2 className="text-[11px] font-bold uppercase tracking-[0.16em]">Data and credits</h2>
        <p className="mt-2">
          Wicker Park intersection changes by Steven Vance,{" "}
          <a className="underline" href="https://creativecommons.org/licenses/by/3.0/">
            CC BY 3.0
          </a>
          , via{" "}
          <a
            className="underline"
            href="https://commons.wikimedia.org/wiki/File:Wicker_Park_intersection_changes.webm"
          >
            Wikimedia Commons
          </a>
          .
        </p>
        <p className="mt-1">
          DSCF camera-trap clips, including the person on the forest trail: Seattle(ish) Camera
          Traps, Dan Morris, LILA BC. License: Community Data License Agreement (permissive
          variant). The published person clip has the face blurred.{" "}
          <a className="underline" href="https://lila.science/datasets/seattleish-camera-traps/">
            Dataset page
          </a>
          .
        </p>
        <p className="mt-1">
          Gray fox in New Mexico by Andy, CC BY 3.0. Goats going home by Thamizhpparithi Maari,
          CC BY-SA 3.0. Plaza Mayor (Madrid) by Michiel1972, CC BY-SA 3.0. All via Wikimedia Commons.
        </p>
      </footer>
    </div>
    </NotebookShell>
  );
}

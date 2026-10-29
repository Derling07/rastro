/**
 * Trabajos de cola (public.jobs — CORE migration + stage 38dd986).
 * status: queued | processing | done | failed
 * stage:  descargando | motor | guardando
 * Adapter mock: simula transiciones; sin Supabase ni claves. Siempre «simulado».
 */

export type JobStatus = "queued" | "processing" | "done" | "failed";

export type JobStageName = "descargando" | "motor" | "guardando";

export type JobStage = JobStageName | null;

export interface Job {
  id: string;
  storage_path: string;
  pack_id: string;
  original_name: string;
  size_bytes: number;
  content_type: "video/mp4" | "video/quicktime" | string;
  status: JobStatus;
  /** Si está presente, la UI lista las 3 etapas; si no, solo el status. */
  stage: JobStage;
  attempts: number;
  run_id: string | null;
  error: string | null;
  worker: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  simulado: true;
}

/** Únicas etapas de UI (= enum DB). Sin porcentajes inventados. */
export const PIPELINE_STAGES: readonly {
  id: JobStageName;
  label: string;
}[] = [
  { id: "descargando", label: "Descargando" },
  { id: "motor", label: "Motor" },
  { id: "guardando", label: "Guardando" },
] as const;

export const MAX_JOB_ATTEMPTS = 3;
export const QUEUED_STALL_MS = 60_000;

export function stageIndex(stage: JobStage): number {
  if (!stage) return -1;
  return PIPELINE_STAGES.findIndex((s) => s.id === stage);
}

export type MockScenario =
  | "success"
  | "fail-then-success"
  | "fail"
  | "stuck-queued";

export type JobsAdapter = {
  readonly simulado: true;
  getJob(id: string): Promise<Job | null>;
  watchJob(id: string, onUpdate: (job: Job) => void): () => void;
  startMockJob(opts?: {
    packId?: string;
    originalName?: string;
    scenario?: MockScenario;
    /** run_id al completar (para abrir en el contador). */
    doneRunId?: string;
  }): Job;
};

function uuid(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `mock-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function nowIso(): string {
  return new Date().toISOString();
}

function baseJob(
  partial: Partial<Job> & Pick<Job, "id" | "pack_id" | "original_name">,
): Job {
  return {
    storage_path: `videos/${partial.id}.mp4`,
    size_bytes: 1_024_000,
    content_type: "video/mp4",
    status: "queued",
    stage: null,
    attempts: 0,
    run_id: null,
    error: null,
    worker: null,
    created_at: nowIso(),
    started_at: null,
    finished_at: null,
    simulado: true,
    ...partial,
  };
}

export function createMockJobsAdapter(opts?: {
  tickMs?: number;
}): JobsAdapter {
  const tickMs = opts?.tickMs ?? 700;
  const store = new Map<string, Job>();
  const timers = new Map<string, ReturnType<typeof setInterval>>();
  const listeners = new Map<string, Set<(j: Job) => void>>();
  const scenarios = new Map<string, MockScenario>();
  const doneRuns = new Map<string, string>();

  const emit = (job: Job) => {
    store.set(job.id, job);
    listeners.get(job.id)?.forEach((fn) => fn(job));
  };

  const stop = (id: string) => {
    const t = timers.get(id);
    if (t) clearInterval(t);
    timers.delete(id);
  };

  const advance = (id: string) => {
    const scenario = scenarios.get(id) ?? "success";
    const job = store.get(id);
    if (!job) return;
    if (job.status === "done" || job.status === "failed") {
      stop(id);
      return;
    }
    if (scenario === "stuck-queued") return;

    if (job.status === "queued") {
      emit({
        ...job,
        status: "processing",
        attempts: job.attempts + 1,
        started_at: nowIso(),
        worker: "simulado@demo",
        stage: "descargando",
        error: null,
      });
      return;
    }

    // processing — avanzar etapas DB
    const idx = stageIndex(job.stage);
    if (idx >= 0 && idx < PIPELINE_STAGES.length - 1) {
      emit({ ...job, stage: PIPELINE_STAGES[idx + 1].id });
      return;
    }

    const shouldFail =
      scenario === "fail" ||
      (scenario === "fail-then-success" && job.attempts < 2);

    if (shouldFail) {
      if (job.attempts < MAX_JOB_ATTEMPTS) {
        emit({
          ...job,
          status: "queued",
          stage: null,
          error: "Fallo simulado del worker (reintento).",
          worker: null,
        });
      } else {
        emit({
          ...job,
          status: "failed",
          stage: null,
          error: "El worker falló tras 3 intentos (simulado).",
          finished_at: nowIso(),
        });
        stop(id);
      }
      return;
    }

    emit({
      ...job,
      status: "done",
      stage: null,
      run_id: doneRuns.get(id) ?? "demo-real-coyote-0112",
      finished_at: nowIso(),
      error: null,
    });
    stop(id);
  };

  const startTicking = (id: string) => {
    stop(id);
    timers.set(
      id,
      setInterval(() => advance(id), tickMs),
    );
  };

  return {
    simulado: true,
    async getJob(id) {
      return store.get(id) ?? null;
    },
    watchJob(id, onUpdate) {
      let set = listeners.get(id);
      if (!set) {
        set = new Set();
        listeners.set(id, set);
      }
      set.add(onUpdate);
      const cur = store.get(id);
      if (cur) onUpdate(cur);
      return () => {
        set!.delete(onUpdate);
        if (set!.size === 0) listeners.delete(id);
      };
    },
    startMockJob({
      packId = "fauna-camtrap",
      originalName = "clip-demo.mp4",
      scenario = "success",
      doneRunId = "demo-real-coyote-0112",
    } = {}) {
      const id = uuid();
      const job = baseJob({
        id,
        pack_id: packId,
        original_name: originalName,
      });
      scenarios.set(id, scenario);
      doneRuns.set(id, doneRunId);
      emit(job);
      startTicking(id);
      return job;
    },
  };
}

let shared: JobsAdapter | null = null;
export function getMockJobsAdapter(): JobsAdapter {
  if (!shared) shared = createMockJobsAdapter();
  return shared;
}

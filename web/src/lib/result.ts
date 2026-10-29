/**
 * Adaptador tipado de outputs/<run_id>/result.json
 * Schema: docs/OUTPUT_SCHEMA.md **v1.1**
 *
 * Reglas:
 * - Fuente de verdad = result.json (no DB para cajas).
 * - Máscaras solo en artifacts.annotated_video — la UI lo reproduce.
 * - frames[].objects[].bbox para resaltar un ID al hover/tap (no dibujar todas por defecto).
 * - voice.is_public: si falta → false (privada: solo resumen del report).
 * - CORE/Supabase aún no cableado (fetchRunOverviewFromSupabase es stub).
 */

export type PackKey = "fauna" | "transito" | "multitudes";
export type AlertSeverity = "info" | "media" | "alta" | "critica" | string;

/** bbox = [x1, y1, x2, y2] en píxeles del frame de trabajo. */
export type BBox = [number, number, number, number];

export interface FrameObject {
  track_id: string;
  class: string;
  bbox: BBox;
}

export interface Frame {
  frame: number;
  t_s: number;
  objects: FrameObject[];
}

export interface Track {
  track_id: string;
  class: string;
  start_frame: number;
  end_frame: number;
  dwell_s?: number;
  n_dets?: number;
}

export interface RastroEvent {
  kind?: string;
  t_s: number;
  track_id?: string;
  class?: string;
  dwell_s?: number;
  [key: string]: unknown;
}

export interface Alert {
  id: string;
  severity: AlertSeverity;
  message: string;
  /** Obligatorio en v1.1 — seek al hacer clic. */
  t_s: number;
  local_hour?: number;
  zone?: string;
}

export interface VoiceTurn {
  turn_id?: number;
  speaker: string;
  start_s: number;
  end_s: number;
  /** Schema usa transcript; aceptamos text como alias. */
  transcript: string;
}

export interface VoiceNote {
  transcript?: string;
  audio_duration_ms?: number;
  station?: string;
  local_hour?: number;
  est_usd?: number;
  is_mock?: boolean;
  mock?: boolean;
  session_id?: string;
  linked_note?: string;
  turns: VoiceTurn[];
  /**
   * Si falta en el JSON → se trata como false (privada).
   * Solo con true se muestra el texto de los turnos.
   */
  is_public: boolean;
}

export interface AgentStep {
  step: number | string;
  tool?: string;
  detail?: string;
  ok?: boolean;
  [key: string]: unknown;
}

export interface ReportSection {
  titulo: string;
  resumen: string;
  especies?: { clase: string; individuos: number }[];
  alertas?: { id: string; severidad: string; mensaje: string }[];
  recomendaciones?: string[];
  gancho_demo?: string;
  notas_campo?: string;
  /** Tránsito: conteos origen→destino (N/S/E/O). */
  matriz_giros?: Record<string, number>;
  [key: string]: unknown;
}

export interface Counts {
  naive: number;
  unique: number;
  by_class: Record<string, number>;
  /** Detecciones crudas SAM (opcional, schema 1.1 aditivo). */
  detections_total?: number;
}

export interface VideoMeta {
  path?: string | null;
  fps: number;
  native_fps?: number;
  /** Helpers de la web (no schema): URL servida del annotated.mp4 */
  url?: string | null;
  annotated_url?: string | null;
  poster?: string | null;
}

export interface PackInfo {
  id: string;
  version?: string;
  path?: string;
}

export interface Artifacts {
  annotated_video?: string | null;
  blurred_video?: string | null;
  voice_json?: string | null;
  cost_json?: string | null;
  tracks_json?: string | null;
}

export interface CostInfo {
  est_usd_sam?: number;
  est_usd_voice?: number;
  est_usd_total?: number;
}

export interface DensitySample {
  t_s: number;
  zone: string;
  persons: number;
  /** null si la zona no tiene area_m2 (NOVA: solo mostrar persons). */
  density_per_m2: number | null;
}

export interface PeakDensity {
  zone: string;
  t_s: number;
  persons: number;
  density_per_m2: number | null;
}

/** Zona de geometría (espejo pack o embebida en result). */
export interface ZoneInfo {
  id: string;
  polygon: [number, number][];
  area_m2: number | null;
}

/** Forma canónica v1.1 + helpers de UI. */
export interface RastroResult {
  schema_version: string;
  run_id: string;
  source_video_id: string;
  created_at?: string;
  pack: PackInfo;
  pack_key: PackKey;
  video: VideoMeta;
  station?: string;
  local_hour?: number | null;
  naive_count: number;
  unique_count: number;
  /** Opcional: si falta, la UI no muestra el tachado. */
  detections_total: number | null;
  by_class: Record<string, number>;
  cost_usd: number;
  counts: Counts;
  tracks: Track[];
  frames: Frame[];
  events: RastroEvent[];
  alerts: Alert[];
  voice: VoiceNote | null;
  agent_log: AgentStep[];
  report: ReportSection;
  artifacts: Artifacts;
  cost: CostInfo;
  sam?: unknown[];
  is_mock: boolean;
  /** Multitudes aditivo 1.1 */
  density: DensitySample[];
  peak_density: PeakDensity | null;
  persons_per_zone: Record<string, number>;
  sampling_mode?: "video_track" | "image_sample" | string;
  /** Zonas con área (pack o result); area_m2 null → sin densidad. */
  zones: ZoneInfo[];
  /**
   * Futuro motor: conteo parcial (tope de objetos/frame).
   * Solo mostrar banner si el campo está presente y es true.
   */
  partial?: boolean;
  /** Instantes t_s (segundos) donde se tocó el tope de objetos (opcional). */
  max_objects_hit?: number[];
}

export interface PackMeta {
  key: PackKey;
  id: string;
  file: string;
  label: string;
  description: string;
  accent: string;
}

/** Acentos NOVA DESIGN.md */
export const PACKS: PackMeta[] = [
  {
    key: "fauna",
    id: "fauna-camtrap",
    file: "fauna.json",
    label: "Fauna",
    description: "Cámaras trampa · individuos únicos",
    accent: "#F2A93B",
  },
  {
    key: "transito",
    id: "transito-giros",
    file: "transito.json",
    label: "Transit",
    description: "Intersección · matriz de giros",
    accent: "#C8E34A",
  },
  {
    key: "multitudes",
    id: "multitudes-densidad",
    file: "multitudes.json",
    label: "Crowd",
    description: "Densidad por zona · sin rostros",
    accent: "#5CC8E0",
  },
];

export function packByKey(key: PackKey): PackMeta {
  return PACKS.find((p) => p.key === key) ?? PACKS[0];
}

export function packKeyFromId(packId: string): PackKey {
  const id = packId.toLowerCase();
  if (id.includes("transito")) return "transito";
  if (id.includes("multitud")) return "multitudes";
  return "fauna";
}

export interface RunIndexEntry {
  id: string;
  label: string;
  pack: PackKey | string;
  pack_file?: string;
  source_video_id?: string;
  is_mock: boolean;
  naive_count?: number;
  unique_count?: number;
  path: string;
}

export interface RunsIndex {
  runs: RunIndexEntry[];
  packs: Record<
    string,
    { pack_file: string; has_run: boolean; _sin_corrida?: boolean }
  >;
  default_run_id?: string;
}

function asNum(v: unknown, fallback = 0): number {
  const n = Number(v);
  return Number.isFinite(n) ? n : fallback;
}

function normalizeBBox(raw: unknown): BBox {
  if (Array.isArray(raw) && raw.length >= 4) {
    return [asNum(raw[0]), asNum(raw[1]), asNum(raw[2]), asNum(raw[3])];
  }
  if (raw && typeof raw === "object") {
    const b = raw as Record<string, unknown>;
    return [asNum(b.x1), asNum(b.y1), asNum(b.x2), asNum(b.y2)];
  }
  return [0, 0, 0, 0];
}

function normalizeVoice(raw: unknown): VoiceNote | null {
  if (!raw || typeof raw !== "object") return null;
  const v = raw as Record<string, unknown>;
  const turnsRaw = Array.isArray(v.turns) ? v.turns : [];
  const turns: VoiceTurn[] = turnsRaw.map((t) => {
    const turn = t as Record<string, unknown>;
    const start =
      turn.start_s !== undefined
        ? asNum(turn.start_s)
        : asNum(turn.start_ms) / 1000;
    const end =
      turn.end_s !== undefined ? asNum(turn.end_s) : asNum(turn.end_ms) / 1000;
    return {
      turn_id: typeof turn.turn_id === "number" ? turn.turn_id : undefined,
      speaker: String(turn.speaker ?? "A"),
      start_s: start,
      end_s: end,
      transcript: String(turn.transcript ?? turn.text ?? ""),
    };
  });
  // v1.1: is_public aún no está en el schema — si falta, false (privada).
  const is_public = v.is_public === true;
  return {
    transcript: typeof v.transcript === "string" ? v.transcript : undefined,
    audio_duration_ms:
      typeof v.audio_duration_ms === "number" ? v.audio_duration_ms : undefined,
    station: typeof v.station === "string" ? v.station : undefined,
    local_hour: typeof v.local_hour === "number" ? v.local_hour : undefined,
    est_usd: typeof v.est_usd === "number" ? v.est_usd : undefined,
    is_mock: Boolean(v.is_mock ?? v.mock),
    mock: Boolean(v.mock),
    session_id: typeof v.session_id === "string" ? v.session_id : undefined,
    linked_note: typeof v.linked_note === "string" ? v.linked_note : undefined,
    turns,
    is_public,
  };
}

/** Parsea result.json v1.1. */
export function parseResult(raw: unknown, fallbackRunId = "unknown"): RastroResult {
  if (!raw || typeof raw !== "object") {
    throw new Error("result.json vacío o inválido");
  }
  const r = raw as Record<string, unknown>;

  const packRaw = r.pack;
  let pack: PackInfo;
  if (typeof packRaw === "string") {
    pack = { id: packRaw };
  } else if (packRaw && typeof packRaw === "object") {
    const p = packRaw as Record<string, unknown>;
    pack = {
      id: String(p.id ?? "fauna-camtrap"),
      version: typeof p.version === "string" ? p.version : undefined,
      path: typeof p.path === "string" ? p.path : undefined,
    };
  } else {
    pack = { id: "fauna-camtrap" };
  }

  const countsObj = (r.counts as Record<string, unknown>) ?? {};
  const videoObj = (r.video as Record<string, unknown>) ?? {};
  const costObj = (r.cost as Record<string, unknown>) ?? {};
  const artifactsObj = (r.artifacts as Record<string, unknown>) ?? {};
  const report = (r.report as ReportSection) ?? {
    titulo: "Sin reporte",
    resumen: "",
  };

  const naive = asNum(r.naive_count ?? countsObj.naive);
  const unique = asNum(r.unique_count ?? countsObj.unique);
  // Solo result.json (campo flat); si falta, null — la UI oculta el tachado.
  const detections_total =
    r.detections_total === undefined || r.detections_total === null
      ? null
      : asNum(r.detections_total);
  const by_class =
    (r.by_class as Record<string, number>) ??
    (countsObj.by_class as Record<string, number>) ??
    {};

  const framesSrc = Array.isArray(r.frames) ? r.frames : [];
  const frames: Frame[] = framesSrc.map((f) => {
    const fr = f as Record<string, unknown>;
    const objs = Array.isArray(fr.objects) ? fr.objects : [];
    return {
      frame: asNum(fr.frame),
      t_s: asNum(fr.t_s),
      objects: objs.map((o) => {
        const obj = o as Record<string, unknown>;
        return {
          track_id: String(obj.track_id ?? ""),
          class: String(obj.class ?? ""),
          bbox: normalizeBBox(obj.bbox),
        };
      }),
    };
  });

  const tracksSrc = Array.isArray(r.tracks) ? r.tracks : [];
  const tracks: Track[] = tracksSrc.map((t) => {
    const tr = t as Record<string, unknown>;
    return {
      track_id: String(tr.track_id ?? ""),
      class: String(tr.class ?? tr.class_name ?? "objeto"),
      start_frame: asNum(tr.start_frame),
      end_frame: asNum(tr.end_frame),
      dwell_s: tr.dwell_s !== undefined ? asNum(tr.dwell_s) : undefined,
      n_dets: tr.n_dets !== undefined ? asNum(tr.n_dets) : undefined,
    };
  });

  const alertsSrc = Array.isArray(r.alerts) ? r.alerts : [];
  const alerts: Alert[] = alertsSrc.map((a) => {
    const al = a as Record<string, unknown>;
    return {
      id: String(al.id ?? "alert"),
      severity: String(al.severity ?? "info"),
      message: String(al.message ?? al.mensaje ?? ""),
      t_s: asNum(al.t_s),
      local_hour: typeof al.local_hour === "number" ? al.local_hour : undefined,
      zone: typeof al.zone === "string" ? al.zone : undefined,
    };
  });

  const runId = String(r.run_id ?? fallbackRunId);
  const artifacts: Artifacts = {
    annotated_video: (artifactsObj.annotated_video as string | null) ?? null,
    blurred_video: (artifactsObj.blurred_video as string | null) ?? null,
    voice_json: (artifactsObj.voice_json as string | null) ?? null,
    cost_json: (artifactsObj.cost_json as string | null) ?? null,
    tracks_json: (artifactsObj.tracks_json as string | null) ?? null,
  };

  // URL del video anotado: helper web o /runs/<id>/<artifact>
  let annotatedUrl =
    (videoObj.annotated_url as string | null | undefined) ??
    (videoObj.url as string | null | undefined) ??
    null;
  if (!annotatedUrl && artifacts.annotated_video) {
    annotatedUrl = `/runs/${runId}/${artifacts.annotated_video}`;
  }

  const densitySrc = Array.isArray(r.density) ? r.density : [];
  const density: DensitySample[] = densitySrc.map((row) => {
    const d = row as Record<string, unknown>;
    const dens =
      d.density_per_m2 === undefined || d.density_per_m2 === null
        ? null
        : asNum(d.density_per_m2);
    return {
      t_s: asNum(d.t_s),
      zone: String(d.zone ?? ""),
      persons: asNum(d.persons),
      density_per_m2: dens,
    };
  });

  let peak_density: PeakDensity | null = null;
  if (r.peak_density && typeof r.peak_density === "object") {
    const p = r.peak_density as Record<string, unknown>;
    const dens =
      p.density_per_m2 === undefined || p.density_per_m2 === null
        ? null
        : asNum(p.density_per_m2);
    peak_density = {
      zone: String(p.zone ?? ""),
      t_s: asNum(p.t_s),
      persons: asNum(p.persons),
      density_per_m2: dens,
    };
  }

  const persons_per_zone: Record<string, number> = {};
  if (r.persons_per_zone && typeof r.persons_per_zone === "object") {
    for (const [k, v] of Object.entries(
      r.persons_per_zone as Record<string, unknown>,
    )) {
      persons_per_zone[k] = asNum(v);
    }
  }

  const zonesSrc = Array.isArray(r.zones)
    ? r.zones
    : Array.isArray((r.geometry as Record<string, unknown> | undefined)?.zones)
      ? ((r.geometry as Record<string, unknown>).zones as unknown[])
      : [];
  const zones: ZoneInfo[] = zonesSrc.map((z) => {
    const zo = z as Record<string, unknown>;
    const polyRaw = Array.isArray(zo.polygon) ? zo.polygon : [];
    const polygon: [number, number][] = polyRaw.map((pt) => {
      if (Array.isArray(pt) && pt.length >= 2) {
        return [asNum(pt[0]), asNum(pt[1])];
      }
      return [0, 0];
    });
    const area =
      zo.area_m2 === undefined || zo.area_m2 === null ? null : asNum(zo.area_m2);
    return { id: String(zo.id ?? ""), polygon, area_m2: area };
  });

  const sampling_mode =
    typeof r.sampling_mode === "string" ? r.sampling_mode : undefined;

  const partial =
    typeof r.partial === "boolean" ? r.partial : undefined;
  const max_objects_hit = Array.isArray(r.max_objects_hit)
    ? (r.max_objects_hit as unknown[]).map((n) => asNum(n))
    : undefined;

  const cost_usd = asNum(r.cost_usd ?? costObj.est_usd_total);

  return {
    schema_version: String(r.schema_version ?? "1.1"),
    run_id: runId,
    source_video_id: String(r.source_video_id ?? "unknown"),
    created_at: typeof r.created_at === "string" ? r.created_at : undefined,
    pack,
    pack_key: packKeyFromId(pack.id),
    video: {
      path: (videoObj.path as string | null | undefined) ?? null,
      fps: asNum(videoObj.fps, 5),
      native_fps:
        videoObj.native_fps !== undefined
          ? asNum(videoObj.native_fps)
          : undefined,
      url: annotatedUrl,
      annotated_url: annotatedUrl,
      poster: (videoObj.poster as string | null | undefined) ?? null,
    },
    station: typeof r.station === "string" ? r.station : undefined,
    local_hour:
      typeof r.local_hour === "number"
        ? r.local_hour
        : r.local_hour === null
          ? null
          : undefined,
    naive_count: naive,
    unique_count: unique,
    detections_total,
    by_class,
    cost_usd,
    counts: {
      naive,
      unique,
      by_class,
      ...(detections_total !== null ? { detections_total } : {}),
    },
    tracks,
    frames,
    events: (Array.isArray(r.events) ? r.events : []) as RastroEvent[],
    alerts,
    voice: normalizeVoice(r.voice),
    agent_log: (Array.isArray(r.agent_log) ? r.agent_log : []) as AgentStep[],
    report,
    artifacts,
    cost: {
      est_usd_sam:
        typeof costObj.est_usd_sam === "number" ? costObj.est_usd_sam : undefined,
      est_usd_voice:
        typeof costObj.est_usd_voice === "number"
          ? costObj.est_usd_voice
          : undefined,
      est_usd_total:
        typeof costObj.est_usd_total === "number"
          ? costObj.est_usd_total
          : undefined,
    },
    sam: Array.isArray(r.sam) ? r.sam : undefined,
    is_mock: Boolean(r.is_mock ?? r.mock),
    density,
    peak_density,
    persons_per_zone,
    sampling_mode,
    zones,
    ...(partial !== undefined ? { partial } : {}),
    ...(max_objects_hit !== undefined ? { max_objects_hit } : {}),
  };
}

/** Objetos del frame más cercano a t_s (para highlight al hover). */
export function objectsNearTime(frames: Frame[], t_s: number): FrameObject[] {
  if (!frames.length) return [];
  let best = frames[0];
  let bestDist = Math.abs(best.t_s - t_s);
  for (const f of frames) {
    const d = Math.abs(f.t_s - t_s);
    if (d < bestDist) {
      best = f;
      bestDist = d;
    }
  }
  // tolerancia ~ medio frame a 5 fps = 0.1s; usamos 0.25s
  if (bestDist > 0.3) return [];
  return best.objects;
}

export function objectsAtFrame(frames: Frame[], frame: number): FrameObject[] {
  const hit = frames.find((f) => f.frame === frame);
  return hit?.objects ?? [];
}

const TRACK_PALETTE = [
  "#F2A93B",
  "#5CC8E0",
  "#C8E34A",
  "#FF6B5B",
  "#E879F9",
  "#38BDF8",
  "#FB923C",
  "#A3E635",
];

export function colorForTrack(trackId: string): string {
  let h = 0;
  for (let i = 0; i < trackId.length; i++) {
    h = (h * 31 + trackId.charCodeAt(i)) >>> 0;
  }
  return TRACK_PALETTE[h % TRACK_PALETTE.length];
}

export async function fetchRun(runId: string): Promise<RastroResult> {
  const res = await fetch(`/runs/${runId}/result.json`);
  if (!res.ok) {
    throw new Error(`No se pudo cargar la corrida ${runId} (${res.status})`);
  }
  return parseResult(await res.json(), runId);
}

export async function fetchRunsIndex(): Promise<RunsIndex> {
  const res = await fetch("/runs/index.json");
  if (!res.ok) throw new Error("No se pudo cargar el índice de corridas");
  return res.json();
}

/** Stub CORE — no cablear aún (supabase/README.md). */
export async function fetchRunOverviewFromSupabase(): Promise<never> {
  throw new Error(
    "Supabase aún no cableado. Usá /runs/<id>/result.json.",
  );
}

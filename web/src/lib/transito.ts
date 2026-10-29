/**
 * Tránsito: matriz de giros N/S/E/O.
 * Fuente de verdad del pack = packs/transito.json (RO, pendiente ORION).
 * Hasta que exista corrida real: UI muestra layout vacío («sin corrida»).
 * No usar web/mock/transito-demo como corrida (solo diseño).
 */

export const CARDINALS = ["N", "S", "E", "O"] as const;
export type Cardinal = (typeof CARDINALS)[number];

/** Letter shown in the UI. Pack geometry still uses O for west. */
export const CARDINAL_LETTER: Record<Cardinal, string> = {
  N: "N",
  S: "S",
  E: "E",
  O: "W",
};

export const CARDINAL_LABEL: Record<Cardinal, string> = {
  N: "North",
  S: "South",
  E: "East",
  O: "West",
};

/** Líneas de acceso esperadas en packs/transito.json → geometry.lines[].id */
export const ACCESS_LINES: { id: string; from: Cardinal; label: string }[] = [
  { id: "acceso_N", from: "N", label: "Approach N" },
  { id: "acceso_S", from: "S", label: "Approach S" },
  { id: "acceso_E", from: "E", label: "Approach E" },
  { id: "acceso_O", from: "O", label: "Approach W" },
];

export type TurnKey = `${Cardinal}->${Cardinal}`;

export type TurnMatrixData = Partial<Record<TurnKey, number>>;

const MOVE_RE = /^([NSEO])->([NSEO])$/i;

export function parseMovement(raw: unknown): TurnKey | null {
  if (typeof raw !== "string") return null;
  const m = raw.trim().match(MOVE_RE);
  if (!m) return null;
  const a = m[1].toUpperCase() as Cardinal;
  const b = m[2].toUpperCase() as Cardinal;
  if (!CARDINALS.includes(a) || !CARDINALS.includes(b)) return null;
  return `${a}->${b}`;
}

/** Agrega matriz desde report.matriz_giros o events[].movement. */
export function buildTurnMatrix(input: {
  matriz?: unknown;
  events?: { movement?: unknown; kind?: unknown }[];
}): TurnMatrixData {
  const out: TurnMatrixData = {};
  const matriz = input.matriz;
  if (matriz && typeof matriz === "object" && !Array.isArray(matriz)) {
    for (const [k, v] of Object.entries(matriz as Record<string, unknown>)) {
      const key = parseMovement(k);
      if (!key) continue;
      const n = Number(v);
      if (Number.isFinite(n)) out[key] = (out[key] ?? 0) + n;
    }
  }
  if (Object.keys(out).length === 0 && Array.isArray(input.events)) {
    for (const ev of input.events) {
      if (ev.kind && String(ev.kind) !== "turn") continue;
      const key = parseMovement(ev.movement);
      if (!key) continue;
      out[key] = (out[key] ?? 0) + 1;
    }
  }
  return out;
}

export function countFor(matrix: TurnMatrixData, key: TurnKey): number | null {
  const v = matrix[key];
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

/** Totales saliendo de cada acceso (origen). */
export function outboundTotals(matrix: TurnMatrixData): Record<Cardinal, number> {
  const totals: Record<Cardinal, number> = { N: 0, S: 0, E: 0, O: 0 };
  for (const from of CARDINALS) {
    for (const to of CARDINALS) {
      if (from === to) continue;
      const n = countFor(matrix, `${from}->${to}`);
      if (n !== null) totals[from] += n;
    }
  }
  return totals;
}

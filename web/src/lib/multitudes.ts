/**
 * Helpers multitudes — umbrales y geometría espejo de packs/multitudes.json (RO).
 * area_m2 se lee del pack/result; no hardcodear en UI más allá de este espejo.
 */

import type { DensitySample, PeakDensity, ZoneInfo } from "./result";

/** Umbrales dens_personas_m2 del pack (propuesta; siempre rotular). */
export const DENSITY_MEDIUM = 4;
export const DENSITY_HIGH = 6;

/**
 * Espejo RO de packs/multitudes.json → zones[].
 * Usado solo cuando result.zones no trae area_m2.
 */
export const PACK_ZONES_MULTITUDES: ZoneInfo[] = [
  {
    id: "zona_1",
    polygon: [
      [0.1, 0.4],
      [0.9, 0.4],
      [0.9, 0.95],
      [0.1, 0.95],
    ],
    area_m2: 25,
  },
];

export type DensityLevel = "ok" | "medium" | "high" | "unknown";

/** Nivel según densidad (personas/m²). null → unknown (sin área). */
export function densityLevel(d: number | null | undefined): DensityLevel {
  if (d === null || d === undefined || Number.isNaN(d)) return "unknown";
  if (d >= DENSITY_HIGH) return "high";
  if (d >= DENSITY_MEDIUM) return "medium";
  return "ok";
}

/** Colores NOVA: verde <4, ámbar 4–6, rojo ≥6. Siempre acompañar con número. */
export function densityColor(d: number | null | undefined): string {
  switch (densityLevel(d)) {
    case "high":
      return "#ef4444";
    case "medium":
      return "#f59e0b";
    case "ok":
      return "#22c55e";
    default:
      return "var(--muted)";
  }
}

export function densityFill(d: number | null | undefined, alpha = 0.35): string {
  const hex = densityColor(d);
  if (!hex.startsWith("#") || hex.length < 7) return `rgba(128,128,128,${alpha})`;
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r},${g},${b},${alpha})`;
}

export function formatDensity(d: number | null | undefined): string {
  if (d === null || d === undefined || Number.isNaN(d)) return "—";
  return d.toFixed(2);
}

/** Muestras de una zona ordenadas por t_s. */
export function seriesForZone(
  density: DensitySample[],
  zone: string,
): DensitySample[] {
  return density
    .filter((s) => s.zone === zone)
    .slice()
    .sort((a, b) => a.t_s - b.t_s);
}

/** Densidad por zona más cercana a t_s. */
export function densityNearTime(
  density: DensitySample[],
  t_s: number,
): Map<string, DensitySample> {
  const byZone = new Map<string, DensitySample[]>();
  for (const s of density) {
    const list = byZone.get(s.zone) ?? [];
    list.push(s);
    byZone.set(s.zone, list);
  }
  const out = new Map<string, DensitySample>();
  for (const [zone, list] of byZone) {
    let best = list[0];
    let bestDist = Math.abs(best.t_s - t_s);
    for (const s of list) {
      const dist = Math.abs(s.t_s - t_s);
      if (dist < bestDist) {
        best = s;
        bestDist = dist;
      }
    }
    out.set(zone, best);
  }
  return out;
}

/** Une zones del result con espejo del pack (preferir result). */
export function resolveZones(resultZones: ZoneInfo[]): ZoneInfo[] {
  if (resultZones.length) {
    return resultZones.map((z) => {
      if (z.area_m2 !== null && z.area_m2 !== undefined) return z;
      const pack = PACK_ZONES_MULTITUDES.find((p) => p.id === z.id);
      return pack
        ? { ...z, area_m2: pack.area_m2, polygon: z.polygon.length ? z.polygon : pack.polygon }
        : z;
    });
  }
  return PACK_ZONES_MULTITUDES;
}

export function areaForZone(
  zones: ZoneInfo[],
  zoneId: string,
): number | null {
  const z = zones.find((x) => x.id === zoneId);
  return z?.area_m2 ?? null;
}

export function peakWithArea(
  peak: PeakDensity | null,
  zones: ZoneInfo[],
): { peak: PeakDensity; area_m2: number | null } | null {
  if (!peak) return null;
  return { peak, area_m2: areaForZone(zones, peak.zone) };
}

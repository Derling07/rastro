"use client";

import type {
  DensitySample,
  PeakDensity,
  ZoneInfo,
} from "@/lib/result";
import { zoneLabel } from "@/lib/labels";
import {
  densityColor,
  formatDensity,
  peakWithArea,
  resolveZones,
} from "@/lib/multitudes";
import { DensityChart } from "./DensityChart";

type Props = {
  density: DensitySample[];
  peak_density: PeakDensity | null;
  persons_per_zone: Record<string, number>;
  zones: ZoneInfo[];
  empty?: boolean;
  isMock?: boolean;
  sampling_mode?: string;
  onSeek?: (t_s: number) => void;
};

/**
 * Vista multitudes: pico, personas/zona, chart densidad.
 * Sin corrida → empty honesto. Área leída de pack/result (no hardcode).
 */
export function MultitudesPanel({
  density,
  peak_density,
  persons_per_zone,
  zones: rawZones,
  empty,
  isMock,
  sampling_mode,
  onSeek,
}: Props) {
  if (empty) {
    return (
      <div
        className="rounded-lg border border-dashed border-line bg-panel p-4 text-sm text-muted"
        role="status"
      >
        <p className="font-bold text-[var(--text)]">Crowd · no run yet</p>
        <p className="mt-1">
          No density result yet. After a run this panel shows the chart, the peak, and people per zone.
        </p>
      </div>
    );
  }

  const zones = resolveZones(rawZones);
  const peakInfo = peakWithArea(peak_density, zones);
  const zoneEntries = Object.entries(persons_per_zone);
  const chartZone =
    peak_density?.zone ??
    (zoneEntries[0]?.[0] ?? zones[0]?.id);

  return (
    <div className="space-y-3">
      {/* Peak card */}
      <div className="rounded-lg border border-line bg-panel p-4">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <p className="text-[11px] font-bold uppercase tracking-[0.14em] text-muted">
              Peak density
            </p>
            {peakInfo && peakInfo.peak.density_per_m2 !== null ? (
              <>
                <p
                  className="mt-1 font-display text-4xl font-bold"
                  style={{ color: densityColor(peakInfo.peak.density_per_m2) }}
                >
                  {formatDensity(peakInfo.peak.density_per_m2)}
                  <span className="ml-1 text-lg font-normal text-muted">people/m²</span>
                </p>
                <p className="mt-1 text-sm text-muted">(NOT VERIFIED)</p>
                <p className="mt-1 text-sm text-muted">
                  {zoneLabel(peakInfo.peak.zone)} · t={peakInfo.peak.t_s.toFixed(1)}s
                </p>
              </>
            ) : (
              <p className="mt-1 text-sm text-muted">No verified person count.</p>
            )}
          </div>
          {peakInfo && peakInfo.area_m2 !== null && (
            <div className="text-right">
              <p className="text-xs text-muted">
                assumed area:{" "}
                <span className="font-semibold text-[var(--text)]">
                  {peakInfo.area_m2} m²
                </span>
              </p>
              <span className="mt-1 inline-block rounded-full bg-[var(--line)] px-2 py-0.5 text-[10px] font-bold uppercase text-muted">
                assumed area
              </span>
            </div>
          )}
          {isMock && (
            <span className="rounded-full bg-[var(--line)] px-2 py-0.5 text-[10px] font-bold uppercase text-muted">
              Mock
            </span>
          )}
        </div>
        {sampling_mode && (
          <p className="mt-2 text-[11px] text-muted">
            sampling: <code>{sampling_mode}</code>
          </p>
        )}
      </div>

      {/* persons_per_zone */}
      <div className="rounded-lg border border-line bg-panel p-3">
        <h3 className="mb-2 text-sm font-bold text-muted">Density per zone</h3>
        {zoneEntries.length === 0 ? (
          <p className="text-sm text-muted">No data.</p>
        ) : (
          <ul className="space-y-1.5">
            {zoneEntries.map(([zid, n]) => {
              const z = zones.find((x) => x.id === zid);
              const area = z?.area_m2 ?? null;
              const dens = area && area > 0 ? n / area : null;
              return (
                <li
                  key={zid}
                  className="flex items-baseline justify-between gap-2 text-sm"
                >
                  <span className="text-pack">{zoneLabel(zid)}</span>
                  <span>
                    {dens !== null ? (
                      <span className="text-xs" style={{ color: densityColor(dens) }}>
                        {formatDensity(dens)}/m² (NOT VERIFIED)
                      </span>
                    ) : (
                      <span className="text-xs text-muted">no area</span>
                    )}
                  </span>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      <DensityChart
        density={density}
        zone={chartZone}
        empty={!density.length}
        onSeek={onSeek}
      />
    </div>
  );
}

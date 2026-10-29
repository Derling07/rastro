"use client";

import type {
  DensitySample,
  PeakDensity,
  ZoneInfo,
} from "@/lib/result";
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
        <p className="font-bold text-[var(--text)]">Multitudes · sin corrida</p>
        <p className="mt-1">
          Aún no hay un result.json de densidad. El panel mostrará chart,
          pico y personas/zona cuando exista una corrida.
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
              Pico de densidad
            </p>
            {peakInfo ? (
              <>
                <p
                  className="mt-1 font-display text-4xl font-bold"
                  style={{
                    color:
                      peakInfo.peak.density_per_m2 !== null
                        ? densityColor(peakInfo.peak.density_per_m2)
                        : "var(--pack)",
                  }}
                >
                  {peakInfo.peak.density_per_m2 !== null
                    ? `${formatDensity(peakInfo.peak.density_per_m2)}`
                    : peakInfo.peak.persons}
                  <span className="ml-1 text-lg font-normal text-muted">
                    {peakInfo.peak.density_per_m2 !== null
                      ? "pers/m²"
                      : "pers"}
                  </span>
                </p>
                <p className="mt-1 text-sm text-muted">
                  {peakInfo.peak.zone} · t={peakInfo.peak.t_s.toFixed(1)}s ·{" "}
                  {peakInfo.peak.persons} personas
                </p>
              </>
            ) : (
              <p className="mt-1 text-sm text-muted">Sin pico reportado.</p>
            )}
          </div>
          {peakInfo && peakInfo.area_m2 !== null && (
            <div className="text-right">
              <p className="text-xs text-muted">
                área supuesta:{" "}
                <span className="font-semibold text-[var(--text)]">
                  {peakInfo.area_m2} m²
                </span>
              </p>
              <span className="mt-1 inline-block rounded-full bg-[var(--line)] px-2 py-0.5 text-[10px] font-bold uppercase text-muted">
                ejemplo
              </span>
            </div>
          )}
          {isMock && (
            <span className="rounded-full bg-[var(--line)] px-2 py-0.5 text-[10px] font-bold uppercase text-muted">
              ejemplo
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
        <h3 className="mb-2 text-sm font-bold text-muted">Personas por zona</h3>
        {zoneEntries.length === 0 ? (
          <p className="text-sm text-muted">Sin datos.</p>
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
                  <span className="text-pack">{zid}</span>
                  <span>
                    <span className="font-display text-lg font-bold">{n}</span>
                    {dens !== null ? (
                      <span
                        className="ml-2 text-xs"
                        style={{ color: densityColor(dens) }}
                      >
                        {formatDensity(dens)}/m²
                      </span>
                    ) : (
                      <span className="ml-2 text-xs text-muted">
                        sin área → solo personas
                      </span>
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

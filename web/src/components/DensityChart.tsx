"use client";

import { useMemo } from "react";
import type { DensitySample } from "@/lib/result";
import { zoneLabel } from "@/lib/labels";
import {
  DENSITY_HIGH,
  densityColor,
  seriesForZone,
} from "@/lib/multitudes";

type Props = {
  density: DensitySample[];
  zone?: string;
  empty?: boolean;
  onSeek?: (t_s: number) => void;
};

/**
 * Density over time. Two states: below 6 people/m², and from 6 (crush risk).
 */
export function DensityChart({ density, zone, empty, onSeek }: Props) {
  const series = useMemo(() => {
    if (!density.length) return [];
    if (zone) return seriesForZone(density, zone);
    // Si no hay zona: agregar por t_s (suma persons / promedio dens)
    const byT = new Map<number, { persons: number; densSum: number; n: number }>();
    for (const s of density) {
      const cur = byT.get(s.t_s) ?? { persons: 0, densSum: 0, n: 0 };
      cur.persons += s.persons;
      if (s.density_per_m2 !== null) {
        cur.densSum += s.density_per_m2;
        cur.n += 1;
      }
      byT.set(s.t_s, cur);
    }
    return Array.from(byT.entries())
      .sort((a, b) => a[0] - b[0])
      .map(([t_s, v]) => ({
        t_s,
        zone: zone ?? "all",
        persons: v.persons,
        density_per_m2: v.n ? v.densSum / v.n : null,
      }));
  }, [density, zone]);

  if (empty || !series.length) {
    return (
      <p className="text-sm text-muted" role="status">
        No density series.
      </p>
    );
  }

  const W = 480;
  const H = 160;
  const padL = 36;
  const padR = 12;
  const padT = 16;
  const padB = 28;
  const plotW = W - padL - padR;
  const plotH = H - padT - padB;

  const tMin = series[0].t_s;
  const tMax = Math.max(series[series.length - 1].t_s, tMin + 1);
  const densVals = series
    .map((s) => s.density_per_m2)
    .filter((d): d is number => d !== null);
  const hasDens = densVals.length > 0;
  if (!hasDens) {
    return (
      <p className="text-sm text-muted" role="status">
        No density series.
      </p>
    );
  }
  const yMax = Math.max(DENSITY_HIGH * 1.25, ...densVals);

  const xOf = (t: number) => padL + ((t - tMin) / (tMax - tMin)) * plotW;
  const yOf = (v: number) => padT + plotH - (v / yMax) * plotH;

  const points = series
    .map((s) => `${xOf(s.t_s).toFixed(1)},${yOf(s.density_per_m2 ?? 0).toFixed(1)}`)
    .join(" ");

  const yHigh = yOf(DENSITY_HIGH);

  return (
    <div className="rounded-lg border border-line bg-panel p-3">
      <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-sm font-bold text-muted">
          Density over time
          {zone ? (
            <span className="ml-1 font-normal text-pack">{zoneLabel(zone)}</span>
          ) : null}
        </h3>
        <p className="text-[10px] uppercase tracking-wide text-muted">
          people/m²
        </p>
      </div>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="h-auto w-full"
        role="img"
        aria-label="Density over time"
      >
        <line
          x1={padL}
          x2={W - padR}
          y1={yHigh}
          y2={yHigh}
          stroke="#ef4444"
          strokeDasharray="2 2"
          strokeWidth={1}
        />
        <text
          x={W - padR}
          y={yHigh - 3}
          textAnchor="end"
          fill="#ef4444"
          fontSize={9}
        >
          6 crush risk
        </text>
        <polyline
          fill="none"
          stroke="var(--pack)"
          strokeWidth={2}
          points={points}
        />
        {series.map((s) => {
          const v = s.density_per_m2;
          const cx = xOf(s.t_s);
          const cy = yOf(v ?? 0);
          return (
            <g key={`${s.zone}-${s.t_s}`}>
              <circle
                cx={cx}
                cy={cy}
                r={3.5}
                fill={densityColor(v)}
                className={onSeek ? "cursor-pointer" : undefined}
                onClick={() => onSeek?.(s.t_s)}
              >
                <title>{`t=${s.t_s.toFixed(1)}s · ${v !== null && v !== undefined ? `${v.toFixed(2)}/m²` : "no density"}`}</title>
              </circle>
            </g>
          );
        })}
        <text x={padL} y={H - 8} fill="var(--muted)" fontSize={9}>
          {tMin.toFixed(0)}s
        </text>
        <text
          x={W - padR}
          y={H - 8}
          textAnchor="end"
          fill="var(--muted)"
          fontSize={9}
        >
          {tMax.toFixed(0)}s
        </text>
      </svg>
    </div>
  );
}

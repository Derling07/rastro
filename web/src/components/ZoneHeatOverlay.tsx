"use client";

import { useMemo } from "react";
import type { DensitySample, ZoneInfo } from "@/lib/result";
import {
  densityColor,
  densityFill,
  densityNearTime,
  formatDensity,
} from "@/lib/multitudes";

type Props = {
  zones: ZoneInfo[];
  density: DensitySample[];
  /** currentTime del video (s). */
  t_s: number;
  /** Dimensiones del viewBox (px del video o 0–1 normalizado). */
  width?: number;
  height?: number;
};

/**
 * Heat overlay por zona sincronizado al tiempo del video (muestra más cercana).
 * Two states only: green below 6 people/m², red from 6. No person count.
 */
export function ZoneHeatOverlay({
  zones,
  density,
  t_s,
  width = 1,
  height = 1,
}: Props) {
  const near = useMemo(() => densityNearTime(density, t_s), [density, t_s]);

  if (!zones.length) return null;

  const norm = width === 1 && height === 1;

  return (
    <svg
      className="pointer-events-none absolute inset-0 h-full w-full"
      viewBox={norm ? "0 0 1 1" : `0 0 ${width} ${height}`}
      preserveAspectRatio="none"
      aria-hidden
    >
      {zones.map((z) => {
        const sample = near.get(z.id);
        const dens = sample?.density_per_m2 ?? null;
        const hasArea = z.area_m2 !== null && z.area_m2 !== undefined;
        const showDensity = hasArea && dens !== null;
        const pts = z.polygon
          .map(([x, y]) =>
            norm
              ? `${x},${y}`
              : `${x * width},${y * height}`,
          )
          .join(" ");
        const cx =
          z.polygon.reduce((s, p) => s + p[0], 0) / Math.max(1, z.polygon.length);
        const cy =
          z.polygon.reduce((s, p) => s + p[1], 0) / Math.max(1, z.polygon.length);
        const labelX = norm ? cx : cx * width;
        const labelY = norm ? cy : cy * height;
        const fill = showDensity
          ? densityFill(dens, 0.4)
          : "rgba(92,200,224,0.2)";
        const stroke = showDensity ? densityColor(dens) : "var(--pack)";
        const label = showDensity ? `${formatDensity(dens)}/m²` : "—";

        return (
          <g key={z.id}>
            <polygon
              points={pts}
              fill={fill}
              stroke={stroke}
              strokeWidth={norm ? 0.004 : 2}
            />
            <text
              x={labelX}
              y={labelY}
              textAnchor="middle"
              dominantBaseline="middle"
              fill="#fff"
              fontSize={norm ? 0.045 : 16}
              fontFamily="var(--font-display)"
              fontWeight={700}
              style={{ paintOrder: "stroke", stroke: "#000", strokeWidth: norm ? 0.006 : 3 }}
            >
              {label}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

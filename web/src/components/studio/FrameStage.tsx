"use client";

import { useEffect, useMemo, useState } from "react";
import { colorForTrack, type Frame } from "@/lib/result";

type Props = {
  frames: Frame[];
  time: number;
  onTime: (t: number) => void;
  isMock?: boolean;
};

function reducedMotion(): boolean {
  return typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

export function FrameStage({ frames, time, onTime, isMock }: Props) {
  const [playing, setPlaying] = useState(false);
  const ordered = useMemo(
    () => frames.filter((frame) => frame.objects.length > 0).sort((a, b) => a.t_s - b.t_s),
    [frames],
  );
  const size = useMemo(() => {
    let w = 960;
    let h = 540;
    for (const frame of ordered) {
      for (const object of frame.objects) {
        w = Math.max(w, object.bbox[2]);
        h = Math.max(h, object.bbox[3]);
      }
    }
    return { w, h };
  }, [ordered]);
  const active =
    ordered.reduce<Frame | null>((best, frame) => {
      if (frame.t_s <= time + 0.001) return frame;
      return best;
    }, ordered[0] ?? null) ?? null;

  useEffect(() => {
    if (!playing || ordered.length < 2) return;
    const id = window.setInterval(() => {
      const next = ordered.find((frame) => frame.t_s > time + 0.001) ?? ordered[0];
      onTime(next.t_s);
    }, 140);
    return () => window.clearInterval(id);
  }, [playing, ordered, time, onTime]);

  if (!active) {
    return (
      <div className="flex aspect-video items-center justify-center rounded-lg border border-dashed border-line bg-panel text-sm text-muted">
        No frame boxes in this result.
      </div>
    );
  }

  const end = ordered[ordered.length - 1]?.t_s ?? 0;

  return (
    <div className="space-y-2">
      <div className="relative overflow-hidden rounded-lg border border-line bg-black">
        <svg viewBox={`0 0 ${size.w} ${size.h}`} className="block aspect-video w-full" role="img" aria-label="Tracked boxes on the current frame">
          <rect width={size.w} height={size.h} fill="#0b100e" />
          {active.objects.map((object) => {
            const color = colorForTrack(object.track_id);
            const x = object.bbox[0];
            const y = object.bbox[1];
            const w = Math.max(0, object.bbox[2] - object.bbox[0]);
            const h = Math.max(0, object.bbox[3] - object.bbox[1]);
            return (
              <g key={object.track_id + String(object.bbox)}>
                <rect x={x} y={y} width={w} height={h} fill={color} fillOpacity={0.18} stroke={color} strokeWidth={Math.max(2, size.w / 400)} />
                <text x={x + 4} y={Math.max(18, y - 6)} fill={color} fontSize={Math.max(14, size.w / 70)} fontFamily="var(--font-display)">
                  {object.track_id}
                </text>
              </g>
            );
          })}
        </svg>
        {isMock && (
          <span className="absolute left-2 top-2 rounded-full bg-[var(--line)] px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-muted">
            Mock
          </span>
        )}
        <span className="absolute bottom-2 right-2 rounded bg-black/70 px-2 py-0.5 font-display text-sm">
          {active.t_s.toFixed(1)}s
        </span>
      </div>
      <div className="flex items-center gap-3">
        <button
          type="button"
          className="rounded-full border border-line px-3 py-1 text-sm hover:border-pack"
          onClick={() => {
            if (reducedMotion()) return;
            setPlaying((value) => !value);
          }}
          title={reducedMotion() ? "Playback is off because reduced motion is on. Use the slider." : "Play the tracked frames"}
        >
          {playing ? "Pause" : "Play"}
        </button>
        <input
          className="w-full accent-[var(--pack)]"
          type="range"
          min={0}
          max={end}
          step={0.1}
          value={Math.min(time, end)}
          aria-label="Frame time"
          onChange={(event) => {
            setPlaying(false);
            onTime(Number(event.target.value));
          }}
        />
      </div>
      <p className="text-xs text-muted">Boxes are the tracker’s frames. The id stays with the individual after a re-entry.</p>
    </div>
  );
}

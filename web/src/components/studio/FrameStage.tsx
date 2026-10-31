"use client";

import { useEffect, useMemo, useState } from "react";
import { Viewfinder } from "@/components/notebook/Viewfinder";
import { colorForTrack, type Frame } from "@/lib/result";

type Props = {
  frames: Frame[];
  time: number;
  onTime: (t: number) => void;
  isMock?: boolean;
};

export function FrameStage({ frames, time, onTime, isMock }: Props) {
  const [playing, setPlaying] = useState(false);
  const [reduceMotion, setReduceMotion] = useState(false);
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
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    const apply = () => setReduceMotion(query.matches);
    apply();
    query.addEventListener("change", apply);
    return () => query.removeEventListener("change", apply);
  }, []);

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
      <Viewfinder label={isMock ? "Simulated camera · mock" : "Simulated camera"}>
        <div className="flex aspect-video items-center justify-center px-6 text-center text-sm text-[#d7e0d8]">
          No frame boxes in this result.
        </div>
      </Viewfinder>
    );
  }

  const end = ordered[ordered.length - 1]?.t_s ?? 0;

  return (
    <div className="space-y-2">
      <Viewfinder label={isMock ? "Simulated camera · mock" : "Simulated camera"}>
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
        <span className="absolute bottom-2 right-2 bg-black/70 px-2 py-0.5 font-facts text-sm text-[#f3f6f1]">
          {active.t_s.toFixed(1)}s
        </span>
      </Viewfinder>
      <div className="flex items-center gap-3">
        <button
          type="button"
          className="rounded-full border border-line px-3 py-1 text-sm hover:border-pack"
          onClick={() => {
            if (reduceMotion) return;
            setPlaying((value) => !value);
          }}
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
      {reduceMotion && (
        <p className="text-sm text-muted">
          Playback stays off while reduced motion is on. Use the slider to change frames.
        </p>
      )}
      <p className="text-xs text-muted">Boxes are the tracker’s frames. The id stays with the individual after a re-entry.</p>
    </div>
  );
}

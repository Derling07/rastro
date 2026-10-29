"use client";

import {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  colorForTrack,
  objectsNearTime,
  type DensitySample,
  type Frame,
  type Track,
  type ZoneInfo,
} from "@/lib/result";
import { ZoneHeatOverlay } from "./ZoneHeatOverlay";

export type AnnotatedPlayerHandle = {
  seek: (t_s: number) => void;
  getCurrentTime: () => number;
};

type Props = {
  src: string | null | undefined;
  poster?: string | null;
  frames: Frame[];
  tracks: Track[];
  isMock?: boolean;
  empty?: boolean;
  onTimeUpdate?: (t_s: number) => void;
  /** Overlay de densidad multitudes (norm 0–1). */
  heatZones?: ZoneInfo[];
  heatDensity?: DensitySample[];
};

/**
 * Reproduce artifacts.annotated_video (máscaras ya pintadas).
 * NO dibuja cajas por defecto. frames[].bbox solo al hover/tap de un track_id.
 */
export const AnnotatedPlayer = forwardRef<AnnotatedPlayerHandle, Props>(
  function AnnotatedPlayer(
    { src, poster, frames, tracks, isMock, empty, onTimeUpdate, heatZones, heatDensity },
    ref,
  ) {
    const videoRef = useRef<HTMLVideoElement>(null);
    const wrapRef = useRef<HTMLDivElement>(null);
    const [highlightId, setHighlightId] = useState<string | null>(null);
    const [t, setT] = useState(0);
    const [dims, setDims] = useState({ w: 960, h: 540 });

    useImperativeHandle(ref, () => ({
      seek(t_s: number) {
        const v = videoRef.current;
        if (!v) return;
        v.currentTime = Math.max(0, t_s);
        void v.play().catch(() => undefined);
      },
      getCurrentTime() {
        return videoRef.current?.currentTime ?? 0;
      },
    }));

    useEffect(() => {
      const v = videoRef.current;
      if (!v) return;
      const onTime = () => {
        const ct = v.currentTime;
        setT(ct);
        onTimeUpdate?.(ct);
      };
      const onMeta = () => {
        if (v.videoWidth && v.videoHeight) {
          setDims({ w: v.videoWidth, h: v.videoHeight });
        }
      };
      v.addEventListener("timeupdate", onTime);
      v.addEventListener("loadedmetadata", onMeta);
      return () => {
        v.removeEventListener("timeupdate", onTime);
        v.removeEventListener("loadedmetadata", onMeta);
      };
    }, [src, onTimeUpdate]);

    const highlightObj = useMemo(() => {
      if (!highlightId) return null;
      const objs = objectsNearTime(frames, t);
      return objs.find((o) => o.track_id === highlightId) ?? null;
    }, [highlightId, frames, t]);

    const onLeave = useCallback(() => setHighlightId(null), []);

    if (empty || !src) {
      return (
        <div
          className="flex aspect-video items-center justify-center rounded-lg border border-dashed border-line bg-panel text-sm text-muted"
          role="status"
        >
          Sin video anotado para este paquete
        </div>
      );
    }

    return (
      <div className="space-y-2">
        <div
          ref={wrapRef}
          className="relative overflow-hidden rounded-lg border border-line bg-black"
        >
          <video
            ref={videoRef}
            className="block w-full"
            src={src}
            poster={poster ?? undefined}
            controls
            playsInline
            preload="metadata"
            aria-label="Video anotado con máscaras Rastro"
          />
          {/* Overlay: solo el bbox del track resaltado */}
          {highlightObj && (
            <svg
              className="pointer-events-none absolute inset-0 h-full w-full"
              viewBox={`0 0 ${dims.w} ${dims.h}`}
              preserveAspectRatio="xMidYMid meet"
              aria-hidden
            >
              <rect
                x={highlightObj.bbox[0]}
                y={highlightObj.bbox[1]}
                width={Math.max(0, highlightObj.bbox[2] - highlightObj.bbox[0])}
                height={Math.max(0, highlightObj.bbox[3] - highlightObj.bbox[1])}
                fill="none"
                stroke={colorForTrack(highlightObj.track_id)}
                strokeWidth={3}
                vectorEffect="non-scaling-stroke"
              />
              <text
                x={highlightObj.bbox[0]}
                y={Math.max(14, highlightObj.bbox[1] - 6)}
                fill={colorForTrack(highlightObj.track_id)}
                fontSize={14}
                fontFamily="var(--font-display)"
              >
                {highlightObj.track_id}
              </text>
            </svg>
          )}
          {heatZones && heatZones.length > 0 && heatDensity && (
            <ZoneHeatOverlay
              zones={heatZones}
              density={heatDensity}
              t_s={t}
            />
          )}
          {isMock && (
            <span className="absolute left-2 top-2 rounded-full bg-[var(--line)] px-2 py-0.5 text-[10px] font-bold uppercase text-muted">
              ejemplo
            </span>
          )}
        </div>

        {tracks.length > 0 && (
          <div
            className="flex flex-wrap gap-1.5"
            role="group"
            aria-label="Tracks — hover o toque para resaltar caja"
            onMouseLeave={onLeave}
          >
            {tracks.map((tr) => {
              const active = highlightId === tr.track_id;
              const color = colorForTrack(tr.track_id);
              return (
                <button
                  key={tr.track_id}
                  type="button"
                  className={
                    "rounded-full border px-2.5 py-1 text-xs transition-colors " +
                    (active
                      ? "border-transparent text-ink"
                      : "border-line text-muted hover:text-[var(--text)]")
                  }
                  style={
                    active
                      ? { background: color }
                      : { borderColor: color, color }
                  }
                  onMouseEnter={() => setHighlightId(tr.track_id)}
                  onFocus={() => setHighlightId(tr.track_id)}
                  onBlur={onLeave}
                  onClick={() =>
                    setHighlightId((cur) =>
                      cur === tr.track_id ? null : tr.track_id,
                    )
                  }
                  aria-pressed={active}
                  title={`${tr.class} · frames ${tr.start_frame}–${tr.end_frame}`}
                >
                  {tr.track_id}
                  <span className="ml-1 opacity-70">{tr.class}</span>
                </button>
              );
            })}
          </div>
        )}
        <p className="text-[11px] text-muted">
          Máscaras en el video. Las cajas (frames[].bbox) solo al pasar el
          cursor o tocar un track.
        </p>
      </div>
    );
  },
);

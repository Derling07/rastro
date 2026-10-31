"use client";

import { clipLabel } from "@/lib/labels";
import type { Alert } from "@/lib/result";

type Props = {
  alerts: Alert[];
  onSeek?: (t: number) => void;
};

function severityLabel(s: string): string {
  const k = s.toLowerCase();
  if (k === "alta" || k === "high") return "High";
  if (k === "media" || k === "medium") return "Medium";
  if (k === "critica" || k === "crítica" || k === "critical") return "Critical";
  if (k === "info") return "Info";
  return s;
}

function severityColor(s: string): string {
  const k = s.toLowerCase();
  if (k === "alta" || k === "high" || k === "critica" || k === "crítica" || k === "critical") {
    return "var(--alta)";
  }
  if (k === "media" || k === "medium") return "var(--media)";
  return "var(--pack)";
}

function fmtTime(t: number): string {
  const m = Math.floor(t / 60);
  const s = Math.floor(t % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export function AlertList({ alerts, onSeek }: Props) {
  if (!alerts.length) {
    return <p className="text-sm text-muted">No alerts.</p>;
  }
  return (
    <ul className="space-y-2">
      {alerts.map((a) => (
        <li key={a.id + String(a.t_s)}>
          <button
            type="button"
            className="w-full rounded border border-line bg-panel px-3 py-2 text-left hover:border-pack"
            style={{
              borderLeftWidth: 3,
              borderLeftColor: severityColor(a.severity),
            }}
            onClick={() => onSeek?.(a.t_s)}
          >
            <span className="text-[11px] font-bold uppercase text-muted">
              {severityLabel(a.severity)}
              <span className="ml-2 text-pack">{fmtTime(a.t_s)}</span>
            </span>
            <p className="text-sm">{clipLabel(a.message)}</p>
          </button>
        </li>
      ))}
    </ul>
  );
}

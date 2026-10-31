"use client";

import { useEffect, useState } from "react";

type PeakPayload = {
  module: "crowd" | "traffic";
  badge: string;
  real_runs: number;
  needed_runs: number;
  not_verified: boolean;
  unit: string;
  weekdays: string[];
  heatmap: number[][];
  series: number[];
};

export function PeakHours() {
  const [module, setModule] = useState<"crowd" | "traffic">("crowd");
  const [data, setData] = useState<PeakPayload | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancel = false;
    fetch(`/engine/api/peaks?module=${module}`, { cache: "no-store" })
      .then(async (res) => {
        if (!res.ok) throw new Error("Peak hours are unavailable.");
        return (await res.json()) as PeakPayload;
      })
      .then((body) => {
        if (!cancel) setData(body);
      })
      .catch((err: Error) => {
        if (!cancel) setError(err.message);
      });
    return () => {
      cancel = true;
    };
  }, [module]);

  const maxCell = Math.max(1, ...(data?.heatmap.flat() ?? [1]));
  const maxBar = Math.max(1, ...(data?.series ?? [1]));

  return (
    <section className="rounded-lg border border-line bg-panel p-4" aria-labelledby="peaks-h">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="peaks-h" className="font-display text-2xl">
          Peak hours
        </h2>
        <div className="flex gap-2" role="group" aria-label="Peak hour sector">
          {(["crowd", "traffic"] as const).map((item) => (
            <button
              key={item}
              type="button"
              className={
                "rounded-full border px-3 py-1 text-sm " +
                (module === item ? "chip border-pack" : "border border-line text-muted")
              }
              aria-pressed={module === item}
              onClick={() => setModule(item)}
            >
              {item === "crowd" ? "Crowd" : "Traffic"}
            </button>
          ))}
        </div>
      </div>
      <p className="mt-1 text-sm text-muted">
        Counts added up by hour and weekday. The chart uses example numbers until this server has{" "}
        {data?.needed_runs ?? 7} real runs, then it switches to your data.
        {module === "traffic"
          ? " Exports in a standard format compatible with Waze for Cities. This app does not send the feed. Traffic counts are not verified."
          : ""}
      </p>
      {error && (
        <p className="mt-2 text-sm text-alta" role="alert">
          {error}
        </p>
      )}
      {data && (
        <>
          <div className="mt-3 flex flex-wrap gap-2">
            <span className="rounded-full border border-pack px-2 py-0.5 text-[11px] font-bold uppercase tracking-wide text-pack">
              {data.badge}
            </span>
            {data.not_verified && (
              <span className="rounded-full border border-alta px-2 py-0.5 text-[11px] font-bold uppercase tracking-wide text-alta">
                Not verified
              </span>
            )}
            <span className="text-xs text-muted">
              {data.real_runs} real run{data.real_runs === 1 ? "" : "s"} · {data.unit}
            </span>
          </div>
          <h3 className="mt-4 text-xs font-bold uppercase tracking-[0.16em] text-muted">Hour × weekday</h3>
          <div className="mt-2 overflow-x-auto" tabIndex={0} role="region" aria-label="Peak hours table">
            <table className="border-collapse text-[10px]">
              <thead>
                <tr>
                  <th className="p-1 text-left text-muted" />
                  {data.series.map((_, hour) => (
                    <th key={hour} className="px-0.5 font-normal text-muted">
                      {hour % 3 === 0 ? hour : ""}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.heatmap.map((row, day) => (
                  <tr key={data.weekdays[day]}>
                    <th className="pr-2 text-left font-normal text-muted">{data.weekdays[day]}</th>
                    {row.map((value, hour) => (
                      <td key={hour} className="p-0.5">
                        <span
                          className="block h-4 w-4 rounded-sm"
                          style={{ background: `rgba(20, 36, 28, ${0.12 + (value / maxCell) * 0.88})` }}
                          title={`${data.weekdays[day]} ${hour}:00 · ${value} ${data.unit}`}
                        />
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <h3 className="mt-4 text-xs font-bold uppercase tracking-[0.16em] text-muted">By hour</h3>
          <div className="mt-2 flex h-24 items-end gap-1" aria-label="Counts by hour">
            {data.series.map((value, hour) => (
              <div key={hour} className="flex flex-1 flex-col items-center justify-end">
                <span
                  className="block w-full bg-[var(--ink)]"
                  style={{ height: `${Math.max(4, (value / maxBar) * 96)}px` }}
                  title={`${hour}:00 · ${value} ${data.unit}`}
                />
              </div>
            ))}
          </div>
        </>
      )}
    </section>
  );
}

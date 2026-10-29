"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState, type MouseEvent } from "react";
import { PeakHours } from "@/components/PeakHours";

type Point = [number, number];

type BoxRow = { class: string; bbox: number[]; track_id?: string };

type AlertRow = {
  id: string;
  kind: string;
  severity: string;
  message: string;
  label?: string;
  t_s: number;
  status: string;
  zone?: string;
  class?: string;
  snapshot?: { t_s: number; blurred: boolean; boxes: BoxRow[] };
  camera_id?: string;
  camera_name?: string;
  verification?: string;
};

type Frame = { frame: number; t_s: number; objects: { track_id: string; class: string; bbox: number[] }[] };

type Camera = {
  id: string;
  name: string;
  site: string;
  module: string;
  simulated: boolean;
  verified: boolean;
  verification: string;
  verification_note: string;
  headline: string;
  duration_s: number;
  video_url?: string | null;
  frame_width?: number;
  frame_height?: number;
  credit?: { title?: string; author?: string; license?: string; license_url?: string; source_url?: string };
  zone: { id: string; polygon: Point[] } | null;
  zone_editable: boolean;
  frames: Frame[];
  alerts: AlertRow[];
  actions: string[];
  sustain_s: number | null;
};

type CameraCard = {
  id: string;
  name: string;
  site: string;
  verification: string;
  open_alerts: number;
  headline: string;
};

const SIZE = 1000;

export function Cameras() {
  const [cards, setCards] = useState<CameraCard[]>([]);
  const [inbox, setInbox] = useState<AlertRow[]>([]);
  const [camera, setCamera] = useState<Camera | null>(null);
  const [selected, setSelected] = useState("gray-fox");
  const [time, setTime] = useState(0);
  const [playing, setPlaying] = useState(true);
  const [draft, setDraft] = useState<Point[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [reduceMotion, setReduceMotion] = useState(false);

  const loadList = useCallback(async () => {
    const res = await fetch("/engine/api/cameras", { cache: "no-store" });
    if (!res.ok) throw new Error("Can't reach the analysis server, try again");
    const body = (await res.json()) as { cameras: CameraCard[]; inbox: AlertRow[] };
    setCards(body.cameras);
    setInbox(body.inbox);
  }, []);

  const loadCamera = useCallback(async (id: string) => {
    const res = await fetch(`/engine/api/cameras/${id}`, { cache: "no-store" });
    if (!res.ok) throw new Error("That camera is not on this server.");
    const body = (await res.json()) as { camera: Camera };
    setCamera(body.camera);
    setDraft([]);
  }, []);

  useEffect(() => {
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    const apply = () => {
      setReduceMotion(query.matches);
      if (query.matches) setPlaying(false);
    };
    apply();
    query.addEventListener("change", apply);
    return () => query.removeEventListener("change", apply);
  }, []);

  useEffect(() => {
    loadList().catch((err: Error) => setError(err.message));
  }, [loadList]);

  useEffect(() => {
    loadCamera(selected).catch((err: Error) => setError(err.message));
    setTime(0);
  }, [loadCamera, selected]);

  useEffect(() => {
    if (!playing || !camera || reduceMotion) return;
    const end = Math.max(camera.duration_s, 0.5);
    const id = window.setInterval(() => {
      setTime((current) => (current + 0.25 >= end ? 0 : current + 0.25));
    }, 250);
    return () => window.clearInterval(id);
  }, [playing, camera, reduceMotion]);

  const frame = useMemo(() => {
    const frames = camera?.frames ?? [];
    return frames.reduce<Frame | null>((best, row) => (row.t_s <= time + 0.001 ? row : best), frames[0] ?? null);
  }, [camera, time]);

  const liveAlert = camera?.alerts.find((alert) => Math.abs(alert.t_s - time) < 0.6 && alert.status === "open");

  async function applyZone() {
    if (!camera || draft.length < 3) return;
    setError(null);
    const res = await fetch(`/engine/api/cameras/${camera.id}/zone`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ polygon: draft }),
    });
    const body = (await res.json()) as { camera?: Camera; error?: string };
    if (!res.ok || !body.camera) {
      setError(body.error || "Could not apply the pen.");
      return;
    }
    setCamera(body.camera);
    setDraft([]);
    await loadList();
  }

  async function review(alertId: string, cameraId: string) {
    setError(null);
    const res = await fetch(`/engine/api/cameras/${cameraId}/alerts/${encodeURIComponent(alertId)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "review" }),
    });
    const body = (await res.json()) as { camera?: Camera; error?: string };
    if (!res.ok) {
      setError(body.error || "Could not mark this reviewed.");
      return;
    }
    if (body.camera && body.camera.id === selected) setCamera(body.camera);
    await loadList();
  }

  async function act(alertId: string, action: "confirm" | "dismiss", cameraId = camera?.id) {
    if (!cameraId) return;
    setError(null);
    const res = await fetch(`/engine/api/cameras/${cameraId}/alerts/${encodeURIComponent(alertId)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action }),
    });
    const body = (await res.json()) as { camera?: Camera; error?: string };
    if (!res.ok) {
      setError(body.error || "Could not update the alert.");
      return;
    }
    if (body.camera && body.camera.id === selected) setCamera(body.camera);
    await loadList();
  }

  function onStageClick(event: MouseEvent<SVGSVGElement>) {
    if (!camera?.zone_editable) return;
    const svg = event.currentTarget;
    const point = svg.createSVGPoint();
    point.x = event.clientX;
    point.y = event.clientY;
    const ctm = svg.getScreenCTM();
    if (!ctm) return;
    const mapped = point.matrixTransform(ctm.inverse());
    const width = camera.frame_width || SIZE;
    const height = camera.frame_height || SIZE;
    const nx = Math.min(1, Math.max(0, mapped.x / width));
    const ny = Math.min(1, Math.max(0, mapped.y / height));
    setDraft((current) => [...current, [Number(nx.toFixed(3)), Number(ny.toFixed(3))]]);
  }

  const polygon = draft.length >= 3 ? draft : camera?.zone?.polygon ?? [];

  return (
    <div className="mx-auto max-w-6xl px-4 py-5 sm:px-6">
      <header className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-baseline gap-4">
            <h1 className="font-display text-4xl font-bold tracking-tight">Rastro</h1>
            <Link href="/" className="text-sm text-muted underline">
              Analyze a clip
            </Link>
          </div>
          <p className="mt-1 max-w-xl text-sm text-muted">
            Rastro counts each individual once — and uses that to alert what matters.
          </p>
        </div>
      </header>

      <div className="mb-4 rounded-lg border border-line bg-panel p-4">
        <p className="font-display text-2xl">Cameras</p>
        <p className="mt-1 text-sm text-muted">
          Each camera plays a real clip under an open license. It is not a live stream. Alerts are tied to the second they happened.
        </p>
      </div>

      {error && (
        <p className="mb-4 rounded-lg border border-alta/50 bg-panel p-3 text-sm" role="alert">
          {error}
        </p>
      )}

      <div className="grid gap-6 lg:grid-cols-[240px_minmax(0,1fr)]">
        <aside>
          <h2 className="text-xs font-bold uppercase tracking-[0.16em] text-muted">Sites</h2>
          <ul className="mt-2 space-y-2">
            {cards.map((card) => (
              <li key={card.id}>
                <button
                  type="button"
                  className={
                    "w-full rounded-lg border px-3 py-2 text-left " +
                    (card.id === selected ? "border-pack bg-panel" : "border-line hover:border-pack")
                  }
                  aria-pressed={card.id === selected}
                  onClick={() => setSelected(card.id)}
                >
                  <span className="block text-xs uppercase tracking-wide text-muted">{card.site}</span>
                  <span className="block font-display text-xl">{card.name}</span>
                  <span className="text-xs text-muted">
                    {card.verification}
                    {card.open_alerts ? ` · ${card.open_alerts} open` : ""}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </aside>

        <div className="space-y-4">
          {camera && (
            <>
              <div className="flex flex-wrap items-center gap-2">
                <span className="rounded-full border border-pack px-2 py-0.5 text-[11px] font-bold uppercase tracking-wide text-pack">
                  {camera.video_url ? "Recorded clip" : "Stored run"}
                </span>
                {!camera.verified && (
                  <span className="rounded-full border border-alta px-2 py-0.5 text-[11px] font-bold uppercase tracking-wide text-alta">
                    Not verified
                  </span>
                )}
              </div>
              <p className="font-display text-3xl leading-tight">{camera.headline}</p>
              <p className="text-sm text-muted">{camera.verification_note}</p>

              <div className="rounded-lg border border-line bg-black p-2">
                <div className="relative">
                {camera.video_url && (
                  <video
                    key={camera.id}
                    className="block aspect-video w-full bg-black"
                    src={camera.video_url}
                    muted
                    playsInline
                    loop
                    autoPlay={!reduceMotion}
                    onTimeUpdate={(event) => setTime(event.currentTarget.currentTime)}
                  />
                )}
                <svg
                  viewBox={`0 0 ${camera.frame_width || SIZE} ${camera.frame_height || SIZE}`}
                  className={camera.video_url ? "absolute inset-0 h-full w-full" : "block aspect-video w-full"}
                  role="img"
                  aria-label="Recorded camera frame"
                  onClick={onStageClick}
                >
                  {!camera.video_url && <rect width={SIZE} height={SIZE} fill="#0b100e" />}
                  {polygon.length >= 2 && (
                    <polygon
                      points={polygon.map(([x, y]) => `${x * (camera.frame_width || SIZE)},${y * (camera.frame_height || SIZE)}`).join(" ")}
                      fill="#5cc8e0"
                      fillOpacity={0.12}
                      stroke="#5cc8e0"
                      strokeWidth={4}
                    />
                  )}
                  {draft.map(([x, y], index) => (
                    <circle key={index} cx={x * (camera.frame_width || SIZE)} cy={y * (camera.frame_height || SIZE)} r={8} fill="#f2a93b" />
                  ))}
                  {frame?.objects.map((object, index) => {
                    const [x1, y1, x2, y2] = object.bbox;
                    return (
                      <g key={object.track_id || index}>
                        <rect
                          x={x1}
                          y={y1}
                          width={Math.max(0, x2 - x1)}
                          height={Math.max(0, y2 - y1)}
                          fill="none"
                          stroke="#f2a93b"
                          strokeWidth={4}
                        />
                        <text x={x1} y={Math.max(24, y1 - 8)} fill="#f2a93b" fontSize={28}>
                          {object.class}
                        </text>
                      </g>
                    );
                  })}
                </svg>
                </div>
                <div className="mt-2 flex flex-wrap items-center gap-3 px-1 text-sm">
                  <button type="button" className="demo-secondary" onClick={() => setPlaying((value) => !value)}>
                    {playing ? "Pause" : "Play loop"}
                  </button>
                  <label className="text-muted">
                    {time.toFixed(1)}s
                    <input
                      className="ml-2 align-middle"
                      type="range"
                      min={0}
                      max={camera.duration_s}
                      step={0.1}
                      value={Math.min(time, camera.duration_s)}
                      onChange={(event) => {
                        setPlaying(false);
                        setTime(Number(event.target.value));
                      }}
                    />
                  </label>
                  {liveAlert && <span className="text-alta">Now: {liveAlert.message}</span>}
                </div>
              </div>

              {camera.zone_editable && (
                <div className="rounded-lg border border-dashed border-line p-3 text-sm">
                  <p className="font-bold">Draw the pen</p>
                  <p className="mt-1 text-muted">
                    Click the corners of the corral on the picture, then apply. Alerts use a {camera.sustain_s} second
                    wait, so an animal that only passes through does not count. In-app only — no SMS.
                  </p>
                  <div className="flex flex-wrap gap-2">
                    <button type="button" className="demo-primary" disabled={draft.length < 3} onClick={() => void applyZone()}>
                      Apply this pen
                    </button>
                    <button type="button" className="demo-secondary" onClick={() => setDraft([])}>
                      Clear corners
                    </button>
                  </div>
                </div>
              )}
            </>
          )}

          <section aria-labelledby="inbox-h">
            <h2 id="inbox-h" className="text-xs font-bold uppercase tracking-[0.16em] text-muted">
              Alert inbox
            </h2>
            <p className="mt-1 text-sm text-muted">
              Confirm means you saw it. Dismiss means you do not need it. Rastro does not text anyone or call anyone.
            </p>
            {inbox.length === 0 ? (
              <p className="mt-2 text-sm text-muted">No alerts for the cameras on this server.</p>
            ) : (
              <ul className="mt-3 space-y-3">
                {inbox.map((alert) => (
                  <li key={`${alert.camera_id}-${alert.id}`} className="rounded-lg border border-line bg-panel p-3">
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <div>
                        <p className="text-xs uppercase tracking-wide text-muted">
                          {alert.camera_name} · {alert.t_s.toFixed(1)}s · {alert.severity}
                          {alert.verification === "NOT VERIFIED" ? " · Not verified" : ""}
                        </p>
                        <p className="mt-1 font-display text-2xl leading-tight">{alert.message}</p>
                        {alert.label && <p className="text-sm text-muted">{alert.label}</p>}
                        <p className="text-sm text-muted">Status: {alert.status}</p>
                      </div>
                      <Snapshot boxes={alert.snapshot?.boxes ?? []} />
                    </div>
                    {alert.status === "open" && alert.camera_id && alert.kind === "person_in_zone" && (
                      <div>
                        <p className="text-sm text-muted">
                          Possible intrusion — needs review. A person chooses. Rastro does not notify authorities.
                        </p>
                        <button type="button" className="demo-primary" onClick={() => void review(alert.id, alert.camera_id!)}>
                          Review
                        </button>
                      </div>
                    )}
                    {alert.status === "open" && alert.camera_id && alert.kind !== "person_in_zone" && alert.kind !== "count" && (
                      <div className="flex flex-wrap gap-2">
                        <button type="button" className="demo-primary" onClick={() => void act(alert.id, "confirm", alert.camera_id)}>
                          Confirm
                        </button>
                        <button type="button" className="demo-secondary" onClick={() => void act(alert.id, "dismiss", alert.camera_id)}>
                          Dismiss
                        </button>
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </section>

          <PeakHours />
          {camera?.credit?.source_url && (
            <p className="text-xs leading-relaxed text-muted">
              This clip: {camera.credit.title} by {camera.credit.author},{" "}
              <a className="underline" href={camera.credit.license_url}>
                {camera.credit.license}
              </a>
              .{" "}
              <a className="underline" href={camera.credit.source_url}>
                Source
              </a>
              .
            </p>
          )}
        </div>
      </div>
      <footer className="mt-8 border-t border-line pt-4 text-xs leading-relaxed text-muted">
        <h2 className="text-[11px] font-bold uppercase tracking-[0.16em]">Data and credits</h2>
        <ul className="mt-2 space-y-1">
          <li>Gray fox in New Mexico by Andy, CC BY 3.0, Wikimedia Commons.</li>
          <li>Goats going home by Thamizhpparithi Maari, CC BY-SA 3.0, Wikimedia Commons.</li>
          <li>DSCF0004 and DSCF0112, Seattle(ish) Camera Traps by Dan Morris, LILA BC, CDLA permissive. Faces in the published person clip are blurred.</li>
          <li>Plaza Mayor (Madrid) by Michiel1972, CC BY-SA 3.0, Wikimedia Commons.</li>
          <li>Wicker Park intersection changes by Steven Vance, CC BY 3.0, Wikimedia Commons. Traffic count not verified.</li>
        </ul>
      </footer>
    </div>
  );
}

function Snapshot({ boxes }: { boxes: BoxRow[] }) {
  if (!boxes.length) return null;
  return (
    <svg viewBox={`0 0 ${SIZE} ${SIZE}`} className="h-24 w-40 rounded border border-line bg-ink" aria-label="Snapshot frame">
      <rect width={SIZE} height={SIZE} fill="#0b100e" />
      {boxes.map((box, index) => {
        const [x1, y1, x2, y2] = box.bbox;
        return (
          <rect
            key={index}
            x={x1}
            y={y1}
            width={Math.max(1, x2 - x1)}
            height={Math.max(1, y2 - y1)}
            fill="#ff6b5b"
            fillOpacity={0.35}
            stroke="#ff6b5b"
            strokeWidth={8}
          />
        );
      })}
    </svg>
  );
}

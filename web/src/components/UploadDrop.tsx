"use client";

import { useCallback, useId, useRef, useState } from "react";
import {
  MAX_DURATION_S,
  MAX_UPLOAD_BYTES,
  uploadClip,
  validateUploadFile,
} from "@/lib/upload";

type Props = {
  packId: string;
  /** Se llama solo si la validación client-side pasa. */
  onFile?: (file: File, meta: { duration_s: number }) => void;
  /** Tras firmar+PUT (o null si backend pendiente). */
  onJobId?: (jobId: string) => void;
};

type UiState =
  | { kind: "idle" }
  | { kind: "checking"; name: string }
  | { kind: "ok"; name: string; duration_s: number; note?: string }
  | { kind: "error"; message: string };

export function UploadDrop({ packId, onFile, onJobId }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [drag, setDrag] = useState(false);
  const [state, setState] = useState<UiState>({ kind: "idle" });
  const helpId = useId();
  const statusId = useId();
  const busy = state.kind === "checking";

  const take = useCallback(
    async (file: File | undefined) => {
      if (!file || busy) return;
      setState({ kind: "checking", name: file.name });

      const validated = await validateUploadFile(file);
      if (!validated.ok) {
        setState({ kind: "error", message: validated.message });
        if (inputRef.current) inputRef.current.value = "";
        return;
      }

      onFile?.(validated.file, { duration_s: validated.duration_s });

      const uploaded = await uploadClip({
        file: validated.file,
        duration_s: validated.duration_s,
        packId,
      });

      if (uploaded.ok) {
        setState({
          kind: "ok",
          name: validated.file.name,
          duration_s: validated.duration_s,
          note: `Trabajo ${uploaded.jobId.slice(0, 8)}…`,
        });
        onJobId?.(uploaded.jobId);
      } else if (uploaded.pending) {
        setState({
          kind: "ok",
          name: validated.file.name,
          duration_s: validated.duration_s,
          note: uploaded.message,
        });
      } else {
        setState({ kind: "error", message: uploaded.message });
      }

      if (inputRef.current) inputRef.current.value = "";
    },
    [busy, onFile, onJobId, packId],
  );

  return (
    <div
      className={
        "rounded-lg border border-dashed p-4 text-center transition-colors " +
        (drag ? "border-pack bg-panel" : "border-line bg-panel/60") +
        (state.kind === "error" ? " border-alta/50" : "")
      }
      onDragOver={(e) => {
        e.preventDefault();
        setDrag(true);
      }}
      onDragLeave={() => setDrag(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDrag(false);
        void take(e.dataTransfer.files?.[0]);
      }}
      aria-busy={busy}
      aria-describedby={helpId}
    >
      <p className="font-display text-lg font-semibold text-pack">
        Subí un clip
      </p>
      <p id={helpId} className="mt-1 text-xs text-muted">
        Solo MP4 o MOV · máx. {MAX_UPLOAD_BYTES / (1024 * 1024)} MB · máx.{" "}
        {MAX_DURATION_S} s. Recomendado: 720p. La validación es local; el
        backend de subida lo aporta CORE.
      </p>
      <button
        type="button"
        className="mt-3 rounded-full border border-line px-4 py-1.5 text-sm hover:border-pack disabled:opacity-50"
        onClick={() => inputRef.current?.click()}
        disabled={busy}
      >
        {busy ? "Validando…" : "Elegir archivo"}
      </button>
      <input
        ref={inputRef}
        type="file"
        accept="video/mp4,video/quicktime,.mp4,.mov"
        className="sr-only"
        disabled={busy}
        aria-describedby={helpId}
        onChange={(e) => void take(e.target.files?.[0])}
      />

      <div
        id={statusId}
        className="mt-2 min-h-[1.25rem] text-xs"
        role="status"
        aria-live="polite"
        aria-atomic="true"
      >
        {state.kind === "checking" && (
          <p className="text-muted">Validando «{state.name}»…</p>
        )}
        {state.kind === "ok" && (
          <p className="text-[var(--text)]">
            Listo: {state.name} ({state.duration_s.toFixed(1)} s)
            {state.note ? ` — ${state.note}` : ""}
          </p>
        )}
        {state.kind === "error" && (
          <p className="text-alta" role="alert">
            {state.message}
          </p>
        )}
      </div>
    </div>
  );
}

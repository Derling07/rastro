/**
 * Subida de clips — FRONT valida; CORE posee /api/upload (commits 2e0c4f3, 91900a0).
 * Contrato: POST {filename, contentType, size, duration_s, packId}
 *           → {jobId, uploadUrl}; luego PUT del archivo a uploadUrl.
 */

export const MAX_UPLOAD_BYTES = 50 * 1024 * 1024; // 50 MB
export const MAX_DURATION_S = 120;
export const ACCEPTED_MIME = ["video/mp4", "video/quicktime"] as const;
export const ACCEPTED_EXT = [".mp4", ".mov"] as const;

export type UploadValidationOk = {
  ok: true;
  file: File;
  duration_s: number;
};

export type UploadValidationErr = {
  ok: false;
  message: string;
};

export type UploadValidation = UploadValidationOk | UploadValidationErr;

export type SignedUploadRequest = {
  filename: string;
  contentType: string;
  size: number;
  duration_s: number;
  packId: string;
};

export type SignedUploadResponse = {
  uploadUrl: string;
  jobId: string;
  headers?: Record<string, string>;
};

export type SignedUploadResult =
  | { ok: true; data: SignedUploadResponse }
  | { ok: false; pending: true; message: string }
  | { ok: false; pending: false; message: string; status?: number };

export type UploadClipResult =
  | { ok: true; jobId: string }
  | { ok: false; pending: true; message: string }
  | { ok: false; pending: false; message: string };

function extOf(name: string): string {
  const i = name.lastIndexOf(".");
  return i >= 0 ? name.slice(i).toLowerCase() : "";
}

/** Tipo o extensión MP4/MOV (QuickTime). */
export function isAcceptedVideoFile(file: File): boolean {
  if ((ACCEPTED_MIME as readonly string[]).includes(file.type)) return true;
  if (!file.type) {
    return (ACCEPTED_EXT as readonly string[]).includes(extOf(file.name));
  }
  return false;
}

/**
 * Lee la duración con un <video> oculto (loadedmetadata).
 * Revoca el object URL al terminar.
 */
export function readVideoDuration(file: File): Promise<number> {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const video = document.createElement("video");
    video.preload = "metadata";
    video.muted = true;
    video.playsInline = true;

    const cleanup = () => {
      video.removeAttribute("src");
      video.load();
      URL.revokeObjectURL(url);
    };

    video.onloadedmetadata = () => {
      const d = video.duration;
      cleanup();
      if (!Number.isFinite(d) || d <= 0) {
        reject(new Error("duration"));
        return;
      }
      resolve(d);
    };
    video.onerror = () => {
      cleanup();
      reject(new Error("metadata"));
    };
    video.src = url;
  });
}

/**
 * Validación client-side ANTES de cualquier subida:
 * MP4/MOV, ≤50 MB, ≤120 s (vía loadedmetadata).
 */
export async function validateUploadFile(
  file: File,
): Promise<UploadValidation> {
  if (!isAcceptedVideoFile(file)) {
    return {
      ok: false,
      message:
        "Solo se aceptan videos MP4 o MOV (video/mp4 o video/quicktime).",
    };
  }
  if (file.size > MAX_UPLOAD_BYTES) {
    const mb = (file.size / (1024 * 1024)).toFixed(1);
    return {
      ok: false,
      message: `El archivo pesa ${mb} MB. El máximo es 50 MB.`,
    };
  }

  let duration_s: number;
  try {
    duration_s = await readVideoDuration(file);
  } catch {
    return {
      ok: false,
      message:
        "No se pudo leer la duración del video. Probá otro archivo MP4/MOV.",
    };
  }

  if (duration_s > MAX_DURATION_S) {
    return {
      ok: false,
      message: `El video dura ${Math.ceil(duration_s)} s. El máximo es 120 segundos.`,
    };
  }

  return { ok: true, file, duration_s };
}

/**
 * Placeholder tipado: POST /api/upload (ruta de CORE).
 * Body: {filename, contentType, size, duration_s, packId}.
 * 404 → pending («backend de subida pendiente»).
 */
export async function requestSignedUpload(
  body: SignedUploadRequest,
): Promise<SignedUploadResult> {
  try {
    const res = await fetch("/api/upload", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(body),
    });

    if (res.status === 404) {
      return {
        ok: false,
        pending: true,
        message: "Backend de subida pendiente (CORE aún no expone /api/upload).",
      };
    }

    if (!res.ok) {
      let detail = "";
      try {
        const j = (await res.json()) as { message?: string; error?: string };
        detail = j.message || j.error || "";
      } catch {
        /* ignore */
      }
      return {
        ok: false,
        pending: false,
        status: res.status,
        message: detail || `Error al pedir URL de subida (${res.status}).`,
      };
    }

    const data = (await res.json()) as SignedUploadResponse;
    if (!data?.uploadUrl || !data?.jobId) {
      return {
        ok: false,
        pending: false,
        message: "Respuesta de /api/upload sin uploadUrl o jobId.",
      };
    }
    return { ok: true, data };
  } catch {
    return {
      ok: false,
      pending: true,
      message: "Backend de subida pendiente (no se pudo contactar /api/upload).",
    };
  }
}

/** PUT del archivo a la URL firmada que devolvió CORE. */
export async function putToSignedUrl(
  uploadUrl: string,
  file: File,
  headers?: Record<string, string>,
): Promise<{ ok: true } | { ok: false; message: string }> {
  try {
    const res = await fetch(uploadUrl, {
      method: "PUT",
      headers: {
        "Content-Type": file.type || "video/mp4",
        ...(headers ?? {}),
      },
      body: file,
    });
    if (!res.ok) {
      return {
        ok: false,
        message: `No se pudo subir el archivo (${res.status}).`,
      };
    }
    return { ok: true };
  } catch {
    return {
      ok: false,
      message: "Falló la subida directa al almacenamiento.",
    };
  }
}

/**
 * Flujo completo: firmar → PUT → devolver jobId para JobProgress.
 */
export async function uploadClip(opts: {
  file: File;
  duration_s: number;
  packId: string;
}): Promise<UploadClipResult> {
  const signed = await requestSignedUpload({
    filename: opts.file.name,
    contentType: opts.file.type || "video/mp4",
    size: opts.file.size,
    duration_s: opts.duration_s,
    packId: opts.packId,
  });

  if (!signed.ok) {
    if (signed.pending) {
      return { ok: false, pending: true, message: signed.message };
    }
    return { ok: false, pending: false, message: signed.message };
  }

  const put = await putToSignedUrl(
    signed.data.uploadUrl,
    opts.file,
    signed.data.headers,
  );
  if (!put.ok) {
    return { ok: false, pending: false, message: put.message };
  }

  return { ok: true, jobId: signed.data.jobId };
}

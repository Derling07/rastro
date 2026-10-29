// POST /api/upload — firma una subida directa a Supabase Storage y encola el trabajo.
// El video NO pasa por Vercel: el navegador sube con la URL firmada que devolvemos.
// Variables (solo servidor, nunca NEXT_PUBLIC_): SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY.
import { randomUUID } from "node:crypto";

export const runtime = "nodejs";

const BUCKET = "videos";
const MAX_BYTES = 50 * 1024 * 1024; // límite por archivo de la capa gratuita
const TYPES: Record<string, string> = { "video/mp4": "mp4", "video/quicktime": "mov" };
const PACK_RE = /^[a-z0-9][a-z0-9-]{1,63}$/;

type Body = { filename?: unknown; size?: unknown; contentType?: unknown; packId?: unknown; duration_s?: unknown };

function validateUpload(b: Body): { ok: true; ext: string } | { ok: false; error: string } {
  if (typeof b.filename !== "string" || b.filename.length === 0 || b.filename.length > 200)
    return { ok: false, error: "Nombre de archivo inválido." };
  if (typeof b.contentType !== "string" || !(b.contentType in TYPES))
    return { ok: false, error: "Solo se aceptan videos MP4 o MOV." };
  if (typeof b.size !== "number" || !Number.isInteger(b.size) || b.size <= 0)
    return { ok: false, error: "Tamaño inválido." };
  if (b.size > MAX_BYTES)
    return { ok: false, error: "El video pasa de 50 MB. Usá un clip de máximo 2 minutos a 720p." };
  if (typeof b.duration_s !== "number" || b.duration_s <= 0 || b.duration_s > 120)
    return { ok: false, error: "El video dura más de 2 minutos." };
  if (typeof b.packId !== "string" || !PACK_RE.test(b.packId))
    return { ok: false, error: "Paquete inválido." };
  return { ok: true, ext: TYPES[b.contentType] };
}

export async function POST(req: Request): Promise<Response> {
  // Primero se valida el pedido (400) y después la configuración (503).
  let body: Body;
  try { body = await req.json(); } catch { return Response.json({ error: "JSON inválido." }, { status: 400 }); }
  const v = validateUpload(body);
  if (!v.ok) return Response.json({ error: v.error }, { status: 400 });

  const url = process.env.SUPABASE_URL;
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!url || !key) return Response.json({ error: "Subida no configurada." }, { status: 503 });

  const objectPath = `${randomUUID()}.${v.ext}`;
  const headers = { Authorization: `Bearer ${key}`, apikey: key, "Content-Type": "application/json" };

  const sign = await fetch(`${url}/storage/v1/object/upload/sign/${BUCKET}/${objectPath}`, {
    method: "POST", headers, body: "{}",
  });
  if (!sign.ok) return Response.json({ error: "No se pudo firmar la subida." }, { status: 502 });
  const { url: signedPath } = (await sign.json()) as { url: string };

  const job = await fetch(`${url}/rest/v1/jobs`, {
    method: "POST",
    headers: { ...headers, Prefer: "return=representation" },
    body: JSON.stringify({
      storage_path: `${BUCKET}/${objectPath}`, pack_id: body.packId,
      original_name: body.filename, size_bytes: body.size, content_type: body.contentType,
    }),
  });
  if (!job.ok) return Response.json({ error: "No se pudo crear el trabajo." }, { status: 502 });
  const [row] = (await job.json()) as { id: string }[];

  // signedPath viene como "/object/upload/sign/videos/<path>?token=...". El cliente hace PUT del archivo a uploadUrl.
  return Response.json({ jobId: row.id, uploadUrl: `${url}/storage/v1${signedPath}` }, { status: 201 });
}

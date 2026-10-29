// POST /api/upload — sign a direct upload to Supabase Storage and enqueue the job.
// The video does not pass through the app server: the browser uploads to the signed URL.
// Server-only variables (never NEXT_PUBLIC_): SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY.
import { randomUUID } from "node:crypto";

export const runtime = "nodejs";

const BUCKET = "videos";
const MAX_BYTES = 50 * 1024 * 1024; // free-tier per-file limit
const TYPES: Record<string, string> = { "video/mp4": "mp4", "video/quicktime": "mov" };
const PACK_RE = /^[a-z0-9][a-z0-9-]{1,63}$/;

type Body = { filename?: unknown; size?: unknown; contentType?: unknown; packId?: unknown; duration_s?: unknown };

function validateUpload(b: Body): { ok: true; ext: string } | { ok: false; error: string } {
  if (typeof b.filename !== "string" || b.filename.length === 0 || b.filename.length > 200)
    return { ok: false, error: "Invalid file name." };
  if (typeof b.contentType !== "string" || !(b.contentType in TYPES))
    return { ok: false, error: "Only MP4 or MOV videos are accepted." };
  if (typeof b.size !== "number" || !Number.isInteger(b.size) || b.size <= 0)
    return { ok: false, error: "Invalid size." };
  if (b.size > MAX_BYTES)
    return { ok: false, error: "The video is over 50 MB. Use a clip of at most 2 minutes at 720p." };
  if (typeof b.duration_s !== "number" || b.duration_s <= 0 || b.duration_s > 120)
    return { ok: false, error: "The video is longer than 2 minutes." };
  if (typeof b.packId !== "string" || !PACK_RE.test(b.packId))
    return { ok: false, error: "Invalid pack." };
  return { ok: true, ext: TYPES[b.contentType] };
}

export async function POST(req: Request): Promise<Response> {
  // Validate the request first (400), then configuration (503).
  let body: Body;
  try { body = await req.json(); } catch { return Response.json({ error: "Invalid JSON." }, { status: 400 }); }
  const v = validateUpload(body);
  if (!v.ok) return Response.json({ error: v.error }, { status: 400 });

  const url = process.env.SUPABASE_URL;
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!url || !key) return Response.json({ error: "Upload is not configured." }, { status: 503 });

  const objectPath = `${randomUUID()}.${v.ext}`;
  const headers = { Authorization: `Bearer ${key}`, apikey: key, "Content-Type": "application/json" };

  const sign = await fetch(`${url}/storage/v1/object/upload/sign/${BUCKET}/${objectPath}`, {
    method: "POST", headers, body: "{}",
  });
  if (!sign.ok) return Response.json({ error: "Could not sign the upload." }, { status: 502 });
  const { url: signedPath } = (await sign.json()) as { url: string };

  const job = await fetch(`${url}/rest/v1/jobs`, {
    method: "POST",
    headers: { ...headers, Prefer: "return=representation" },
    body: JSON.stringify({
      storage_path: `${BUCKET}/${objectPath}`, pack_id: body.packId,
      original_name: body.filename, size_bytes: body.size, content_type: body.contentType,
    }),
  });
  if (!job.ok) return Response.json({ error: "Could not create the job." }, { status: 502 });
  const [row] = (await job.json()) as { id: string }[];

  // signedPath looks like "/object/upload/sign/videos/<path>?token=...". The client PUTs the file to uploadUrl.
  return Response.json({ jobId: row.id, uploadUrl: `${url}/storage/v1${signedPath}` }, { status: 201 });
}

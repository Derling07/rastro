// Server-only proxy for field-note writes. The token never reaches the browser.
export const runtime = "nodejs";
export const dynamic = "force-dynamic";

function apiBase(): string {
  return (process.env.RASTRO_API_URL || "http://127.0.0.1:8787").replace(/\/$/, "");
}

export async function GET(req: Request): Promise<Response> {
  const url = new URL(req.url);
  const res = await fetch(`${apiBase()}/api/field-note${url.search}`, { cache: "no-store" });
  return new Response(await res.arrayBuffer(), {
    status: res.status,
    headers: { "content-type": "application/json", "cache-control": "no-store" },
  });
}

export async function POST(req: Request): Promise<Response> {
  const token = process.env.RASTRO_WRITE_TOKEN;
  if (!token) {
    return Response.json({ error: "Set RASTRO_WRITE_TOKEN" }, { status: 401 });
  }
  const res = await fetch(`${apiBase()}/api/field-note`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-rastro-token": token,
    },
    body: await req.text(),
    cache: "no-store",
  });
  return new Response(await res.arrayBuffer(), {
    status: res.status,
    headers: { "content-type": "application/json", "cache-control": "no-store" },
  });
}

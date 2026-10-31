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
  const headers = new Headers({ "content-type": "application/json" });
  // Empty token: forward as-is so the API can allow localhost. A set token is attached here.
  if (token) headers.set("x-rastro-token", token);
  const res = await fetch(`${apiBase()}/api/field-note`, {
    method: "POST",
    headers,
    body: await req.text(),
    cache: "no-store",
  });
  return new Response(await res.arrayBuffer(), {
    status: res.status,
    headers: { "content-type": res.headers.get("content-type") || "application/json", "cache-control": "no-store" },
  });
}

import type { FieldNote } from "@/components/notebook/AlertCard";

/** Shared confirm/dismiss/review. A non-JSON body becomes a status error, not a page crash. */
export async function saveFieldNote(
  id: string,
  action: "confirm" | "dismiss" | "review",
): Promise<FieldNote> {
  let res: Response;
  try {
    res = await fetch("/api/field-note", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id, action }),
    });
  } catch {
    throw new Error("server error (0)");
  }
  let body: { note?: FieldNote; error?: string } | null = null;
  try {
    body = (await res.json()) as { note?: FieldNote; error?: string };
  } catch {
    throw new Error(`server error (${res.status})`);
  }
  if (!body || typeof body !== "object" || !body.note) {
    const message = body && typeof body.error === "string" ? body.error : "";
    throw new Error(message || `server error (${res.status})`);
  }
  if (!res.ok) {
    throw new Error(body.error || `server error (${res.status})`);
  }
  return body.note;
}

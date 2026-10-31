/** Human names for clips and modules. File names stay out of the UI. */

const PACK_LABEL: Record<string, string> = {
  fauna: "Wildlife camera",
  "fauna-camtrap": "Wildlife camera",
  transito: "Intersection",
  "transito-giros": "Intersection",
  multitudes: "Crowds",
  "multitudes-densidad": "Crowds",
  farm: "Farm",
  "farm-pen": "Farm",
  protected: "Protected area",
  "protected-zone": "Protected area",
};

/** Longest pack id first so fauna-camtrap is not rewritten as "Wildlife camera-camtrap". */
const PACK_KEYS = Object.entries(PACK_LABEL).sort((a, b) => b[0].length - a[0].length);

/** Add one final period when the text does not already end with punctuation. */
export function finishSentence(text: string): string {
  const cleaned = text.trim();
  if (!cleaned || ".!?".includes(cleaned[cleaned.length - 1])) return cleaned;
  return `${cleaned}.`;
}

export function zoneLabel(zone: string | undefined | null): string {
  const raw = (zone || "").trim();
  const match = /^(?:zone|zona)[_\s-]*(\d+)$/i.exec(raw);
  if (match) return `Zone ${match[1]}`;
  return raw.replace(/_/g, " ");
}

export function clipLabel(text: string): string {
  let cleaned = text.replace(/\bok\.mp4\b/gi, "");
  cleaned = cleaned.replace(/DSCF0112\.mp4(?:\s*\([^)]*\))?/gi, "Wildlife camera");
  cleaned = cleaned.replace(/Clip\s+Intersection\.mp4/gi, "Intersection");
  cleaned = cleaned.replace(/Intersection\.mp4/gi, "Intersection");
  cleaned = cleaned.replace(/\([^)]*\bfps\b[^)]*\)/gi, "");
  cleaned = cleaned.replace(/\b[\w.-]+\.(mp4|mov|webm|ogv)\b/gi, "");
  cleaned = cleaned.replace(/\s+at demo\b/gi, "");
  for (const [raw, label] of PACK_KEYS) {
    const escaped = raw.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    cleaned = cleaned.replace(new RegExp(`\\b${escaped}\\b`, "g"), label);
  }
  cleaned = cleaned.replace(/\b(?:zone|zona)[_\s-]*(\d+)\b/gi, "Zone $1");
  cleaned = cleaned.replace(/\s{2,}/g, " ").replace(/\s+([.,])/g, "$1").trim();
  return cleaned || "Upload";
}

export function moduleLabel(pack: string | undefined): string {
  return PACK_LABEL[pack || ""] || pack || "";
}

export function placeLabel(name: string): string {
  return name;
}

/** Visible tracker name. Raw track and object ids stay in the result JSON. */
export function trackerLabel(trackId: string, className?: string): string {
  const id = trackId || "";
  const numbered = /^(.*?)-(\d+)$/.exec(id);
  const rawName = (className || (numbered ? numbered[1] : id) || "track").replace(/[_-]+/g, " ").trim();
  const index = numbered ? String(Number(numbered[2])) : "1";
  const name = rawName.replace(/\b[a-z]/g, (letter) => letter.toUpperCase());
  return `${name} ${index}`;
}

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

export function clipLabel(text: string): string {
  let cleaned = text.replace(/\bok\.mp4\b/gi, "");
  cleaned = cleaned.replace(/DSCF0112\.mp4(?:\s*\([^)]*\))?/gi, "Wildlife camera");
  cleaned = cleaned.replace(/Clip\s+Intersection\.mp4/gi, "Intersection");
  cleaned = cleaned.replace(/Intersection\.mp4/gi, "Intersection");
  cleaned = cleaned.replace(/\([^)]*\bfps\b[^)]*\)/gi, "");
  cleaned = cleaned.replace(/\b[\w.-]+\.(mp4|mov|webm|ogv)\b/gi, "");
  cleaned = cleaned.replace(/\s+at demo\b/gi, "");
  for (const [raw, label] of Object.entries(PACK_LABEL)) {
    cleaned = cleaned.replace(new RegExp(`\\b${raw}\\b`, "g"), label);
  }
  cleaned = cleaned.replace(/\s{2,}/g, " ").replace(/\s+([.,])/g, "$1").trim();
  return cleaned || "Upload";
}

export function moduleLabel(pack: string | undefined): string {
  return PACK_LABEL[pack || ""] || pack || "";
}

export function placeLabel(name: string): string {
  return name;
}

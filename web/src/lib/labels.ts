/** Human names for clips and modules. File names stay out of the UI. */

export function clipLabel(text: string): string {
  const cleaned = text
    .replace(/\bok\.mp4\b/gi, "")
    .replace(/DSCF0112\.mp4/gi, "Camera trap clip")
    .replace(/Intersection\.mp4/gi, "Intersection clip")
    .replace(/\b[\w.-]+\.(mp4|mov)\b/gi, (name) => name.replace(/\.(mp4|mov)$/i, ""))
    .replace(/\s{2,}/g, " ")
    .replace(/\s+([.,])/g, "$1")
    .trim();
  return cleaned || "Upload";
}

export function moduleLabel(pack: string | undefined): string {
  if (pack === "multitudes" || pack === "multitudes-densidad") return "Crowds";
  if (pack === "transito" || pack === "transito-giros") return "Turning traffic";
  if (pack === "fauna" || pack === "fauna-camtrap") return "Camera trap";
  if (pack === "farm") return "Farm";
  if (pack === "protected") return "Protected area";
  return pack || "";
}

export function placeLabel(name: string): string {
  if (name === "Forest trail") return "Forest Trail clip";
  return name;
}

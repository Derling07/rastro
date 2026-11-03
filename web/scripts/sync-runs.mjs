#!/usr/bin/env node
import { cpSync, mkdirSync, existsSync, rmSync, readFileSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = join(__dirname, "..");
const dest = join(root, "public", "runs");
const outputs = join(root, "..", "outputs");

const DEMOS = [
  ["demo-real-coyote-0112", "Coyote DSCF0112 real (90 raw detections, individuals NOT VERIFIED)"],
  ["demo-real-coyote", "Coyote DSCF0104 real"],
  ["demo-mock-coyote", "Coyote · datos de ejemplo"],
  ["demo-mock-persona", "Persona noche · datos de ejemplo"],
  ["demo-mock-voice", "Con nota de voz · datos de ejemplo"],
];

if (existsSync(dest)) rmSync(dest, { recursive: true, force: true });
mkdirSync(dest, { recursive: true });

const runs = [];
for (const [id, label] of DEMOS) {
  const src = join(outputs, id);
  if (!existsSync(src)) { console.warn("skip", id); continue; }
  const target = join(dest, id);
  cpSync(src, target, { recursive: true });
  const resultPath = join(target, "result.json");
  const result = JSON.parse(readFileSync(resultPath, "utf8"));
  const ann = result.artifacts?.annotated_video;
  result.video = result.video || {};
  if (ann) {
    result.video.annotated_url = `/runs/${id}/${ann}`;
    result.video.url = `/runs/${id}/${ann}`;
  }
  const stem = result.source_video_id || "DSCF0104";
  const poster = join(root, "public", "frames", `${stem}_t1.jpg`);
  if (existsSync(poster)) result.video.poster = `/frames/${stem}_t1.jpg`;
  if (result.voice && result.voice.is_public === undefined) {
    result.voice.is_public = false;
  }
  writeFileSync(resultPath, JSON.stringify(result, null, 2));
  runs.push({
    id, label, pack: "fauna", pack_file: "fauna.json",
    source_video_id: result.source_video_id,
    is_mock: Boolean(result.is_mock),
    naive_count: result.naive_count,
    unique_count: result.unique_count,
    detections_total: result.detections_total ?? null,
    path: `/runs/${id}`,
  });
  console.log("✓", id);
}

writeFileSync(join(dest, "index.json"), JSON.stringify({
  runs,
  packs: {
    fauna: { pack_file: "fauna.json", has_run: true },
    transito: { pack_file: "transito.json", has_run: false, _sin_corrida: true },
    multitudes: { pack_file: "multitudes.json", has_run: false, _sin_corrida: true },
  },
  default_run_id: "demo-real-coyote-0112",
}, null, 2));
console.log("listo:", runs.length, "default demo-real-coyote-0112");

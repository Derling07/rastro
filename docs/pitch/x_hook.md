# Plan de premios extra (X / comunidad / agentes / creatividad) — Rastro

**Estado:** borrador interno. **No publicar** nada en X, GitHub ni redes hasta que Derling apruebe el texto y ORION autorice deploy/publicación.

Meta Global AI Developer Hackathon 2026 · Indie · entrega 4 nov 2026, 8:00 p.m. hora Costa Rica ([evento](https://dev.meta.ai/events/global-hackathon)).

Números solo desde `eval/`, `outputs/real/`, `outputs/demo-real-coyote-0112` o `docs/OUTPUT_SCHEMA.md` v1.1. Si falta → `[PENDIENTE]`.

---

## Premios

| Premio | Ángulo |
|---|---|
| **Más viral (X)** | **90 detecciones → 2 coyotes** (`demo-real-coyote-0112`, SAM real) + cambio de pack que muestra **sin corrida** en tránsito/multitudes (honestidad) |
| **Voto comunidad** | Panel local (`web/`) con `demo-real-coyote-0112` precargado; mocks marcados **ejemplo** |
| **Mejor uso de agentes** | `agent_log` en `result.json` v1.1 + Spark (Baseten) |
| **Creatividad** | Sector = JSON; mismo motor |

---

## 1. Ganchos para X (3–5) — sin publicar

### A — Contraste verificado (usar este)

> 90 detecciones → 2 coyotes.
>
> SAM 3.1 tracks identity. Rastro counts individuals, not frames.
>
> LILA Seattle(ish) · DSCF0112 · `outputs/demo-real-coyote-0112` (schema 1.1, `is_mock=false`, ≈ \$0.0102).
>
> 90 = `detections_total` (schema 1.1) = raw SAM dets across frames (`sam[].n_detections`). `naive_count` is **2** — do **not** call 90 a naive count. Written by the engine (regenerated at `586a9a1`).

**Fuente:** `outputs/demo-real-coyote-0112/result.json` · Round 2 score `eval/last_score_outputs.json` / `eval/ROUND2_NOTES.md` (DSCF0112 PASS, gt=2).

### B — Panel honesto / pack switch

> Same engine. Different JSON.
>
> Fauna: real run. Transit / crowds: **sin corrida** until we have licensed clips.
>
> Transit: RepOD licenses **vary per file**, not verified — plan is own San José clip (pending Derling). Crowds: clip to be recorded by Derling in San José.

### C — Schema / agent

> One `result.json` (schema 1.1): `naive_count`, `detections_total`, `unique_count`, `by_class`, `cost_usd`, `alerts[].t_s`, `agent_log`, `artifacts.annotated_video`.
>
> Counts from rules — not from the LLM.

### D — Costo / eval

> Round 2 fauna score (3 clips — **small sample**): **MAE 0**, **3/3 exact** (`eval/last_score_outputs.json`, `eval/ROUND2_NOTES.md`).
> DSCF0104 1=1 via `demo-real-coyote` (prompt fallback); DSCF0112 2=2 via `demo-real-coyote-0112`; DSCF0004 1=1. Tests: eval 12/12, repo 24/24.
> Session cost estimate earlier ≈ \$0.082 (`outputs/real/cost_summary.json`).

### E — Comunidad

> Want a new sector? It’s a pack JSON.
> Open an issue: “pack ___”.
> [PENDIENTE: URL repo público]

**Prohibido en X:** cualquier “11 → 3”. Ese contraste **no** está medido en `eval/`.

---

## 2. Storyboard 15–30 s (9:16)

| t | Pantalla | Texto |
|---|---|---|
| 0:00–0:04 | Cámara trampa / clips sin revisar | «Hours of trap video. Nobody reviews it all.» |
| 0:04–0:12 | `artifacts.annotated_video` + contador | «**90 detecciones → 2 coyotes.** DSCF0112.» |
| 0:12–0:20 | Pack switch: fauna (real) → tránsito **· sin corrida** | «Same engine. No fake transit run.» |
| 0:20–0:26 | Nota de voz **solo si** `voice.is_public` (Derling) | «Field note, consented.» Si no hay nota pública: saltar o mostrar solo `report`. |
| 0:26–0:30 | CTA | «Open source · pack = JSON» |

**Accesibilidad:** subtítulos ES+EN burn-in; números grandes; alt text con atribución LILA; sin flash.

**Assets públicos:** no usar `probe_jfk.wav` ni `probe_animal.png` (flags en `eval/LICENSES.md`).

---

## 3. Timing (hora Costa Rica)

| Cuándo | Qué |
|---|---|
| **3 nov** | Clip + hilo con métricas reales | Etiquetar cuentas oficiales — **[PENDIENTE: handles]** |
| **4 nov &lt; 18:00** | Quote/recordatorio | Formulario con colchón antes de las 20:00 |
| Tras OK Derling | Pedir voto comunidad | Publicar en X solo con su aprobación |

Usar corridas cacheadas (`outputs/demo-real-coyote-0112`, `outputs/real/`). No gastar créditos Meta solo para el clip.

---

## 4. Hashtags (borrador)

```
#MetaAIHackathon #SAM3 #OpenSource #CameraTraps #BuildInPublic
```

Atribución: Seattle(ish) Camera Traps — https://lila.science/datasets/seattleish-camera-traps/ (CDLA permissive; versión numerada no clara en ficha — ver `eval/LICENSES.md`).

---

## 5. Voto comunidad / demo local

```bash
cd web && npm install && npm run sync-runs && npm run dev
```

- Default run: `demo-real-coyote-0112` (`is_mock=false`, DSCF0112).
- `demo-mock-*` → etiqueta **ejemplo**.
- Tránsito / multitudes: chips con **sin corrida** (sin fingir pipeline).

---

## 6. No hacer desde este doc

- No publicar en X / no push / no deploy.
- No imprimir `META_API_KEY` / `BASETEN_API_KEY`.
- No gastar créditos sin orden de ORION/Derling.

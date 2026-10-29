# Gaps del set de evaluación (QA)

Plan (`plan_rastro.md` §6): 10 fauna + 5 tránsito + 5 multitudes etiquetados a mano.

## Estado hoy (26 oct 2026)

| Pack | Clips locales etiquetados | Meta del plan |
|---|---|---|
| Fauna | 4 (3 VERIFIED, 1 NOT VERIFIED) | 10 |
| Tránsito | **0** | 5 |
| Multitudes | **0** | 5 |

## Falta para tránsito

- No hay video de intersección en `data/`.
- Métricas previstas: matriz de giros + unique count por clase (auto/bus/moto/camión).

### Candidatos con licencia verificada (sin descargar)

1. **Politechnika Bydgoska — Intersection drone videos (RepOD)**  
   - https://repod.icm.edu.pl/dataset.xhtml?persistentId=doi:10.18150/BAI5PS  
   - Licencia del video de ejemplo: **CC BY 4.0** (confirmada en plan + ficha RepOD).  
   - Nota: video completo a menudo requiere solicitud; es vista de dron (no CCTV a nivel de calle).

2. **Grabación propia San José (recomendado para demo)**  
   - Licencia propuesta: CC BY 4.0 del autor.  
   - Evita depender de sets sin permiso.

### Candidato a evitar en demo público

- **City of Bellevue Traffic Video Dataset** — https://github.com/City-of-Bellevue/TrafficVideoDataset  
  - **FLAG: sin licencia declarada** (plan §5.1). Solo pruebas internas o con permiso escrito.

## Falta para multitudes

- No hay clips de densidad / peatones etiquetados.
- Métrica prevista: personas por zona en frames muestreados (+ densidad/m² si hay homografía).

### Candidatos con licencia verificada (sin descargar)

1. **MOT20** — https://motchallenge.net/data/MOT20  
   - Licencia: **CC BY-NC-SA 3.0** (plan §5.1).  
   - **FLAG NC:** usable en hackathon open source con atribución; **no redistribuir** los videos en el repo; enlazar. Declarar NC-SA en README.

2. **Grabación propia** (feria / salida de estadio, lejos, desde arriba) + difuminado de caras.  
   - Licencia CC BY; mejor historia Costa Rica. Privacidad: sin identidad, solo agregados.

## Otras gaps de fauna

- Solo 4 clips; plan pide 10. Faltan ~6 (idealmente con re-entradas y nocturnos difíciles).
- DSCF0840 quedó **NOT VERIFIED** (niebla IR) — no entra a MAE hasta re-etiquetar o descartar.
- Sin pizotes: historia actual = coyotes Seattle(ish); video CR propio sigue pendiente.
- Lindenthal Camera Traps (IDs de pista anotados) — https://lila.science/datasets/lindenthal-camera-traps/ — CDLA-Permissive, pero rosbag ~213 GB; no bajado.

## Cómo cerrar (propuesta QA, sin ejecutar)

1. Etiquetar 6 fauna más de Seattle(ish) ya listados en Azure (mismo CDLA).  
2. Grabar 1 intersección SJ + etiquetar 5 ventanas de 15–60 s.  
3. Para multitudes: o MOT20 enlazado (NC) o 1 grabación propia difuminada.  
4. Re-visitar DSCF0840 con más frames o marcarlo excluido permanente del leaderboard.

## RepOD Round 2 (transit)

- Only 1 public video (Rondo Fordońskie example, 3.5 GB HEVC, CC BY 4.0) — too large to fetch under 200 MB rule.
- Remaining intersection videos: request-only per dataset description.
- Hand labels for turning movements: NOT VERIFIED until short H.264 cuts are obtained.

## Round 3 transit (Wikimedia)

- Descargados: Chiang Mai (CC BY-SA 4.0) + Wicker Park (CC BY 3.0) → `data/transit/` (ver LICENSES.md §8).
- Etiquetas: **NOT VERIFIED** (densidad / oclusión). Esperan corrida del pack tránsito por ORION → score SKIPPED hasta entonces.
- Seed Supabase actual (`seed_packs.sql`) solo incluye `fauna-camtrap`; falta sembrar pack `transito` desde `packs/*.json` cuando exista.

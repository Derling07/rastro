# supabase/ — base de datos y API de Rastro (CORE)

Capa gratuita de Supabase. La base guarda **solo agregados y metadatos**; los videos
(difuminados) van a Storage y las máscaras de SAM se quedan en `outputs/`.

## Tablas
| Tabla | Qué guarda |
|---|---|
| `packs` | Copia del JSON de cada paquete de `packs/` |
| `runs` | Una corrida: video + paquete, conteo ingenuo vs. único, `by_class`, costo, `is_mock` |
| `events` | Eventos del motor (individuo, cruce, giro, densidad…), campos extra en `data` |
| `alerts` | Alertas (`info`/`baja`/`media`/`alta`), con `acknowledged` |
| `reports` | Reporte del agente, uno por corrida |
| `voice_notes` | Turnos de Voice Transcribe (por turno). Privada salvo `is_public = true` (notas de Derling con consentimiento) |

Vista `run_overview`: una fila por corrida con alertas abiertas, para el panel.

## API
- **Lectura (web):** PostgREST con la clave `anon`, p. ej.
  `GET /rest/v1/run_overview?order=created_at.desc`,
  `GET /rest/v1/events?run_id=eq.<uuid>&order=t_s`.
- **Escritura (solo worker):** `POST /rest/v1/rpc/ingest_run` con `{ "payload": {...} }`
  usando `service_role`. Es atómica e idempotente por `run_key`.

El payload es **`result.json` v1.1 tal cual** (`docs/OUTPUT_SCHEMA.md`):
`run_id` → `runs.run_key`, `pack.id`, `source_video_id`, conteos planos, `events`,
`alerts` (con `t_s`), `voice` (turnos; `voice.is_public` opcional, por defecto privada),
`agent_log`, `report` y `artifacts`. Las `frames`/`tracks` con cajas **no** se guardan
en la base (pesan mucho para la capa gratuita): la web las lee del `result.json`.
Rechaza `schema_version` distinta de `1.x`.

## Seguridad
- RLS activado en todas las tablas: `anon` solo lee; nadie escribe salvo `service_role`.
- `service_role` vive solo en el worker (variable de entorno), **nunca en `web/`** ni en git.

## Aplicar
Nada está desplegado. Cuando ORION lo autorice:
`supabase db push` (o pegar la migración en el SQL Editor) y luego `seed.sql`.

-- Rastro: esquema base (corridas, eventos, alertas, reportes).
-- Capa gratuita de Supabase: solo agregados y metadatos; el video y las
-- máscaras viven en Storage o en outputs/, nunca en la base.

create extension if not exists pgcrypto;

-- Paquetes de sector (copia del JSON de packs/ para que la web los liste).
create table public.packs (
  id          text primary key,                 -- ej. 'fauna-camtrap'
  version     text,
  sector      text,                             -- 'fauna' | 'transito' | 'multitudes' (libre: los paquetes son datos)
  description text,
  config      jsonb not null,                   -- el JSON completo del paquete
  updated_at  timestamptz not null default now()
);

-- Una corrida = un video procesado con un paquete.
create table public.runs (
  id            uuid primary key default gen_random_uuid(),
  run_key       text unique not null,           -- <run_id> de outputs/<run_id>/
  pack_id       text not null references public.packs(id),
  source_video_id text,                         -- mismo video en varios paquetes (cambio en vivo)
  video_name    text not null,
  annotated_video text,                         -- video anotado con máscaras (Storage)
  agent_log     jsonb not null default '[]'::jsonb, -- pasos del agente
  video_path    text,                           -- ruta en Storage (video difuminado)
  status        text not null default 'pending'
                check (status in ('pending','processing','done','failed')),
  schema_version text,
  station       text,
  local_hour    int check (local_hour between 0 and 23),
  artifacts     jsonb not null default '{}'::jsonb,
  native_fps    numeric,
  track_fps     numeric,
  detections_total int check (detections_total >= 0), -- detecciones crudas de SAM (opcional)
  naive_count   int  check (naive_count  >= 0),
  unique_count  int  check (unique_count >= 0),
  by_class      jsonb not null default '{}'::jsonb,   -- {"coyote":3,"persona":1}
  is_mock       boolean not null default false,       -- true si SAM fue simulado
  cost_usd      numeric(10,4),
  error         text,
  created_at    timestamptz not null default now(),
  finished_at   timestamptz
);
create index runs_source_video_idx on public.runs (source_video_id, pack_id);
create index runs_pack_created_idx on public.runs (pack_id, created_at desc);

-- Eventos del motor de reglas (individuo, cruce de línea, giro, densidad...).
create table public.events (
  id           bigint generated always as identity primary key,
  run_id       uuid not null references public.runs(id) on delete cascade,
  kind         text not null,
  t_s          numeric not null check (t_s >= 0),
  track_id     text,
  class_name   text,
  start_frame  int,
  end_frame    int,
  dwell_s      numeric,
  data         jsonb not null default '{}'::jsonb   -- campos extra según kind
);
create index events_run_t_idx on public.events (run_id, t_s);

-- Alertas que dispara el agente o el motor.
create table public.alerts (
  id          bigint generated always as identity primary key,
  run_id      uuid not null references public.runs(id) on delete cascade,
  rule_id     text not null,                     -- ej. 'persona_noche'
  severity    text not null check (severity in ('info','baja','media','alta')),
  message     text not null,
  t_s         numeric,
  acknowledged boolean not null default false,
  created_at  timestamptz not null default now()
);
create index alerts_run_idx on public.alerts (run_id);
create index alerts_open_idx on public.alerts (severity) where not acknowledged;

-- Reporte final del agente (uno por corrida).
create table public.reports (
  run_id      uuid primary key references public.runs(id) on delete cascade,
  title       text not null,
  summary     text not null,
  body        jsonb not null,                    -- reporte completo (especies, alertas...)
  created_at  timestamptz not null default now()
);

-- Notas de voz transcritas (turnos, no palabras: Voice Transcribe no da palabras).
create table public.voice_notes (
  id          bigint generated always as identity primary key,
  run_id      uuid not null references public.runs(id) on delete cascade,
  audio_path  text,
  language    text,
  turns       jsonb not null default '[]'::jsonb, -- [{speaker,start_s,end_s,text}]
  is_public   boolean not null default false,      -- solo notas de Derling con consentimiento
  created_at  timestamptz not null default now()
);
create index voice_notes_run_idx on public.voice_notes (run_id);

-- ── Seguridad (RLS) ─────────────────────────────────────────────
-- Demo pública de solo lectura: anon puede LEER; solo el worker con
-- service_role (que salta RLS) escribe. Nunca exponer service_role en web/.
alter table public.packs       enable row level security;
alter table public.runs        enable row level security;
alter table public.events      enable row level security;
alter table public.alerts      enable row level security;
alter table public.reports     enable row level security;
alter table public.voice_notes enable row level security;

create policy "lectura publica" on public.packs       for select to anon, authenticated using (true);
create policy "lectura publica" on public.runs        for select to anon, authenticated using (true);
create policy "lectura publica" on public.events      for select to anon, authenticated using (true);
create policy "lectura publica" on public.alerts      for select to anon, authenticated using (true);
create policy "lectura publica" on public.reports     for select to anon, authenticated using (true);
-- voice_notes: privada por defecto; solo se leen las marcadas is_public.
create policy "lectura notas publicas" on public.voice_notes for select to anon, authenticated using (is_public);

-- ── API: ingesta atómica de una corrida ─────────────────────────
-- El worker llama POST /rest/v1/rpc/ingest_run con el result.json.
-- Es idempotente por run_key: re-subir la misma corrida la reemplaza.
create or replace function public.ingest_run(payload jsonb)
returns uuid
language plpgsql
security invoker
set search_path = public
as $$
-- Acepta result.json v1.1 tal cual (docs/OUTPUT_SCHEMA.md).
declare
  v_run  uuid;
  v_pack text := payload->'pack'->>'id';
  v_voice jsonb := payload->'voice';
begin
  if payload->>'run_id' is null or v_pack is null then
    raise exception 'result.json necesita run_id y pack.id';
  end if;
  if coalesce(payload->>'schema_version','') not like '1.%' then
    raise exception 'schema_version % no soportada (se espera 1.x)', payload->>'schema_version';
  end if;

  -- El paquete puede no estar sembrado todavía: se registra mínimo.
  insert into packs (id, version, config)
  values (v_pack, payload->'pack'->>'version', '{}'::jsonb)
  on conflict (id) do update set version = excluded.version, updated_at = now();

  delete from runs where run_key = payload->>'run_id';

  insert into runs (run_key, pack_id, source_video_id, video_name, annotated_video,
                    agent_log, artifacts, schema_version, station, local_hour,
                    status, native_fps, track_fps, detections_total, naive_count, unique_count,
                    by_class, is_mock, cost_usd, created_at, finished_at)
  values (payload->>'run_id', v_pack, payload->>'source_video_id',
          payload->'video'->>'path',
          payload->'artifacts'->>'annotated_video',
          coalesce(payload->'agent_log', '[]'::jsonb),
          coalesce(payload->'artifacts', '{}'::jsonb),
          payload->>'schema_version', payload->>'station',
          (payload->>'local_hour')::int,
          'done',
          (payload->'video'->>'native_fps')::numeric,
          (payload->'video'->>'fps')::numeric,
          (payload->>'detections_total')::int,
          (payload->>'naive_count')::int,
          (payload->>'unique_count')::int,
          coalesce(payload->'by_class', '{}'::jsonb),
          coalesce((payload->>'is_mock')::boolean, false),
          (payload->>'cost_usd')::numeric,
          coalesce((payload->>'created_at')::timestamptz, now()),
          now())
  returning id into v_run;

  insert into events (run_id, kind, t_s, track_id, class_name,
                      start_frame, end_frame, dwell_s, data)
  select v_run, e->>'kind', coalesce((e->>'t_s')::numeric, 0), e->>'track_id', e->>'class',
         (e->>'start_frame')::int, (e->>'end_frame')::int, (e->>'dwell_s')::numeric,
         e - array['kind','t_s','track_id','class','start_frame','end_frame','dwell_s']
  from jsonb_array_elements(coalesce(payload->'events', '[]'::jsonb)) e;

  insert into alerts (run_id, rule_id, severity, message, t_s)
  select v_run, a->>'id', a->>'severity', a->>'message', (a->>'t_s')::numeric
  from jsonb_array_elements(coalesce(payload->'alerts', '[]'::jsonb)) a;

  if jsonb_typeof(v_voice) = 'object' then
    insert into voice_notes (run_id, audio_path, language, turns, is_public)
    values (v_run, payload->'artifacts'->>'voice_json', v_voice->>'language',
            coalesce(v_voice->'turns', '[]'::jsonb),
            coalesce((v_voice->>'is_public')::boolean, false));
  end if;

  if jsonb_typeof(payload->'report') = 'object' then
    insert into reports (run_id, title, summary, body)
    values (v_run,
            coalesce(payload->'report'->>'titulo', payload->'report'->>'title', ''),
            coalesce(payload->'report'->>'resumen', payload->'report'->>'summary', ''),
            payload->'report');
  end if;

  return v_run;
end;
$$;

-- Solo el worker (service_role) puede ingerir.
revoke execute on function public.ingest_run(jsonb) from public, anon, authenticated;
grant  execute on function public.ingest_run(jsonb) to service_role;

-- Vista para el panel: una fila por corrida con conteos y alertas abiertas.
create or replace view public.run_overview
with (security_invoker = true) as
select r.id, r.run_key, r.source_video_id, r.pack_id, r.station, r.local_hour, r.cost_usd, p.sector, r.video_name, r.status,
       r.detections_total, r.naive_count, r.unique_count, r.by_class, r.is_mock, r.created_at,
       count(a.id) filter (where not a.acknowledged)               as open_alerts,
       count(a.id) filter (where a.severity = 'alta' and not a.acknowledged) as high_alerts
from runs r
join packs p on p.id = r.pack_id
left join alerts a on a.run_id = r.id
group by r.id, p.sector;
-- Nota: no se aplica en Supabase hasta que Derling lo autorice.

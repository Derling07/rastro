-- ingest_run rechaza paquetes inexistentes o con config vacío (pedido de QA/ORION).
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
  -- El paquete tiene que existir con config real (seed_packs.sql); no se crean paquetes vacíos.
  if not exists (select 1 from packs where id = v_pack and config <> '{}'::jsonb) then
    raise exception 'ingest_run: paquete % no sembrado o con config vacío; aplicá seed_packs.sql', v_pack
      using errcode = '22023';
  end if;
  update packs set version = coalesce(payload->'pack'->>'version', version), updated_at = now()
  where id = v_pack;

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

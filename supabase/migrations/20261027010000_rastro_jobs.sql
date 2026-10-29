-- Rastro: cola de trabajos para subir e ingerir videos.
-- Flujo: web firma la subida -> crea job 'queued' -> worker (PC de ORION)
-- lo reclama con claim_job -> corre `rastro run` -> ingest_run -> finish_job.
-- Bucket privado previsto: 'videos' (se crea solo con autorización de Derling).

create table public.jobs (
  id              uuid primary key default gen_random_uuid(),
  storage_path    text not null unique,            -- videos/<uuid>.mp4
  pack_id         text not null,
  original_name   text not null,
  size_bytes      bigint not null check (size_bytes > 0 and size_bytes <= 52428800), -- 50 MB
  content_type    text not null check (content_type in ('video/mp4','video/quicktime')),
  status          text not null default 'queued'
                  check (status in ('queued','processing','done','failed')),
  stage           text check (stage in ('descargando','motor','guardando')), -- etapa actual del worker
  attempts        int  not null default 0,
  run_id          uuid references public.runs(id) on delete set null,
  error           text,
  worker          text,
  created_at      timestamptz not null default now(),
  started_at      timestamptz,
  finished_at     timestamptz
);
create index jobs_queued_idx on public.jobs (created_at) where status = 'queued';

alter table public.jobs enable row level security;
-- La web solo puede ver el estado de los trabajos (para la barra de progreso).
create policy "lectura estado" on public.jobs for select to anon, authenticated using (true);

-- Reclamo atómico: dos workers nunca toman el mismo trabajo.
create or replace function public.claim_job(worker_name text)
returns setof public.jobs
language sql
security invoker
set search_path = public
as $$
  update jobs j
     set status = 'processing', attempts = j.attempts + 1,
         started_at = now(), worker = worker_name, error = null
   where j.id = (
     select id from jobs
      where status = 'queued'
      order by created_at
      for update skip locked
      limit 1)
  returning j.*;
$$;

-- Cierre del trabajo. Si falla y tiene menos de 3 intentos, vuelve a la cola.
create or replace function public.finish_job(job uuid, ok boolean, run uuid default null, err text default null)
returns void
language sql
security invoker
set search_path = public
as $$
  update jobs
     set status = case when ok then 'done'
                       when attempts < 3 then 'queued'
                       else 'failed' end,
         run_id = coalesce(run, run_id),
         error = left(err, 2000),
         finished_at = case when ok or attempts >= 3 then now() end
   where id = job;
$$;

create or replace function public.set_job_stage(job uuid, new_stage text)
returns void language sql security invoker set search_path = public as $$
  update jobs set stage = new_stage where id = job and status = 'processing';
$$;
revoke execute on function public.set_job_stage(uuid, text) from public, anon, authenticated;
grant  execute on function public.set_job_stage(uuid, text) to service_role;

revoke execute on function public.claim_job(text) from public, anon, authenticated;
revoke execute on function public.finish_job(uuid, boolean, uuid, text) from public, anon, authenticated;
grant  execute on function public.claim_job(text) to service_role;
grant  execute on function public.finish_job(uuid, boolean, uuid, text) to service_role;

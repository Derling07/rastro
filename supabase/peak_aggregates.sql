-- Peak-hour rows only. No video, no frames, no identities.
-- Sized for the Supabase free tier (500 MB): one small integer row per run.

create table if not exists peak_aggregates (
  id bigint generated always as identity primary key,
  station text not null,
  pack text not null,
  weekday smallint,
  hour smallint not null check (hour between 0 and 23),
  metric text not null,
  value integer not null,
  verified boolean not null default false,
  recorded_at timestamptz not null default now()
);

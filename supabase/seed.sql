-- Datos de ejemplo para desarrollo local (no reales; is_mock = true).
insert into public.packs (id, version, sector, description, config)
values ('fauna-camtrap', '0.1', 'fauna', 'Cámaras trampa (ejemplo)', '{}'::jsonb)
on conflict (id) do nothing;

-- Bucket privado para los videos subidos (máx. 50 MB, solo MP4/MOV).
-- Solo service_role (ruta /api/upload y worker) accede; sin políticas para anon.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('videos', 'videos', false, 52428800, array['video/mp4','video/quicktime'])
on conflict (id) do update
  set public = false, file_size_limit = excluded.file_size_limit,
      allowed_mime_types = excluded.allowed_mime_types;

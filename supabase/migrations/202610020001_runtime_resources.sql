-- Runtime resources are private to their creator until workspace sharing is implemented.
create table public.daisy_resources (
  id text primary key,
  owner_id uuid not null references auth.users(id) on delete cascade,
  kind text not null check (kind in ('dataset','artifact','run','preferences')),
  metadata jsonb not null default '{}'::jsonb,
  storage_bucket text check (storage_bucket in ('datasets','model-artifacts')),
  storage_path text,
  updated_at timestamptz not null default now(),
  check ((storage_path is null) = (storage_bucket is null))
);
create index daisy_resources_owner_kind on public.daisy_resources(owner_id,kind,updated_at desc);
alter table public.daisy_resources enable row level security;
revoke all on public.daisy_resources from anon, authenticated;
grant select on public.daisy_resources to authenticated;
create policy resources_select_owner on public.daisy_resources
  for select to authenticated using (owner_id = auth.uid());
create trigger runtime_resources_updated before update on public.daisy_resources
  for each row execute function private.set_updated_at();
-- Buckets remain private; all writes/downloads go through the authenticated API.
insert into storage.buckets(id,name,public,file_size_limit)
values ('datasets','datasets',false,52428800),('model-artifacts','model-artifacts',false,52428800)
on conflict(id) do update set public=false,file_size_limit=52428800;

-- DAISY SaaS foundation: tenant-owned projects, datasets, runs and artifacts.
-- All public tables use RLS. The browser receives no access through the anon role.

create extension if not exists pgcrypto with schema extensions;

create schema if not exists private;
revoke all on schema private from public, anon, authenticated;

create table public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  email text,
  display_name text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.workspaces (
  id uuid primary key default gen_random_uuid(),
  name text not null check (char_length(name) between 1 and 100),
  owner_id uuid not null references public.profiles(id) on delete restrict,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.workspace_members (
  workspace_id uuid not null references public.workspaces(id) on delete cascade,
  user_id uuid not null references public.profiles(id) on delete cascade,
  role text not null default 'member' check (role in ('owner', 'admin', 'member', 'viewer')),
  created_at timestamptz not null default now(),
  primary key (workspace_id, user_id)
);

create table public.projects (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces(id) on delete cascade,
  name text not null check (char_length(name) between 1 and 120),
  description text,
  created_by uuid not null references public.profiles(id) on delete restrict,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.datasets (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.projects(id) on delete cascade,
  uploaded_by uuid not null references public.profiles(id) on delete restrict,
  filename text not null,
  storage_bucket text not null default 'datasets' check (storage_bucket = 'datasets'),
  storage_path text not null unique,
  byte_size bigint not null check (byte_size between 1 and 52428800),
  row_count bigint check (row_count is null or row_count >= 0),
  column_count integer check (column_count is null or column_count >= 0),
  schema_report jsonb not null default '{}'::jsonb,
  dataset_fingerprint text,
  status text not null default 'uploaded' check (status in ('uploading', 'uploaded', 'processing', 'ready', 'failed', 'deleted')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.pipeline_runs (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.projects(id) on delete cascade,
  dataset_id uuid not null references public.datasets(id) on delete cascade,
  created_by uuid not null references public.profiles(id) on delete restrict,
  status text not null default 'queued' check (status in ('queued', 'running', 'completed', 'partial', 'failed', 'cancelled')),
  current_stage text,
  target_column text,
  test_size double precision check (test_size is null or (test_size > 0 and test_size < 1)),
  random_state integer not null default 42,
  configuration jsonb not null default '{}'::jsonb,
  error_message text,
  started_at timestamptz,
  completed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.experiments (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.projects(id) on delete cascade,
  run_id uuid not null references public.pipeline_runs(id) on delete cascade,
  model_name text not null,
  problem_type text not null check (problem_type in ('classification', 'regression')),
  status text not null check (status in ('success', 'failed')),
  is_winner boolean not null default false,
  metrics jsonb not null default '{}'::jsonb,
  parameters jsonb not null default '{}'::jsonb,
  training_time_seconds double precision,
  created_at timestamptz not null default now()
);

create unique index experiments_one_winner_per_run
  on public.experiments(run_id) where is_winner;

create table public.model_artifacts (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.projects(id) on delete cascade,
  run_id uuid not null references public.pipeline_runs(id) on delete cascade,
  experiment_id uuid references public.experiments(id) on delete set null,
  created_by uuid not null references public.profiles(id) on delete restrict,
  filename text not null,
  storage_bucket text not null default 'model-artifacts' check (storage_bucket = 'model-artifacts'),
  storage_path text not null unique,
  byte_size bigint not null check (byte_size between 1 and 52428800),
  checksum_sha256 text not null,
  metadata jsonb not null default '{}'::jsonb,
  expires_at timestamptz,
  created_at timestamptz not null default now()
);

create table public.usage_events (
  id bigint generated always as identity primary key,
  workspace_id uuid not null references public.workspaces(id) on delete cascade,
  user_id uuid not null references public.profiles(id) on delete restrict,
  event_type text not null check (event_type in ('dataset_upload', 'training_run', 'storage_bytes', 'model_download')),
  quantity bigint not null default 1 check (quantity >= 0),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index workspace_members_user_idx on public.workspace_members(user_id);
create index projects_workspace_idx on public.projects(workspace_id, created_at desc);
create index datasets_project_idx on public.datasets(project_id, created_at desc);
create index pipeline_runs_project_idx on public.pipeline_runs(project_id, created_at desc);
create index pipeline_runs_dataset_idx on public.pipeline_runs(dataset_id);
create index experiments_run_idx on public.experiments(run_id);
create index model_artifacts_run_idx on public.model_artifacts(run_id);
create index usage_events_workspace_idx on public.usage_events(workspace_id, created_at desc);

create or replace function private.is_workspace_member(requested_workspace_id uuid)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1 from public.workspace_members
    where workspace_id = requested_workspace_id
      and user_id = auth.uid()
  );
$$;

create or replace function private.can_manage_workspace(requested_workspace_id uuid)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1 from public.workspace_members
    where workspace_id = requested_workspace_id
      and user_id = auth.uid()
      and role in ('owner', 'admin')
  );
$$;

grant usage on schema private to authenticated;
grant execute on function private.is_workspace_member(uuid) to authenticated;
grant execute on function private.can_manage_workspace(uuid) to authenticated;

create or replace function private.set_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create trigger profiles_set_updated_at before update on public.profiles
for each row execute function private.set_updated_at();
create trigger workspaces_set_updated_at before update on public.workspaces
for each row execute function private.set_updated_at();
create trigger projects_set_updated_at before update on public.projects
for each row execute function private.set_updated_at();
create trigger datasets_set_updated_at before update on public.datasets
for each row execute function private.set_updated_at();
create trigger pipeline_runs_set_updated_at before update on public.pipeline_runs
for each row execute function private.set_updated_at();

create or replace function private.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  personal_workspace_id uuid;
  chosen_name text;
begin
  chosen_name := coalesce(nullif(new.raw_user_meta_data ->> 'display_name', ''), split_part(coalesce(new.email, 'DAISY user'), '@', 1));
  insert into public.profiles (id, email, display_name)
  values (new.id, new.email, chosen_name);

  insert into public.workspaces (name, owner_id)
  values (chosen_name || '''s workspace', new.id)
  returning id into personal_workspace_id;

  insert into public.workspace_members (workspace_id, user_id, role)
  values (personal_workspace_id, new.id, 'owner');
  return new;
end;
$$;

create trigger on_auth_user_created
after insert on auth.users
for each row execute function private.handle_new_user();

alter table public.profiles enable row level security;
alter table public.workspaces enable row level security;
alter table public.workspace_members enable row level security;
alter table public.projects enable row level security;
alter table public.datasets enable row level security;
alter table public.pipeline_runs enable row level security;
alter table public.experiments enable row level security;
alter table public.model_artifacts enable row level security;
alter table public.usage_events enable row level security;

revoke all on all tables in schema public from anon;
grant select, update on public.profiles to authenticated;
grant select on public.workspaces, public.workspace_members to authenticated;
grant select, insert, update, delete on public.projects to authenticated;
grant select, insert, update, delete on public.datasets to authenticated;
grant select, insert, update, delete on public.pipeline_runs to authenticated;
grant select on public.experiments, public.model_artifacts, public.usage_events to authenticated;

create policy profiles_select_self on public.profiles
for select to authenticated using (id = auth.uid());
create policy profiles_update_self on public.profiles
for update to authenticated using (id = auth.uid()) with check (id = auth.uid());

create policy workspaces_select_member on public.workspaces
for select to authenticated using (private.is_workspace_member(id));

create policy members_select_member on public.workspace_members
for select to authenticated using (private.is_workspace_member(workspace_id));

create policy projects_select_member on public.projects
for select to authenticated using (private.is_workspace_member(workspace_id));
create policy projects_insert_member on public.projects
for insert to authenticated with check (
  private.is_workspace_member(workspace_id) and created_by = auth.uid()
);
create policy projects_update_manager on public.projects
for update to authenticated using (private.can_manage_workspace(workspace_id))
with check (private.can_manage_workspace(workspace_id));
create policy projects_delete_manager on public.projects
for delete to authenticated using (private.can_manage_workspace(workspace_id));

create policy datasets_select_member on public.datasets
for select to authenticated using (
  exists (select 1 from public.projects p where p.id = project_id and private.is_workspace_member(p.workspace_id))
);
create policy datasets_insert_member on public.datasets
for insert to authenticated with check (
  uploaded_by = auth.uid() and
  exists (select 1 from public.projects p where p.id = project_id and private.is_workspace_member(p.workspace_id))
);
create policy datasets_update_member on public.datasets
for update to authenticated using (
  exists (select 1 from public.projects p where p.id = project_id and private.is_workspace_member(p.workspace_id))
);
create policy datasets_delete_manager on public.datasets
for delete to authenticated using (
  exists (select 1 from public.projects p where p.id = project_id and private.can_manage_workspace(p.workspace_id))
);

create policy runs_select_member on public.pipeline_runs
for select to authenticated using (
  exists (select 1 from public.projects p where p.id = project_id and private.is_workspace_member(p.workspace_id))
);
create policy runs_insert_member on public.pipeline_runs
for insert to authenticated with check (
  created_by = auth.uid() and
  exists (select 1 from public.projects p where p.id = project_id and private.is_workspace_member(p.workspace_id))
);
create policy runs_update_creator on public.pipeline_runs
for update to authenticated using (
  created_by = auth.uid() and
  exists (select 1 from public.projects p where p.id = project_id and private.is_workspace_member(p.workspace_id))
);
create policy runs_delete_manager on public.pipeline_runs
for delete to authenticated using (
  exists (select 1 from public.projects p where p.id = project_id and private.can_manage_workspace(p.workspace_id))
);

create policy experiments_select_member on public.experiments
for select to authenticated using (
  exists (select 1 from public.projects p where p.id = project_id and private.is_workspace_member(p.workspace_id))
);

create policy artifacts_select_member on public.model_artifacts
for select to authenticated using (
  exists (select 1 from public.projects p where p.id = project_id and private.is_workspace_member(p.workspace_id))
);

create policy usage_select_member on public.usage_events
for select to authenticated using (private.is_workspace_member(workspace_id));

comment on table public.datasets is 'Metadata only. CSV bytes live in the private datasets Storage bucket.';
comment on table public.model_artifacts is 'Metadata only. ZIP bytes live in the private model-artifacts Storage bucket.';

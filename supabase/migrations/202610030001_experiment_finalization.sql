-- Apply before running the upgraded backend with Supabase persistence.
alter table public.daisy_resources drop constraint daisy_resources_kind_check;
alter table public.daisy_resources add constraint daisy_resources_kind_check
  check (kind in ('dataset','artifact','run','preferences','experiment'));

create function private.protect_experiment_record() returns trigger
language plpgsql set search_path = '' as $$
begin
  if old.kind = 'experiment' then
    raise exception 'Experiment records are immutable';
  end if;
  return new;
end;
$$;
create trigger experiments_immutable before update on public.daisy_resources
  for each row execute function private.protect_experiment_record();

create table public.daisy_finalizations (
  source_id text not null references public.daisy_resources(id) on delete cascade,
  owner_id uuid not null references auth.users(id) on delete cascade,
  experiment_id text not null references public.daisy_resources(id) on delete cascade,
  report jsonb,
  created_at timestamptz not null default now(),
  primary key (source_id,owner_id)
);
alter table public.daisy_finalizations enable row level security;
revoke all on public.daisy_finalizations from anon,authenticated;
grant select on public.daisy_finalizations to authenticated;
create policy finalizations_select_owner on public.daisy_finalizations
  for select to authenticated using (owner_id = auth.uid());

create function public.daisy_claim_finalization(p_source text,p_owner uuid,p_experiment text)
returns jsonb language plpgsql security definer set search_path = '' as $$
declare selected public.daisy_finalizations;
begin
  if not exists (select 1 from public.daisy_resources where id=p_source and owner_id=p_owner and kind='dataset')
     or not exists (select 1 from public.daisy_resources where id=p_experiment and owner_id=p_owner and kind='experiment' and metadata->>'source_dataset_id'=p_source) then
    raise exception 'Invalid experiment ownership or source';
  end if;
  insert into public.daisy_finalizations(source_id,owner_id,experiment_id)
    values(p_source,p_owner,p_experiment) on conflict do nothing;
  select * into selected from public.daisy_finalizations where source_id=p_source and owner_id=p_owner;
  return jsonb_build_object('experiment_id',selected.experiment_id,'report',selected.report);
end;
$$;

create function public.daisy_finish_finalization(p_source text,p_owner uuid,p_experiment text,p_report jsonb)
returns jsonb language plpgsql security definer set search_path = '' as $$
declare selected public.daisy_finalizations;
begin
  select * into selected from public.daisy_finalizations where source_id=p_source and owner_id=p_owner for update;
  if selected.experiment_id is distinct from p_experiment then
    raise exception 'Finalization does not match claimed experiment';
  end if;
  if selected.report is null then
    update public.daisy_finalizations set report=p_report where source_id=p_source and owner_id=p_owner;
    return p_report;
  end if;
  return selected.report;
end;
$$;
revoke all on function public.daisy_claim_finalization(text,uuid,text) from public,anon,authenticated;
revoke all on function public.daisy_finish_finalization(text,uuid,text,jsonb) from public,anon,authenticated;
grant execute on function public.daisy_claim_finalization(text,uuid,text) to service_role;
grant execute on function public.daisy_finish_finalization(text,uuid,text,jsonb) to service_role;

create table public.daisy_prediction_usage (
  id bigint generated always as identity primary key,
  owner_id uuid not null references auth.users(id) on delete cascade,
  created_at timestamptz not null default now(),
  rows integer not null check (rows between 1 and 10000)
);
create index prediction_usage_owner_created on public.daisy_prediction_usage(owner_id,created_at);
alter table public.daisy_prediction_usage enable row level security;
revoke all on public.daisy_prediction_usage from anon,authenticated;
grant select on public.daisy_prediction_usage to authenticated;
create policy prediction_usage_owner on public.daisy_prediction_usage
  for select to authenticated using (owner_id=auth.uid());
create function public.daisy_reserve_prediction(p_owner uuid,p_rows integer)
returns jsonb language plpgsql security definer set search_path = '' as $$
declare calls integer; total_rows integer;
begin
  if p_rows < 1 or p_rows > 10000 then raise exception 'Invalid prediction row count'; end if;
  perform pg_advisory_xact_lock(hashtextextended('prediction-' || p_owner::text,0));
  delete from public.daisy_prediction_usage where created_at < now() - interval '1 day';
  select count(*),coalesce(sum(rows),0) into calls,total_rows
    from public.daisy_prediction_usage where owner_id=p_owner;
  if calls >= 100 or total_rows+p_rows > 100000 then
    return jsonb_build_object('accepted',false);
  end if;
  insert into public.daisy_prediction_usage(owner_id,rows) values(p_owner,p_rows);
  return jsonb_build_object('accepted',true);
end;
$$;
revoke all on function public.daisy_reserve_prediction(uuid,integer) from public,anon,authenticated;
grant execute on function public.daisy_reserve_prediction(uuid,integer) to service_role;

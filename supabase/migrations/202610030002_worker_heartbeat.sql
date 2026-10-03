create table public.daisy_worker_heartbeats (
  worker_id text primary key,
  seen_at timestamptz not null default now(),
  status text not null check (status in ('idle','running','stopped'))
);
alter table public.daisy_worker_heartbeats enable row level security;
revoke all on public.daisy_worker_heartbeats from anon,authenticated;

create function public.daisy_worker_heartbeat(p_worker text,p_status text)
returns void language plpgsql security definer set search_path = '' as $$
begin
  delete from public.daisy_worker_heartbeats where seen_at < now() - interval '1 day';
  insert into public.daisy_worker_heartbeats(worker_id,seen_at,status) values(p_worker,now(),p_status)
    on conflict(worker_id) do update set seen_at=excluded.seen_at,status=excluded.status;
end;
$$;
create function public.daisy_worker_ready(p_worker text default null) returns boolean
language sql security definer set search_path = '' as $$
  select exists(select 1 from public.daisy_worker_heartbeats
    where seen_at > now() - interval '90 seconds' and status in ('idle','running') and (p_worker is null or worker_id=p_worker));
$$;
revoke all on function public.daisy_worker_heartbeat(text,text) from public,anon,authenticated;
revoke all on function public.daisy_worker_ready(text) from public,anon,authenticated;
grant execute on function public.daisy_worker_heartbeat(text,text) to service_role;
grant execute on function public.daisy_worker_ready(text) to service_role;

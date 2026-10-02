create table public.daisy_training_jobs (
 id uuid primary key default gen_random_uuid(),
 owner_id uuid not null references auth.users(id) on delete cascade,
 idempotency_key text not null,
 signature text not null,
 payload jsonb not null,
 status text not null default 'queued' check(status in ('queued','running','completed','failed','cancelled')),
 created_at timestamptz not null default now(),
 lease_until timestamptz,
 result jsonb,
 error text,
 unique(owner_id,idempotency_key)
);
create index training_jobs_queue on public.daisy_training_jobs(status,created_at);
alter table public.daisy_training_jobs enable row level security;
revoke all on public.daisy_training_jobs from anon,authenticated;
grant select on public.daisy_training_jobs to authenticated;
create policy training_jobs_select_owner on public.daisy_training_jobs for select to authenticated using(owner_id=auth.uid());
grant all on public.daisy_training_jobs,public.daisy_resources to service_role;

create function public.daisy_enqueue_training(requested_owner uuid,requested_key text,requested_signature text,requested_payload jsonb)
returns jsonb language plpgsql security definer set search_path='' as $$
declare existing public.daisy_training_jobs; created public.daisy_training_jobs;
begin
 -- A short transaction lock also bounds total queued work across owners.
 perform pg_advisory_xact_lock(20261002);
 select * into existing from public.daisy_training_jobs where owner_id=requested_owner and idempotency_key=requested_key;
 if found then
   if existing.signature<>requested_signature then return jsonb_build_object('error','Idempotency key was used for a different request','status',409); end if;
   return to_jsonb(existing);
 end if;
 if (select count(*) from public.daisy_training_jobs where owner_id=requested_owner and status in ('queued','running'))>=2
 or (select count(*) from public.daisy_training_jobs where owner_id=requested_owner and created_at>now()-interval '24 hours')>=10
 or (select count(*) from public.daisy_training_jobs where status in ('queued','running'))>=100 then
   return jsonb_build_object('error','Training quota reached. Wait for active jobs or try again tomorrow.','status',429);
 end if;
 insert into public.daisy_training_jobs(owner_id,idempotency_key,signature,payload) values(requested_owner,requested_key,requested_signature,requested_payload) returning * into created;
 return to_jsonb(created);
end $$;

create function public.daisy_claim_training() returns jsonb language plpgsql security definer set search_path='' as $$
declare claimed public.daisy_training_jobs;
begin
 update public.daisy_training_jobs set status='failed',error='Worker lease expired. Submit a new job.' where status='running' and lease_until<now();
 update public.daisy_training_jobs set status='running',lease_until=now()+interval '660 seconds'
 where id=(select id from public.daisy_training_jobs where status='queued' order by created_at for update skip locked limit 1)
 returning * into claimed;
 if not found then return null; end if;
 return to_jsonb(claimed);
end $$;
revoke all on function public.daisy_enqueue_training(uuid,text,text,jsonb) from public,anon,authenticated;
revoke all on function public.daisy_claim_training() from public,anon,authenticated;
grant execute on function public.daisy_enqueue_training(uuid,text,text,jsonb) to service_role;
grant execute on function public.daisy_claim_training() to service_role;

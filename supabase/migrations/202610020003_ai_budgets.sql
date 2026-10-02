create table public.daisy_ai_usage (
 id uuid primary key default gen_random_uuid(),
 owner_id uuid not null references auth.users(id) on delete cascade,
 created_at timestamptz not null default now(),
 tokens bigint not null check(tokens>=0)
);
create index ai_usage_owner_time on public.daisy_ai_usage(owner_id,created_at);
alter table public.daisy_ai_usage enable row level security;
revoke all on public.daisy_ai_usage from anon,authenticated;
grant select on public.daisy_ai_usage to authenticated;
grant all on public.daisy_ai_usage to service_role;
create policy ai_usage_select_owner on public.daisy_ai_usage for select to authenticated using(owner_id=auth.uid());
create function public.daisy_reserve_ai(requested_owner uuid,requested_tokens bigint)
returns jsonb language plpgsql security definer set search_path='' as $$
declare calls bigint; spent bigint; identifier uuid;
begin
 if requested_tokens<0 or requested_tokens>200000 then raise exception 'Invalid token reservation'; end if;
 perform pg_advisory_xact_lock(hashtextextended(requested_owner::text,0));
 select count(*),coalesce(sum(tokens),0) into calls,spent from public.daisy_ai_usage where owner_id=requested_owner and created_at>now()-interval '24 hours';
 if calls>=100 or spent+requested_tokens>200000 then return jsonb_build_object('error','AI budget exhausted'); end if;
 insert into public.daisy_ai_usage(owner_id,tokens) values(requested_owner,requested_tokens) returning id into identifier;
 return jsonb_build_object('id',identifier);
end $$;
revoke all on function public.daisy_reserve_ai(uuid,bigint) from public,anon,authenticated;
grant execute on function public.daisy_reserve_ai(uuid,bigint) to service_role;

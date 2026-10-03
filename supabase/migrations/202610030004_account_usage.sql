-- Aggregate only the authenticated owner's usage. API passes its verified owner.
create function public.daisy_account_usage(p_owner uuid)
returns jsonb language sql stable security definer set search_path = '' as $$
select jsonb_build_object(
  'ai', (select jsonb_build_object('requests',count(*),'tokens',coalesce(sum(tokens),0),
             'next_expiry',min(created_at)+interval '1 day')
           from public.daisy_ai_usage where owner_id=p_owner and created_at>now()-interval '1 day'),
  'inference', (select jsonb_build_object('requests',count(*),'scored_rows',coalesce(sum(rows),0),
             'next_expiry',min(created_at)+interval '1 day')
           from public.daisy_prediction_usage where owner_id=p_owner and created_at>now()-interval '1 day'),
  'training', (select jsonb_build_object('requests',count(*) filter (where created_at>now()-interval '1 day'),
             'active_jobs',count(*) filter (where status in ('queued','running')),
             'next_expiry',min(created_at) filter (where created_at>now()-interval '1 day')+interval '1 day')
           from public.daisy_training_jobs where owner_id=p_owner)
);
$$;
revoke all on function public.daisy_account_usage(uuid) from public,anon,authenticated;
grant execute on function public.daisy_account_usage(uuid) to service_role;

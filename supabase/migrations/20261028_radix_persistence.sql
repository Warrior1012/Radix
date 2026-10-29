-- Optional persistence tables for RADIX Talent Match integration.
-- This migration does not alter the existing company or skill benchmark tables.
-- The Role 1 jd_analytics_results table is created by the original Role 1 migration.

create table if not exists public.radix_candidate_profiles (
  candidate_id text primary key,
  profile jsonb not null check (jsonb_typeof(profile) = 'object'),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.radix_talent_check_results (
  id uuid primary key default gen_random_uuid(),
  candidate_id text,
  company_id bigint not null,
  result jsonb not null check (jsonb_typeof(result) = 'object'),
  created_at timestamptz not null default now()
);

create table if not exists public.radix_skill_match_results (
  id uuid primary key default gen_random_uuid(),
  candidate_id text,
  job_id text,
  company_id bigint,
  result jsonb not null check (jsonb_typeof(result) = 'object'),
  created_at timestamptz not null default now()
);

create index if not exists radix_candidate_profiles_updated_idx
  on public.radix_candidate_profiles (updated_at desc);
create index if not exists radix_talent_check_candidate_idx
  on public.radix_talent_check_results (candidate_id, created_at desc);
create index if not exists radix_skill_match_candidate_idx
  on public.radix_skill_match_results (candidate_id, created_at desc);

alter table public.radix_candidate_profiles enable row level security;
alter table public.radix_talent_check_results enable row level security;
alter table public.radix_skill_match_results enable row level security;
revoke all on public.radix_candidate_profiles from anon, authenticated;
revoke all on public.radix_talent_check_results from anon, authenticated;
revoke all on public.radix_skill_match_results from anon, authenticated;
grant select, insert, update, delete on public.radix_candidate_profiles to service_role;
grant select, insert, update, delete on public.radix_talent_check_results to service_role;
grant select, insert, update, delete on public.radix_skill_match_results to service_role;

create or replace function public.radix_set_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists radix_candidate_profiles_updated_at on public.radix_candidate_profiles;
create trigger radix_candidate_profiles_updated_at
before update on public.radix_candidate_profiles
for each row execute function public.radix_set_updated_at();

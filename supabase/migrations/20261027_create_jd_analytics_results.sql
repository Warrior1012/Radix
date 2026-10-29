create table if not exists public.jd_analytics_results (
  id uuid primary key default gen_random_uuid(),
  source_type text not null default 'jd' check (source_type = 'jd'),
  source_file text not null,
  company text,
  role text,
  skills jsonb not null default '[]'::jsonb check (jsonb_typeof(skills) = 'array'),
  extraction_method text not null default 'llm',
  created_at timestamptz not null default now()
);

alter table public.jd_analytics_results enable row level security;
revoke all on table public.jd_analytics_results from anon, authenticated;
grant select, insert, update, delete on table public.jd_analytics_results to service_role;

comment on table public.jd_analytics_results is 'RADIX Talent Match Role 1: structured skills extracted from job descriptions. Access via trusted backend only.';
comment on column public.jd_analytics_results.skills is 'Array of shared-contract skill objects: skill_name, category_code, evidence, confidence.';

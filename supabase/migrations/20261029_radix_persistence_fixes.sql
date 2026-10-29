-- Additive, idempotent follow-up to 20261028_radix_persistence.sql (safe to run more than once).
-- Phase 4 review finding: the API may store a talent-check result for a Supabase-sourced company whose id is not
-- numeric (company_id resolves to NULL), which the original NOT NULL constraint would reject.
alter table public.radix_talent_check_results alter column company_id drop not null;
-- Keep the exact selected company reference (e.g. 'snapshot:4' or 'supabase:9001') alongside the numeric id.
alter table public.radix_talent_check_results add column if not exists company_ref text;

-- =============================================================
-- Migration Central Acervo TI v2
-- Execute no SQL Editor do Supabase (dashboard -> SQL Editor)
-- =============================================================

-- 1. Novo status 'trial' na tabela colegios (se o enum ainda não tiver)
alter table public.colegios
  add column if not exists observacoes text,
  add column if not exists telefone text,
  add column if not exists responsavel text;

-- 2. Tabela de auditoria de ações administrativas
create table if not exists public.auditoria_admin (
    id uuid primary key default gen_random_uuid(),
    admin_user_id uuid not null,
    admin_email text,
    colegio_id uuid,
    acao text not null,
    detalhe jsonb,
    criado_em timestamptz not null default now()
);

alter table public.auditoria_admin enable row level security;

drop policy if exists "auditoria_admin_select" on public.auditoria_admin;

create policy "auditoria_admin_select"
  on public.auditoria_admin for select
  to authenticated
  using (true);

-- 3. Índice para consultas de histórico
create index if not exists idx_auditoria_admin_colegio
  on public.auditoria_admin (colegio_id, criado_em desc);

-- 4. Relaxa UNIQUE da licenca para permitir regerar chave do mesmo serial
--    (remove unique de chave+serial; serial já é único por colegio)
alter table public.licencas
  drop constraint if exists licencas_chave_ativacao_serial_pdv_key;

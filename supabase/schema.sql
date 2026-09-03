-- =====================================================
-- SUPABASE - SCHEMA PARA MULTI-TENANCY E LICENÇAS
-- =====================================================

create extension if not exists pgcrypto;

create type public.assinatura_status as enum (
  'pendente',
  'ativo',
  'trial',
  'cancelado',
  'bloqueado'
);

create type public.licenca_status as enum (
  'pendente',
  'ativa',
  'expirada',
  'bloqueada',
  'cancelada'
);

create type public.user_role as enum (
  'admin_geral',
  'gestor_colegio',
  'tecnico_ti',
  'professor'
);

create table public.colegios (
    id uuid primary key default gen_random_uuid(),
    nome text not null,
    cnpj text,
    email text,
    status_assinatura public.assinatura_status not null default 'pendente',
    data_expiracao timestamptz,
    criado_em timestamptz not null default now(),
    tenant_id uuid generated always as (id) stored
);

create table public.licencas (
    id uuid primary key default gen_random_uuid(),
    colegio_id uuid not null references public.colegios(id) on delete cascade,
    tenant_id uuid generated always as (colegio_id) stored,
    chave_ativacao text not null,
    serial_pdv text not null,
    status public.licenca_status not null default 'pendente',
    ultima_checagem timestamptz,
    criado_em timestamptz not null default now(),
    atualizado_em timestamptz not null default now(),
    unique (colegio_id, serial_pdv),
    unique (chave_ativacao, serial_pdv)
);

create table public.perfis (
    id uuid primary key references auth.users(id) on delete cascade,
    colegio_id uuid not null references public.colegios(id) on delete cascade,
    tenant_id uuid generated always as (colegio_id) stored,
    papel public.user_role not null default 'professor',
    nome text,
    telefone text,
    avatar_url text,
    criado_em timestamptz not null default now()
);

create table public.pdv_devices (
    id uuid primary key default gen_random_uuid(),
    colegio_id uuid not null references public.colegios(id) on delete cascade,
    tenant_id uuid generated always as (colegio_id) stored,
    serial_pdv text not null unique,
    nome_dispositivo text,
    status text not null default 'ativo',
    ultimo_checkin timestamptz,
    criado_em timestamptz not null default now()
);

create table public.pagamentos (
    id uuid primary key default gen_random_uuid(),
    colegio_id uuid not null references public.colegios(id) on delete cascade,
    tenant_id uuid generated always as (colegio_id) stored,
    gateway text not null,
    referencia text not null,
    valor numeric(10,2) not null,
    status text not null default 'pendente',
    payload jsonb,
    criado_em timestamptz not null default now()
);

create or replace function public.current_user_colegio_id()
returns uuid
language sql
stable
security definer
as $$
    select colegio_id
    from public.perfis
    where id = auth.uid()
    limit 1;
$$;

create or replace function public.user_has_role(_papel public.user_role)
returns boolean
language sql
stable
security definer
as $$
    select exists (
        select 1
        from public.perfis
        where id = auth.uid()
          and papel = _papel
    );
$$;

alter table public.colegios enable row level security;
alter table public.licencas enable row level security;
alter table public.perfis enable row level security;
alter table public.pdv_devices enable row level security;
alter table public.pagamentos enable row level security;

create policy "colegios_select" on public.colegios for select to authenticated using (id = public.current_user_colegio_id() or public.user_has_role('admin_geral'));
create policy "colegios_update" on public.colegios for update to authenticated using (id = public.current_user_colegio_id() or public.user_has_role('admin_geral')) with check (id = public.current_user_colegio_id() or public.user_has_role('admin_geral'));
create policy "colegios_insert" on public.colegios for insert to authenticated with check (public.user_has_role('admin_geral'));

create policy "licencas_select" on public.licencas for select to authenticated using (colegio_id = public.current_user_colegio_id() or public.user_has_role('admin_geral'));
create policy "licencas_insert" on public.licencas for insert to authenticated with check (colegio_id = public.current_user_colegio_id() or public.user_has_role('admin_geral'));
create policy "licencas_update" on public.licencas for update to authenticated using (colegio_id = public.current_user_colegio_id() or public.user_has_role('admin_geral')) with check (colegio_id = public.current_user_colegio_id() or public.user_has_role('admin_geral'));

create policy "perfis_select" on public.perfis for select to authenticated using (colegio_id = public.current_user_colegio_id() or public.user_has_role('admin_geral'));
create policy "perfis_insert" on public.perfis for insert to authenticated with check (colegio_id = public.current_user_colegio_id() or public.user_has_role('admin_geral'));
create policy "perfis_update" on public.perfis for update to authenticated using (id = auth.uid() or colegio_id = public.current_user_colegio_id() or public.user_has_role('admin_geral')) with check (id = auth.uid() or colegio_id = public.current_user_colegio_id() or public.user_has_role('admin_geral'));

create policy "pdv_select" on public.pdv_devices for select to authenticated using (colegio_id = public.current_user_colegio_id() or public.user_has_role('admin_geral'));
create policy "pdv_insert" on public.pdv_devices for insert to authenticated with check (colegio_id = public.current_user_colegio_id() or public.user_has_role('admin_geral'));
create policy "pdv_update" on public.pdv_devices for update to authenticated using (colegio_id = public.current_user_colegio_id() or public.user_has_role('admin_geral')) with check (colegio_id = public.current_user_colegio_id() or public.user_has_role('admin_geral'));

create policy "pagamentos_select" on public.pagamentos for select to authenticated using (colegio_id = public.current_user_colegio_id() or public.user_has_role('admin_geral'));
create policy "pagamentos_insert" on public.pagamentos for insert to authenticated with check (colegio_id = public.current_user_colegio_id() or public.user_has_role('admin_geral'));

create or replace function public.set_updated_at()
returns trigger as $$
begin
    new.atualizado_em = now();
    return new;
end;
$$ language plpgsql;

create trigger trg_licencas_updated_at
before update on public.licencas
for each row execute function public.set_updated_at();

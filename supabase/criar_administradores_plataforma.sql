-- Define quem pode usar a Central Acervo TI para criar novos clientes.
-- Execute uma vez no SQL Editor do Supabase.

create table if not exists public.administradores_plataforma (
    user_id uuid primary key references auth.users(id) on delete cascade,
    nome text not null,
    criado_em timestamptz not null default now()
);

alter table public.administradores_plataforma enable row level security;

-- Nenhum usuário autenticado pode consultar ou alterar essa lista diretamente.
-- Apenas as Edge Functions, usando a chave protegida no servidor, a utilizam.

insert into public.administradores_plataforma (user_id, nome)
values (
    '6c5c09f8-f663-4a69-8b99-4a53b26331e6',
    'Administrador da Plataforma'
)
on conflict (user_id) do nothing;
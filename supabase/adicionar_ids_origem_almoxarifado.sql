-- Prepara produtos e movimentacoes locais para sincronizacao multi-tenant.
-- Execute uma vez antes de ativar a fila do almoxarifado.

alter table public.almox_produtos add column if not exists source_id text;
update public.almox_produtos set source_id = id::text where source_id is null;
alter table public.almox_produtos alter column source_id set not null;
alter table public.almox_produtos
    add constraint almox_produtos_source_id_key unique (colegio_id, source_id);

alter table public.almox_movimentacoes
    drop constraint if exists almox_movimentacoes_produto_id_fkey;
alter table public.almox_movimentacoes add column if not exists source_id text;
alter table public.almox_movimentacoes add column if not exists produto_source_id text;
update public.almox_movimentacoes
set source_id = id::text,
    produto_source_id = produto_id::text
where source_id is null or produto_source_id is null;
alter table public.almox_movimentacoes alter column source_id set not null;
alter table public.almox_movimentacoes alter column produto_source_id set not null;
alter table public.almox_movimentacoes
    add constraint almox_movimentacoes_source_id_key unique (colegio_id, source_id);
alter table public.almox_movimentacoes
    add constraint almox_movimentacoes_produto_source_fkey
    foreign key (colegio_id, produto_source_id)
    references public.almox_produtos(colegio_id, source_id)
    on delete restrict;
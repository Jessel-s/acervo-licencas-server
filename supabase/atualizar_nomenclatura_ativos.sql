-- Atualiza a estrutura operacional ja criada no Supabase.
-- Execute uma vez, antes de migrar os ativos de teste.

alter table public.notebooks rename to ativos;
alter table public.problemas rename column notebook_id to ativo_id;
alter index if exists public.idx_notebooks_colegio rename to idx_ativos_colegio;
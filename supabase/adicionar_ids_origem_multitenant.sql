-- Evita colisao de IDs autoincrementais gerados nos bancos SQLite de tenants diferentes.
-- Execute uma vez antes de sincronizar novas sessoes, chamados, historicos ou agendamentos.

alter table public.sessoes_uso add column if not exists source_id text;
update public.sessoes_uso set source_id = id::text where source_id is null;
alter table public.sessoes_uso alter column source_id set not null;
alter table public.sessoes_uso add constraint sessoes_uso_source_id_key unique (colegio_id, source_id);

alter table public.problemas add column if not exists source_id text;
update public.problemas set source_id = id::text where source_id is null;
alter table public.problemas alter column source_id set not null;
alter table public.problemas add constraint problemas_source_id_key unique (colegio_id, source_id);

alter table public.historico add column if not exists source_id text;
update public.historico set source_id = id::text where source_id is null;
alter table public.historico alter column source_id set not null;
alter table public.historico add constraint historico_source_id_key unique (colegio_id, source_id);

alter table public.agendamentos add column if not exists source_id text;
update public.agendamentos set source_id = id::text where source_id is null;
alter table public.agendamentos alter column source_id set not null;
alter table public.agendamentos add constraint agendamentos_source_id_key unique (colegio_id, source_id);
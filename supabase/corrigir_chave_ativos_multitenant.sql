-- Corrige a chave de ativos para permitir o mesmo patrimonio em tenants diferentes.
-- Execute uma vez antes de sincronizar ativos locais.

do $$
declare
        constraint_to_drop text;
begin
        for constraint_to_drop in
                select constraints.constraint_name
                from information_schema.table_constraints as constraints
                where constraints.table_schema = 'public'
                    and constraints.table_name = 'problemas'
                    and constraints.constraint_type = 'FOREIGN KEY'
    loop
                execute format('alter table public.problemas drop constraint %I', constraint_to_drop);
    end loop;

        select constraints.conname into constraint_to_drop
        from pg_constraint as constraints
        where constraints.conrelid = 'public.ativos'::regclass
            and constraints.contype = 'p';

        if constraint_to_drop is not null then
                execute format('alter table public.ativos drop constraint %I', constraint_to_drop);
    end if;
end;
$$;

alter table public.ativos
    add primary key (colegio_id, id);

alter table public.problemas
    add constraint problemas_ativo_tenant_fkey
    foreign key (colegio_id, ativo_id)
    references public.ativos(colegio_id, id)
    on delete cascade;
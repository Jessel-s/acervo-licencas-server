-- Corrige as sequencias de IDs apos a importacao de registros com IDs do SQLite.
-- Execute uma vez no SQL Editor do Supabase.

do $$
declare
    table_name text;
    sequence_name text;
    max_id bigint;
begin
    foreach table_name in array array[
        'sessoes_uso',
        'problemas',
        'historico',
        'agendamentos',
        'almox_produtos',
        'almox_movimentacoes'
    ]
    loop
        select pg_get_serial_sequence(format('%I.%I', 'public', table_name), 'id')
        into sequence_name;

        if sequence_name is not null then
            execute format('select max(id) from public.%I', table_name)
            into max_id;

            if max_id is not null then
                perform setval(sequence_name, max_id, true);
            end if;
        end if;
    end loop;
end;
$$;
-- =====================================================
-- DIAGNOSTICO E CORRECAO: "Usuário autenticado sem perfil de acesso"
-- Cliente: Colegio teste CDV / jesse_leitekl@hotmail.com
-- colegio_id: 682806a9-8a3b-43ba-8cd1-dd594e523b17
-- =====================================================

-- 1) Confirma o UUID do usuario no Auth (copie o "id" retornado)
SELECT id, email
FROM auth.users
WHERE email = 'jesse_leitekl@hotmail.com';

-- 2) Verifica se existe (ou nao) o perfil vinculado a este usuario
SELECT *
FROM public.perfis
WHERE id = (SELECT id FROM auth.users WHERE email = 'jesse_leitekl@hotmail.com');

-- 3) Se o passo 2 NAO retornou nenhuma linha, o perfil foi perdido.
--    Este INSERT recria o perfil de admin_geral para o colegio correto.
--    Pode rodar direto: ele busca o id do Auth automaticamente.
INSERT INTO public.perfis (id, colegio_id, papel, nome)
SELECT
    u.id,
    '682806a9-8a3b-43ba-8cd1-dd594e523b17',
    'admin_geral',
    'Jesse silva leite'
FROM auth.users u
WHERE u.email = 'jesse_leitekl@hotmail.com'
ON CONFLICT (id) DO UPDATE
SET colegio_id = EXCLUDED.colegio_id,
    papel = EXCLUDED.papel
RETURNING *;

-- 4) Garante que as policies de SELECT em perfis existem (idempotente).
--    Sem isso, mesmo com o perfil existindo, a leitura pode ser bloqueada.
drop policy if exists "tenant_select" on public.perfis;
drop policy if exists "perfis_select" on public.perfis;
create policy "tenant_select" on public.perfis for select to authenticated
using (colegio_id = public.current_user_colegio_id() or id = auth.uid());

-- =====================================================
-- SEED INICIAL PARA O PRIMEIRO CLIENTE / TENANT
-- =====================================================

-- 1) Cria o colegio/tenant
INSERT INTO public.colegios (
    nome,
    cnpj,
    email,
    status_assinatura,
    data_expiracao
)
VALUES (
    'Escola Exemplo',
    '00000000000000',
    'contato@escola.com',
    'ativo',
    NOW() + interval '30 days'
)
RETURNING *;

-- 2) Cria a licença do PDV
-- Substitua o valor do colegio_id pelo UUID retornado na instrução anterior.
INSERT INTO public.licencas (
    colegio_id,
    chave_ativacao,
    serial_pdv,
    status,
    ultima_checagem
)
VALUES (
    'COLEGI0_ID_AQUI',
    'LIC-TESTE-123',
    'PDV-001',
    'ativa',
    NOW()
);

-- 3) Cria um perfil de admin geral para o usuário autenticado
-- Substitua o id pelo UUID do usuário autenticado no Supabase Auth.
INSERT INTO public.perfis (
    id,
    colegio_id,
    papel,
    nome
)
VALUES (
    'USUARIO_AUTH_ID_AQUI',
    'COLEGI0_ID_AQUI',
    'admin_geral',
    'Administrador'
);

-- =====================================================
-- PRIMEIRO TENANT REAL CADASTRADO
-- =====================================================

-- Dados confirmados:
-- colegio_id: 78d55a14-7906-49fc-8cd3-68810bb9b4b1
-- tenant_id: 78d55a14-7906-49fc-8cd3-68810bb9b4b1
-- licenca_id: 42c6d7ad-1929-40b3-a292-7b724672d45c
-- chave_ativacao: LIC-TESTE-123
-- serial_pdv: PDV-001
-- status: ativa
-- ultima_checagem: 2026-08-31 18:44:09.299367+00

-- 1) Verifique se a licença realmente existe
SELECT *
FROM public.licencas
WHERE colegio_id = '78d55a14-7906-49fc-8cd3-68810bb9b4b1'
  AND serial_pdv = 'PDV-001';

-- 2) Se a licença estiver correta, crie o perfil do admin no Auth
-- Troque 'UUID_DO_USUARIO_AUTH' pelo UUID gerado no Supabase Auth.
INSERT INTO public.perfis (
    id,
    colegio_id,
    papel,
    nome,
    telefone
)
VALUES (
  '6c5c09f8-f663-4a69-8b99-4a53b26331e6',
    '78d55a14-7906-49fc-8cd3-68810bb9b4b1',
    'admin_geral',
    'Administrador Principal',
    '(11) 99999-9999'
)
RETURNING *;

-- 3) Outros perfis opcionais para o mesmo colegio
-- INSERT INTO public.perfis (id, colegio_id, papel, nome) VALUES ('uuid', '78d55a14-7906-49fc-8cd3-68810bb9b4b1', 'gestor_colegio', 'Gestor');
-- INSERT INTO public.perfis (id, colegio_id, papel, nome) VALUES ('uuid', '78d55a14-7906-49fc-8cd3-68810bb9b4b1', 'tecnico_ti', 'Técnico');
-- INSERT INTO public.perfis (id, colegio_id, papel, nome) VALUES ('uuid', '78d55a14-7906-49fc-8cd3-68810bb9b4b1', 'professor', 'Professor');


-- =====================================================
-- MIGRACAO PONTUAL - RODAR 1x NO SUPABASE (SQL Editor)
-- Alinha os enums em bases JA EXISTENTES criadas antes da versao atual do
-- schema.sql. Em bases novas isso ja vem pronto no schema.sql e esta
-- migracao simplesmente nao faz nada.
--   assinatura_status: + 'expirado', 'suspenso'
--   licenca_status:    + 'revogada'
-- (idempotente: pode rodar mais de uma vez sem erro)
-- =====================================================

alter type public.assinatura_status add value if not exists 'expirado';
alter type public.assinatura_status add value if not exists 'suspenso';
alter type public.licenca_status add value if not exists 'revogada';

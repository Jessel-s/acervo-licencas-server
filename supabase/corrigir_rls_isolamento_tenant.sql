-- Impede que usuarios autenticados, inclusive admin_geral do colegio,
-- acessem dados de outro tenant. A Edge Function usa service role no servidor.

drop policy if exists "colegios_select" on public.colegios;
drop policy if exists "colegios_update" on public.colegios;
drop policy if exists "colegios_insert" on public.colegios;
drop policy if exists "licencas_select" on public.licencas;
drop policy if exists "licencas_insert" on public.licencas;
drop policy if exists "licencas_update" on public.licencas;
drop policy if exists "perfis_select" on public.perfis;
drop policy if exists "perfis_insert" on public.perfis;
drop policy if exists "perfis_update" on public.perfis;
drop policy if exists "pdv_select" on public.pdv_devices;
drop policy if exists "pdv_insert" on public.pdv_devices;
drop policy if exists "pdv_update" on public.pdv_devices;
drop policy if exists "pagamentos_select" on public.pagamentos;
drop policy if exists "pagamentos_insert" on public.pagamentos;

create policy "tenant_select" on public.colegios for select to authenticated
using (id = public.current_user_colegio_id());
create policy "tenant_update" on public.colegios for update to authenticated
using (id = public.current_user_colegio_id())
with check (id = public.current_user_colegio_id());

create policy "tenant_select" on public.licencas for select to authenticated
using (colegio_id = public.current_user_colegio_id());

create policy "tenant_select" on public.perfis for select to authenticated
using (colegio_id = public.current_user_colegio_id());
create policy "self_update" on public.perfis for update to authenticated
using (id = auth.uid())
with check (id = auth.uid() and colegio_id = public.current_user_colegio_id());

create policy "tenant_select" on public.pdv_devices for select to authenticated
using (colegio_id = public.current_user_colegio_id());

create policy "tenant_select" on public.pagamentos for select to authenticated
using (colegio_id = public.current_user_colegio_id());

drop policy if exists "tenant_access" on public.ativos;
drop policy if exists "tenant_access" on public.configuracoes_sistema;
drop policy if exists "tenant_access" on public.sessoes_uso;
drop policy if exists "tenant_access" on public.problemas;
drop policy if exists "tenant_access" on public.historico;
drop policy if exists "tenant_access" on public.agendamentos;
drop policy if exists "tenant_access" on public.almox_produtos;
drop policy if exists "tenant_access" on public.almox_movimentacoes;

create policy "tenant_access" on public.ativos for all to authenticated
using (colegio_id = public.current_user_colegio_id())
with check (colegio_id = public.current_user_colegio_id());
create policy "tenant_access" on public.configuracoes_sistema for all to authenticated
using (colegio_id = public.current_user_colegio_id())
with check (colegio_id = public.current_user_colegio_id());
create policy "tenant_access" on public.sessoes_uso for all to authenticated
using (colegio_id = public.current_user_colegio_id())
with check (colegio_id = public.current_user_colegio_id());
create policy "tenant_access" on public.problemas for all to authenticated
using (colegio_id = public.current_user_colegio_id())
with check (colegio_id = public.current_user_colegio_id());
create policy "tenant_access" on public.historico for all to authenticated
using (colegio_id = public.current_user_colegio_id())
with check (colegio_id = public.current_user_colegio_id());
create policy "tenant_access" on public.agendamentos for all to authenticated
using (colegio_id = public.current_user_colegio_id())
with check (colegio_id = public.current_user_colegio_id());
create policy "tenant_access" on public.almox_produtos for all to authenticated
using (colegio_id = public.current_user_colegio_id())
with check (colegio_id = public.current_user_colegio_id());
create policy "tenant_access" on public.almox_movimentacoes for all to authenticated
using (colegio_id = public.current_user_colegio_id())
with check (colegio_id = public.current_user_colegio_id());
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
const serviceRoleKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const supabase = createClient(supabaseUrl, serviceRoleKey);
const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, apikey, content-type",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
};

function json(body: Record<string, unknown>, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...corsHeaders },
  });
}

async function requirePlatformAdmin(request: Request) {
  const authorization = request.headers.get("Authorization");
  if (!authorization?.startsWith("Bearer ")) {
    return { error: json({ ok: false, mensagem: "Token de autenticacao ausente" }, 401) };
  }
  const token = authorization.slice("Bearer ".length);
  const { data: authData, error: authError } = await supabase.auth.getUser(token);
  if (authError || !authData.user) {
    return { error: json({ ok: false, mensagem: "Token de autenticacao invalido" }, 401) };
  }
  const { data: platformAdmin, error: platformAdminError } = await supabase
    .from("administradores_plataforma")
    .select("user_id")
    .eq("user_id", authData.user.id)
    .maybeSingle();
  if (platformAdminError || !platformAdmin) {
    return { error: json({ ok: false, mensagem: "Acesso restrito ao administrador da plataforma" }, 403) };
  }
  return { user: authData.user };
}

async function registrarAuditoria(
  adminUserId: string,
  adminEmail: string | undefined,
  colegioId: string | null,
  acao: string,
  detalhe?: Record<string, unknown>,
) {
  const { error } = await supabase.from("auditoria_admin").insert({
    admin_user_id: adminUserId,
    admin_email: adminEmail ?? null,
    colegio_id: colegioId,
    acao,
    detalhe: detalhe ?? {},
  });
  if (error) console.error("Falha ao registrar auditoria", error); // nao bloqueia a operacao
}

function diasRestantes(dataExpiracao: string | null): number | null {
  if (!dataExpiracao) return null;
  const diff = new Date(dataExpiracao).getTime() - Date.now();
  return Math.ceil(diff / (24 * 60 * 60 * 1000));
}

async function listarClientes() {
  const { data: colegios, error } = await supabase
    .from("colegios")
    .select("id, nome, cnpj, email, status_assinatura, data_expiracao, criado_em")
    .order("criado_em", { ascending: false });
  if (error) throw error;

  const { data: licencas, error: licError } = await supabase
    .from("licencas")
    .select("colegio_id, serial_pdv, chave_ativacao, status");
  if (licError) throw licError;

  const licencasPorColegio = new Map<string, { serial_pdv: string; chave_ativacao: string; status: string }[]>();
  for (const lic of licencas ?? []) {
    const lista = licencasPorColegio.get(lic.colegio_id) ?? [];
    lista.push({ serial_pdv: lic.serial_pdv, chave_ativacao: lic.chave_ativacao, status: lic.status });
    licencasPorColegio.set(lic.colegio_id, lista);
  }

  const hoje = new Date().toISOString().slice(0, 10);
  const clientes = (colegios ?? []).map((c) => {
    const expirou = c.data_expiracao ? c.data_expiracao.slice(0, 10) < hoje : false;
    const licencasDoCliente = licencasPorColegio.get(c.id) ?? [];
    return {
      colegio_id: c.id,
      nome: c.nome,
      cnpj: c.cnpj,
      email: c.email,
      status_assinatura: c.status_assinatura,
      data_expiracao: c.data_expiracao,
      criado_em: c.criado_em,
      situacao: expirou ? "expirado" : "ativo",
      dias_restantes: diasRestantes(c.data_expiracao),
      licencas: licencasDoCliente,
    };
  });

  return json({ ok: true, clientes });
}

// Gera serial (PDV-XXXXXXXX) e chave (XXXX-XXXX-XXXX-XXXX) a partir de UUIDs.
function gerarSerialPdv(): string {
  return `PDV-${crypto.randomUUID().replace(/-/g, "").slice(0, 8).toUpperCase()}`;
}

function gerarChaveAtivacao(): string {
  const hex = crypto.randomUUID().replace(/-/g, "").toUpperCase();
  return [hex.slice(0, 4), hex.slice(4, 8), hex.slice(8, 12), hex.slice(12, 16)].join("-");
}

async function cadastrarCliente(user: { id: string; email?: string }, body: Record<string, unknown>) {
  const nome = typeof body?.nome === "string" ? body.nome.trim() : "";
  if (!nome) {
    return json({ ok: false, mensagem: "nome do cliente obrigatorio" }, 400);
  }

  const dias = Number.isInteger(body?.dias_validade) && body.dias_validade > 0
    ? Math.min(body.dias_validade, 3650)
    : 365;
  const trial = body?.trial === true;
  const dataExpiracao = new Date(Date.now() + dias * 24 * 60 * 60 * 1000).toISOString();

  const { data: colegio, error: erroColegio } = await supabase
    .from("colegios")
    .insert({
      nome,
      cnpj: typeof body?.cnpj === "string" && body.cnpj.trim() ? body.cnpj.trim() : null,
      email: typeof body?.email === "string" && body.email.trim() ? body.email.trim() : null,
      telefone: typeof body?.telefone === "string" && body.telefone.trim() ? body.telefone.trim() : null,
      responsavel: typeof body?.responsavel === "string" && body.responsavel.trim() ? body.responsavel.trim() : null,
      observacoes: typeof body?.observacoes === "string" && body.observacoes.trim() ? body.observacoes.trim() : null,
      status_assinatura: trial ? "trial" : "ativo",
      data_expiracao: dataExpiracao,
    })
    .select("id, nome, status_assinatura, data_expiracao")
    .single();
  if (erroColegio) throw erroColegio;

  const serialPdv = gerarSerialPdv();
  const chaveAtivacao = gerarChaveAtivacao();

  // Nasce 'pendente' e vira 'ativa' na primeira validacao feita pelo exe do cliente.
  const { error: erroLicenca } = await supabase
    .from("licencas")
    .insert({
      colegio_id: colegio.id,
      serial_pdv: serialPdv,
      chave_ativacao: chaveAtivacao,
      status: "pendente",
    });
  if (erroLicenca) throw erroLicenca;

  await registrarAuditoria(user.id, user.email, colegio.id, "cadastrar", { nome, trial });
  return json({
    ok: true,
    mensagem: `Cliente ${nome} cadastrado. Envie os dados de ativacao para ele.`,
    cliente: {
      colegio_id: colegio.id,
      nome: colegio.nome,
      status_assinatura: colegio.status_assinatura,
      data_expiracao: colegio.data_expiracao,
      serial_pdv: serialPdv,
      chave_ativacao: chaveAtivacao,
    },
  }, 201);
}

async function renovarCliente(user: { id: string; email?: string }, colegioId: string, diasValidade: number) {
  const dataExpiracao = new Date(Date.now() + diasValidade * 24 * 60 * 60 * 1000).toISOString();
  const { error } = await supabase
    .from("colegios")
    .update({ data_expiracao: dataExpiracao, status_assinatura: "ativo" })
    .eq("id", colegioId);
  if (error) throw error;
  // Reativa licenças revogadas do cliente
  await supabase.from("licencas").update({ status: "ativa" }).eq("colegio_id", colegioId);
  await registrarAuditoria(user.id, user.email, colegioId, "renovar", { dias_validade: diasValidade });
  return json({ ok: true, mensagem: "Licenca renovada", data_expiracao: dataExpiracao });
}

async function definirExpiracao(user: { id: string; email?: string }, colegioId: string, dataExpiracao: string) {
  if (!/^\d{4}-\d{2}-\d{2}/.test(dataExpiracao) || Number.isNaN(new Date(dataExpiracao).getTime())) {
    return json({ ok: false, mensagem: "Data de expiracao invalida (use AAAA-MM-DD)" }, 400);
  }
  const hoje = new Date().toISOString().slice(0, 10);
  const status = dataExpiracao.slice(0, 10) < hoje ? "expirado" : "ativo";
  const { error } = await supabase
    .from("colegios")
    .update({ data_expiracao: dataExpiracao, status_assinatura: status === "expirado" ? "expirado" : "ativo" })
    .eq("id", colegioId);
  if (error) throw error;
  await registrarAuditoria(user.id, user.email, colegioId, "definir_expiracao", { data_expiracao: dataExpiracao });
  return json({ ok: true, mensagem: "Validade atualizada", data_expiracao: dataExpiracao });
}

async function editarCliente(user: { id: string; email?: string }, colegioId: string, body: Record<string, unknown>) {
  const update: Record<string, string> = {};
  if (typeof body?.nome === "string" && body.nome.trim()) update.nome = body.nome.trim();
  if (typeof body?.cnpj === "string") update.cnpj = body.cnpj.trim() || null as unknown as string;
  if (typeof body?.email === "string") update.email = body.email.trim() || null as unknown as string;
  if (typeof body?.telefone === "string") update.telefone = body.telefone.trim() || null as unknown as string;
  if (typeof body?.responsavel === "string") update.responsavel = body.responsavel.trim() || null as unknown as string;
  if (typeof body?.observacoes === "string") update.observacoes = body.observacoes.trim() || null as unknown as string;
  if (!Object.keys(update).length) {
    return json({ ok: false, mensagem: "Nenhum campo para atualizar (nome, cnpj, email)" }, 400);
  }
  const { error } = await supabase.from("colegios").update(update).eq("id", colegioId);
  if (error) throw error;
  await registrarAuditoria(user.id, user.email, colegioId, "editar", update);
  return json({ ok: true, mensagem: "Dados do cliente atualizados" });
}

async function exportarCliente(colegioId: string) {
  const { data: colegio, error: erroColegio } = await supabase
    .from("colegios")
    .select("*")
    .eq("id", colegioId)
    .maybeSingle();
  if (erroColegio) throw erroColegio;
  if (!colegio) return json({ ok: false, mensagem: "Cliente nao encontrado" }, 404);

  const { data: licencas, error: erroLic } = await supabase
    .from("licencas")
    .select("*")
    .eq("colegio_id", colegioId)
    .order("criado_em", { ascending: true });
  if (erroLic) throw erroLic;

  const { data: auditoria, error: erroAud } = await supabase
    .from("auditoria_admin")
    .select("*")
    .eq("colegio_id", colegioId)
    .order("criado_em", { ascending: true });
  if (erroAud) console.error("Falha ao buscar auditoria", erroAud); // exporta mesmo assim

  return json({
    ok: true,
    exportado_em: new Date().toISOString(),
    cliente: colegio,
    licencas: licencas ?? [],
    auditoria: auditoria ?? [],
  });
}

async function excluirCliente(colegioId: string) {
  // Remove licencas primeiro (seguranca caso nao haja ON DELETE CASCADE)
  const { error: erroLic } = await supabase.from("licencas").delete().eq("colegio_id", colegioId);
  if (erroLic) throw erroLic;
  const { error } = await supabase.from("colegios").delete().eq("id", colegioId);
  if (error) throw error;
  return json({ ok: true, mensagem: "Cliente excluido permanentemente" });
}

async function novaLicenca(colegioId: string) {
  const { data: colegio } = await supabase
    .from("colegios")
    .select("id")
    .eq("id", colegioId)
    .maybeSingle();
  if (!colegio) return json({ ok: false, mensagem: "Cliente nao encontrado" }, 404);
  const serialPdv = gerarSerialPdv();
  const chaveAtivacao = gerarChaveAtivacao();
  const { error } = await supabase.from("licencas").insert({
    colegio_id: colegioId,
    serial_pdv: serialPdv,
    chave_ativacao: chaveAtivacao,
    status: "pendente",
  });
  if (error) throw error;
  return json({ ok: true, mensagem: "Nova licenca emitida", licenca: { serial_pdv: serialPdv, chave_ativacao: chaveAtivacao } }, 201);
}

async function alterarStatusLicenca(colegioId: string, serialPdv: string, status: string) {
  if (!serialPdv) return json({ ok: false, mensagem: "serial_pdv obrigatorio" }, 400);
  const { error } = await supabase
    .from("licencas")
    .update({ status })
    .eq("colegio_id", colegioId)
    .eq("serial_pdv", serialPdv);
  if (error) throw error;
  return json({ ok: true, mensagem: `Licenca ${status}` });
}

async function alterarStatus(colegioId: string, novoStatus: string) {
  if (!["ativo", "suspenso"].includes(novoStatus)) {
    return json({ ok: false, mensagem: "Status invalido" }, 400);
  }
  const { error } = await supabase
    .from("colegios")
    .update({ status_assinatura: novoStatus })
    .eq("id", colegioId);
  if (error) throw error;
  // Suspenso/revogado bloqueia todas as licenças do cliente
  await supabase
    .from("licencas")
    .update({ status: novoStatus === "ativo" ? "ativa" : "revogada" })
    .eq("colegio_id", colegioId);
  return json({ ok: true, mensagem: `Cliente ${novoStatus}` });
}

Deno.serve(async (request: Request) => {
  if (request.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  const { error: authError } = await requirePlatformAdmin(request);
  if (authError) return authError;

  try {
    if (request.method === "GET") {
      return await listarClientes();
    }

    if (request.method === "POST") {
      const body = await request.json();
      const acao = typeof body?.acao === "string" ? body.acao : "";
      const colegioId = typeof body?.colegio_id === "string" ? body.colegio_id : "";

      if (!colegioId) return json({ ok: false, mensagem: "colegio_id obrigatorio" }, 400);

      if (acao === "cadastrar") {
        return await cadastrarCliente(body);
      }
      if (acao === "renovar") {
        const dias = Number.isInteger(body?.dias_validade) && body.dias_validade > 0
          ? Math.min(body.dias_validade, 3650)
          : 365;
        return await renovarCliente(colegioId, dias);
      }
      if (acao === "definir_expiracao") {
        const data = typeof body?.data_expiracao === "string" ? body.data_expiracao : "";
        if (!data) return json({ ok: false, mensagem: "data_expiracao obrigatoria (AAAA-MM-DD)" }, 400);
        return await definirExpiracao(colegioId, data);
      }
      if (acao === "suspender" || acao === "reativar") {
        return await alterarStatus(colegioId, acao === "reativar" ? "ativo" : "suspenso");
      }
      if (acao === "editar") {
        return await editarCliente(colegioId, body);
      }
      if (acao === "exportar") {
        return await exportarCliente(colegioId);
      }
      if (acao === "excluir") {
        return await excluirCliente(colegioId);
      }
      if (acao === "nova_licenca") {
        return await novaLicenca(colegioId);
      }
      if (acao === "revogar_licenca" || acao === "reativar_licenca") {
        const serial = typeof body?.serial_pdv === "string" ? body.serial_pdv : "";
        return await alterarStatusLicenca(colegioId, serial, acao === "revogar_licenca" ? "revogada" : "ativa");
      }
      return json({ ok: false, mensagem: "Acao invalida" }, 400);
    }

    return json({ ok: false, mensagem: "Metodo nao permitido" }, 405);
  } catch (error) {
    console.error("Falha ao gerenciar clientes", error);
    return json({ ok: false, mensagem: "Nao foi possivel concluir a operacao" }, 500);
  }
});

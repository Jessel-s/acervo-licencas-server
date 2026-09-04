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

function diasRestantes(dataExpiracao: string | null): number | null {
  if (!dataExpiracao) return null;
  const diff = new Date(dataExpiracao).getTime() - Date.now();
  return Math.ceil(diff / (24 * 60 * 60 * 1000));
}

async function listarClientes() {
  const { data: colegios, error } = await supabase
    .from("colegios")
    .select("id, nome, cnpj, email, status_assinatura, data_expiracao, created_at")
    .order("created_at", { ascending: false });
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
      created_at: c.created_at,
      situacao: expirou ? "expirado" : "ativo",
      dias_restantes: diasRestantes(c.data_expiracao),
      licencas: licencasDoCliente,
    };
  });

  return json({ ok: true, clientes });
}

async function renovarCliente(colegioId: string, diasValidade: number) {
  const dataExpiracao = new Date(Date.now() + diasValidade * 24 * 60 * 60 * 1000).toISOString();
  const { error } = await supabase
    .from("colegios")
    .update({ data_expiracao: dataExpiracao, status_assinatura: "ativo" })
    .eq("id", colegioId);
  if (error) throw error;
  // Reativa licenças revogadas do cliente
  await supabase.from("licencas").update({ status: "ativa" }).eq("colegio_id", colegioId);
  return json({ ok: true, mensagem: "Licenca renovada", data_expiracao: dataExpiracao });
}

async function definirExpiracao(colegioId: string, dataExpiracao: string) {
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
  return json({ ok: true, mensagem: "Validade atualizada", data_expiracao: dataExpiracao });
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
      return json({ ok: false, mensagem: "Acao invalida" }, 400);
    }

    return json({ ok: false, mensagem: "Metodo nao permitido" }, 405);
  } catch (error) {
    console.error("Falha ao gerenciar clientes", error);
    return json({ ok: false, mensagem: "Nao foi possivel concluir a operacao" }, 500);
  }
});

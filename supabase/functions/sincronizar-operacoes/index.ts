import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
const serviceRoleKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const supabase = createClient(supabaseUrl, serviceRoleKey);

const entityTables: Record<string, string> = {
  ativo: "ativos",
  usuario: "usuarios",
  sessao_uso: "sessoes_uso",
  historico: "historico",
  problema: "problemas",
  agendamento: "agendamentos",
  almox_produto: "almox_produtos",
  almox_movimentacao: "almox_movimentacoes",
};

const deleteSupported = new Set(["ativo", "usuario", "almox_produto", "almox_movimentacao"]);

function json(body: Record<string, unknown>, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

Deno.serve(async (request: Request) => {
  if (request.method !== "POST") {
    return json({ ok: false, mensagem: "Metodo nao permitido" }, 405);
  }

  try {
    const body = await request.json();
    let colegioId: string | null = null;
    const authorization = request.headers.get("Authorization");

    if (authorization?.startsWith("Bearer ")) {
      const token = authorization.slice("Bearer ".length);
      const { data: authData, error: authError } = await supabase.auth.getUser(token);
      if (!authError && authData.user) {
        const { data: profile, error: profileError } = await supabase
          .from("perfis")
          .select("colegio_id")
          .eq("id", authData.user.id)
          .maybeSingle();
        if (!profileError && profile) colegioId = profile.colegio_id;
      }
    }

    if (!colegioId) {
      const device = body?.device_license;
      const deviceColegioId = typeof device?.colegio_id === "string" ? device.colegio_id.trim() : "";
      const serialPdv = typeof device?.serial_pdv === "string" ? device.serial_pdv.trim() : "";
      const chaveAtivacao = typeof device?.chave_ativacao === "string" ? device.chave_ativacao.trim() : "";
      if (!deviceColegioId || !serialPdv || !chaveAtivacao) {
        return json({ ok: false, mensagem: "Sessao Supabase ou credenciais validas da licenca sao necessarias para sincronizar" }, 401);
      }

      const { data: license, error: licenseError } = await supabase
        .from("licencas")
        .select("id, colegio_id, status")
        .eq("colegio_id", deviceColegioId)
        .eq("serial_pdv", serialPdv)
        .eq("chave_ativacao", chaveAtivacao)
        .maybeSingle();
      if (licenseError || !license || license.status !== "ativa") {
        return json({ ok: false, mensagem: "Licenca deste dispositivo invalida, revogada ou inativa" }, 403);
      }

      const { data: colegio, error: colegioError } = await supabase
        .from("colegios")
        .select("status_assinatura, data_expiracao")
        .eq("id", license.colegio_id)
        .maybeSingle();
      if (colegioError || !colegio || !["ativo", "trial"].includes(colegio.status_assinatura)) {
        return json({ ok: false, mensagem: "Assinatura do cliente nao esta ativa para sincronizacao" }, 403);
      }
      if (colegio.data_expiracao && new Date(colegio.data_expiracao).getTime() < Date.now()) {
        return json({ ok: false, mensagem: "Assinatura do cliente expirou" }, 403);
      }

      colegioId = license.colegio_id;
      await supabase.from("licencas").update({ ultima_checagem: new Date().toISOString() }).eq("id", license.id);
    }

    const events = Array.isArray(body?.events) ? body.events : [];
    if (!events.length || events.length > 100) {
      return json({ ok: false, mensagem: "Informe entre 1 e 100 operacoes" }, 400);
    }

    let processed = 0;
    for (const event of events) {
      const table = entityTables[event?.entity_type];
      if (!table || !event?.entity_id || !["upsert", "delete"].includes(event?.operation)) {
        return json({ ok: false, mensagem: "Operacao de sincronizacao invalida" }, 400);
      }
      if (event.operation === "delete" && !deleteSupported.has(event.entity_type)) {
        return json({ ok: false, mensagem: "Remocao nao permitida para esta operacao" }, 400);
      }

      if (event.operation === "upsert") {
        if (!event.payload || event.payload.colegio_id !== colegioId) {
          return json({ ok: false, mensagem: "Tenant invalido na operacao" }, 403);
        }
        const conflict = event.entity_type === "ativo"
          ? "colegio_id,id"
          : event.entity_type === "almox_produto"
            ? "colegio_id,source_id"
            : "colegio_id,source_id";
        const { error } = await supabase.from(table).upsert(event.payload, { onConflict: conflict });
        if (error) throw error;
      } else {
        const identifier = event.entity_type === "ativo" ? "id" : "source_id";
        const { error } = await supabase
          .from(table)
          .delete()
          .eq("colegio_id", colegioId)
          .eq(identifier, event.entity_id);
        if (error) throw error;
      }
      processed += 1;
    }

    return json({ ok: true, processed });
  } catch (error) {
    console.error("Falha na sincronizacao", error);
    return json({ ok: false, mensagem: "Falha ao processar sincronizacao" }, 500);
  }
});
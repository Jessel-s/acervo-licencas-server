import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
const serviceRoleKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const supabase = createClient(supabaseUrl, serviceRoleKey);

const entityTables: Record<string, string> = {
  ativo: "ativos",
  sessao_uso: "sessoes_uso",
  historico: "historico",
  problema: "problemas",
  agendamento: "agendamentos",
  almox_produto: "almox_produtos",
  almox_movimentacao: "almox_movimentacoes",
};

const deleteSupported = new Set(["ativo", "almox_produto", "almox_movimentacao"]);

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

  const authorization = request.headers.get("Authorization");
  if (!authorization?.startsWith("Bearer ")) {
    return json({ ok: false, mensagem: "Token de autenticacao ausente" }, 401);
  }

  try {
    const token = authorization.slice("Bearer ".length);
    const { data: authData, error: authError } = await supabase.auth.getUser(token);
    if (authError || !authData.user) {
      return json({ ok: false, mensagem: "Token de autenticacao invalido" }, 401);
    }

    const { data: profile, error: profileError } = await supabase
      .from("perfis")
      .select("colegio_id")
      .eq("id", authData.user.id)
      .maybeSingle();
    if (profileError || !profile) {
      return json({ ok: false, mensagem: "Perfil de acesso nao encontrado" }, 403);
    }

    const body = await request.json();
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
        if (!event.payload || event.payload.colegio_id !== profile.colegio_id) {
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
          .eq("colegio_id", profile.colegio_id)
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
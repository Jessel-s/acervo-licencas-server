import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
const supabaseKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const supabase = createClient(supabaseUrl, supabaseKey);

function normalizeStatus(status: string | undefined): string {
  const value = (status || "").toLowerCase();
  if (["paid", "confirmed", "approved", "pago", "aprovado"].includes(value)) return "ativo";
  if (["pending", "waiting", "processing"].includes(value)) return "pendente";
  return "bloqueado";
}

Deno.serve(async (req: Request) => {
  try {
    const body = await req.json();
    const statusGateway = body?.payment?.status || body?.status || body?.event || body?.data?.status;
    const colegioId = body?.metadata?.colegio_id || body?.data?.metadata?.colegio_id || body?.colegio_id;

    if (!colegioId) {
      return new Response(JSON.stringify({ ok: false, mensagem: "colegio_id ausente no webhook" }), {
        status: 400,
        headers: { "Content-Type": "application/json" },
      });
    }

    const statusFinal = normalizeStatus(statusGateway);
    if (statusFinal !== "ativo") {
      return new Response(JSON.stringify({ ok: true, mensagem: "Pagamento ainda não confirmado", status: statusFinal }), {
        headers: { "Content-Type": "application/json" },
      });
    }

    const hoje = new Date();
    const proximoMes = new Date(hoje);
    proximoMes.setDate(hoje.getDate() + 30);

    const { error } = await supabase
      .from("colegios")
      .update({
        status_assinatura: "ativo",
        data_expiracao: proximoMes.toISOString(),
      })
      .eq("id", colegioId);

    if (error) {
      return new Response(JSON.stringify({ ok: false, mensagem: "Erro ao atualizar assinatura", detalhe: error.message }), {
        status: 500,
        headers: { "Content-Type": "application/json" },
      });
    }

    await supabase.from("pagamentos").insert({
      colegio_id: colegioId,
      gateway: "asaas",
      referencia: body?.id || body?.payment?.id || "webhook",
      valor: Number(body?.value || body?.payment?.value || 0),
      status: "confirmado",
      payload: body,
    });

    return new Response(JSON.stringify({ ok: true, mensagem: "Assinatura renovada com sucesso", novo_expira_em: proximoMes.toISOString() }), {
      headers: { "Content-Type": "application/json" },
    });
  } catch (err) {
    return new Response(JSON.stringify({ ok: false, mensagem: "Erro interno no webhook", detalhe: String(err) }), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    });
  }
});

import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
const supabaseKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const supabase = createClient(supabaseUrl, supabaseKey);

Deno.serve(async (req: Request) => {
  try {
    const body = await req.json();
    const serial_pdv = body?.serial_pdv;
    const chave_ativacao = body?.chave_ativacao;
    const colegio_id = body?.colegio_id;

    if (!serial_pdv || !chave_ativacao) {
      return new Response(
        JSON.stringify({ ok: false, mensagem: "serial_pdv e chave_ativacao são obrigatórios" }),
        { status: 400, headers: { "Content-Type": "application/json" } }
      );
    }

    const { data: licenca, error: erroBusca } = await supabase
      .from("licencas")
      .select("*")
      .eq("serial_pdv", serial_pdv)
      .eq("chave_ativacao", chave_ativacao)
      .maybeSingle();

    if (erroBusca) {
      return new Response(
        JSON.stringify({ ok: false, mensagem: "Erro ao consultar licença", detalhe: erroBusca.message }),
        { status: 500, headers: { "Content-Type": "application/json" } }
      );
    }

    if (!licenca) {
      return new Response(
        JSON.stringify({ ok: false, valid: false, mensagem: "Licença não encontrada" }),
        { status: 404, headers: { "Content-Type": "application/json" } }
      );
    }

    if (colegio_id && licenca.colegio_id !== colegio_id) {
      return new Response(
        JSON.stringify({ ok: false, valid: false, mensagem: "Licença vinculada a outro colegio" }),
        { status: 403, headers: { "Content-Type": "application/json" } }
      );
    }

    const { data: colegio, error: erroColegio } = await supabase
      .from("colegios")
      .select("status_assinatura, data_expiracao")
      .eq("id", licenca.colegio_id)
      .maybeSingle();

    if (erroColegio) {
      return new Response(
        JSON.stringify({ ok: false, valid: false, mensagem: "Erro ao consultar contrato do colegio" }),
        { status: 500, headers: { "Content-Type": "application/json" } }
      );
    }

    const agora = new Date();
    const assinaturaAtiva = colegio?.status_assinatura === "ativo" || colegio?.status_assinatura === "trial";
    const expirou = !!colegio?.data_expiracao && new Date(colegio.data_expiracao).getTime() < agora.getTime();
    const valid = licenca.status === "ativa" && assinaturaAtiva && !expirou;

    await supabase
      .from("licencas")
      .update({
        ultima_checagem: agora.toISOString(),
        status: valid ? "ativa" : "expirada",
      })
      .eq("id", licenca.id);

    return new Response(
      JSON.stringify({
        ok: true,
        valid,
        colegio_id: licenca.colegio_id,
        serial_pdv: licenca.serial_pdv,
        status_licenca: valid ? "ativa" : "expirada",
        data_expiracao: colegio?.data_expiracao || null,
      }),
      { headers: { "Content-Type": "application/json" } }
    );
  } catch (err) {
    return new Response(
      JSON.stringify({ ok: false, mensagem: "Erro interno da validação", detalhe: String(err) }),
      { status: 500, headers: { "Content-Type": "application/json" } }
    );
  }
});

import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
const serviceRoleKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const supabase = createClient(supabaseUrl, serviceRoleKey);
const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

function json(body: Record<string, unknown>, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...corsHeaders },
  });
}

// Gera o proximo serial sequencial (PDV-001, PDV-002, ...) ignorando os ja usados.
async function gerarSerialPdv() {
  const { data: existentes } = await supabase
    .from("licencas")
    .select("serial_pdv")
    .not("serial_pdv", "is", null);
  const usados = new Set((existentes ?? []).map((r) => String(r.serial_pdv).toUpperCase()));
  for (let i = 1; i <= 999; i++) {
    const candidato = `PDV-${String(i).padStart(3, "0")}`;
    if (!usados.has(candidato)) return candidato;
  }
  return `PDV-${Date.now().toString().slice(-6)}`;
}

function requiredText(value: unknown, field: string) {
  if (typeof value !== "string" || !value.trim()) {
    throw new Error(`${field} obrigatório.`);
  }
  return value.trim();
}

function normalizeDigits(value: string | null | undefined) {
  return String(value ?? "").replace(/\D/g, "");
}

function isValidEmail(value: string) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value.trim());
}

function isValidPhone(value: string | null | undefined) {
  const digits = normalizeDigits(value);
  return digits.length === 10 || digits.length === 11;
}

function isValidCnpj(value: string | null | undefined) {
  const cnpj = normalizeDigits(value);
  if (cnpj.length !== 14 || /^\d{14}$/.test(cnpj) === false) return false;

  const calc = (slice: number) => {
    const numbers = cnpj.slice(0, slice).split("").map(Number);
    const weights = Array.from({ length: slice }, (_, index) => slice + 1 - index);
    const sum = numbers.reduce((acc, num, idx) => acc + num * weights[idx], 0);
    const rest = sum % 11;
    return rest < 2 ? 0 : 11 - rest;
  };

  const dig1 = calc(12);
  const dig2 = calc(13);
  return dig1 === Number(cnpj[12]) && dig2 === Number(cnpj[13]);
}

Deno.serve(async (request: Request) => {
  if (request.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

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

    const { data: platformAdmin, error: platformAdminError } = await supabase
      .from("administradores_plataforma")
      .select("user_id")
      .eq("user_id", authData.user.id)
      .maybeSingle();
    if (platformAdminError || !platformAdmin) {
      return json({ ok: false, mensagem: "Acesso restrito ao administrador da plataforma" }, 403);
    }

    const body = await request.json();
    const nomeCliente = requiredText(body?.nome_cliente, "Nome do cliente");
    const emailCliente = requiredText(body?.email_cliente, "E-mail do cliente").toLowerCase();
    const nomeAdmin = requiredText(body?.nome_admin, "Nome do administrador");
    const emailAdmin = requiredText(body?.email_admin, "E-mail do administrador").toLowerCase();
    const senhaAdmin = requiredText(body?.senha_admin, "Senha temporária");
    // Serial e gerado automaticamente e sequencial; o campo do formulario e ignorado.
    const serialPdv = await gerarSerialPdv();
    const cnpj = typeof body?.cnpj === "string" ? body.cnpj.trim() || null : null;
    const telefone = typeof body?.telefone === "string" ? body.telefone.trim() || null : null;

    if (!isValidEmail(emailCliente)) {
      throw new Error("E-mail comercial inválido.");
    }
    if (!isValidEmail(emailAdmin)) {
      throw new Error("E-mail de acesso inválido.");
    }
    if (telefone && !isValidPhone(telefone)) {
      throw new Error("Telefone inválido. Use DDD + 8 ou 9 dígitos.");
    }
    if (cnpj && !isValidCnpj(cnpj)) {
      throw new Error("CNPJ inválido.");
    }
    if (senhaAdmin.length < 8) {
      throw new Error("Senha temporária deve ter no mínimo 8 caracteres.");
    }

    const diasValidade = Number.isInteger(body?.dias_validade) && body.dias_validade > 0
      ? Math.min(body.dias_validade, 3650)
      : 365;
    const chaveAtivacao = `ACERVO-${crypto.randomUUID().replaceAll("-", "").slice(0, 20).toUpperCase()}`;
    const dataExpiracao = new Date(Date.now() + diasValidade * 24 * 60 * 60 * 1000).toISOString();

    const { data: colegio, error: colegioError } = await supabase
      .from("colegios")
      .insert({
        nome: nomeCliente,
        cnpj,
        email: emailCliente,
        status_assinatura: "ativo",
        data_expiracao: dataExpiracao,
      })
      .select("id")
      .single();
    if (colegioError || !colegio) throw colegioError || new Error("Não foi possível criar o cliente.");

    const { data: adminUser, error: adminError } = await supabase.auth.admin.createUser({
      email: emailAdmin,
      password: senhaAdmin,
      email_confirm: true,
    });
    if (adminError || !adminUser.user) {
      await supabase.from("colegios").delete().eq("id", colegio.id);
      const mensagem = String(adminError?.message ?? "").toLowerCase();
      if (mensagem.includes("already registered") || mensagem.includes("already exists") || mensagem.includes("user already")) {
        throw new Error("Este e-mail de acesso já está cadastrado no sistema.");
      }
      if (mensagem.includes("password")) {
        throw new Error("Senha inválida. Use uma senha mais forte.");
      }
      throw adminError || new Error("Não foi possível criar o administrador.");
    }

    const { error: profileError } = await supabase.from("perfis").insert({
      id: adminUser.user.id,
      colegio_id: colegio.id,
      papel: "admin_geral",
      nome: nomeAdmin,
      telefone,
    });
    if (profileError) throw profileError;

    const { error: licenseError } = await supabase.from("licencas").insert({
      colegio_id: colegio.id,
      chave_ativacao: chaveAtivacao,
      serial_pdv: serialPdv,
      status: "ativa",
    });
    if (licenseError) throw licenseError;

    const { error: deviceError } = await supabase.from("pdv_devices").insert({
      colegio_id: colegio.id,
      serial_pdv: serialPdv,
      nome_dispositivo: `PDV ${serialPdv}`,
      status: "ativo",
    });
    if (deviceError) throw deviceError;

    return json({
      ok: true,
      cliente: {
        colegio_id: colegio.id,
        serial_pdv: serialPdv,
        chave_ativacao: chaveAtivacao,
        email_admin: emailAdmin,
        data_expiracao: dataExpiracao,
      },
    }, 201);
  } catch (error) {
    const mensagem = error instanceof Error ? error.message : "Não foi possível concluir o cadastro do cliente";
    const status = mensagem.includes("obrigatório") || mensagem.includes("inválido") || mensagem.includes("já está") || mensagem.includes("mínimo") ? 400 : 500;
    console.error("Falha ao criar cliente", error);
    return json({ ok: false, mensagem }, status);
  }
});
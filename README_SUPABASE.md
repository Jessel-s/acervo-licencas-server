# Guia de configuração do Supabase para Acervo TI

## 1) Criar o projeto no Supabase

1. Acesse https://supabase.com
2. Crie um novo projeto
3. Copie as variáveis:
   - Project URL
   - anon public key
   - service_role secret

## 2) Configurar arquivo .env

Copie o arquivo .env.example para .env e preencha com os valores reais:

```bash
copy .env.example .env
```

Depois edite o arquivo .env com os valores do projeto no Supabase.

## 3) Executar o SQL no Supabase

Abra o painel do Supabase > SQL Editor > New query

Cole o conteúdo do arquivo:
- supabase/schema.sql

Execute a query.

## 4) Publicar Edge Functions

O deploy e feito pelo GitHub Actions quando ha push na branch `main` com alteracoes em `supabase/functions/` ou `supabase/config.toml`. Configure o segredo `SUPABASE_ACCESS_TOKEN` em GitHub > Settings > Secrets and variables > Actions.

As funcoes publicadas pelo workflow estao em `supabase/functions/`.

### E-mail de acesso do cliente

O cadastro envia os dados de ativacao e a senha temporaria somente para o e-mail de acesso do administrador (`email_admin`), nunca para o e-mail comercial. Configure `RESEND_API_KEY` nos secrets das Edge Functions e mantenha o dominio remetente validado no Resend. Se o envio falhar, a Central avisa que o cliente foi criado, mas que o e-mail nao foi enviado; nao repita o cadastro por causa desse aviso.

## 5) Criar o primeiro tenant

O primeiro colegio normalmente é o cliente principal.

Você pode criar um registro manualmente no SQL Editor:

```sql
INSERT INTO public.colegios (nome, cnpj, email, status_assinatura, data_expiracao)
VALUES (
  'Escola Exemplo',
  '00000000000000',
  'contato@escola.com',
  'ativo',
  NOW() + interval '30 days'
)
RETURNING *;
```

## 6) Criar a licença

```sql
INSERT INTO public.licencas (
  colegio_id,
  chave_ativacao,
  serial_pdv,
  status,
  ultima_checagem
)
VALUES (
  'SEU_COLEGIO_ID',
  'LIC-TESTE-123',
  'PDV-001',
  'ativa',
  NOW()
);
```

## 7) Criar perfil do usuário admin

```sql
INSERT INTO public.perfis (id, colegio_id, papel, nome)
VALUES (
  'ID_DO_USUARIO_AUTH',
  'SEU_COLEGIO_ID',
  'admin_geral',
  'Administrador'
);
```

## 8) Conectar ao app

No Flask, o ambiente lê o .env automaticamente.

Depois de configurar as chaves, rode:

```bash
python app.py
```

## 9) Testar a validação online

Use o serial e a chave do PDV para consultar a função:

```bash
curl -X POST https://SEU_PROJECT.supabase.co/functions/v1/validar-licenca \
  -H "Authorization: Bearer SUA_ANON_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "serial_pdv": "PDV-001",
    "chave_ativacao": "LIC-TESTE-123",
    "colegio_id": "SEU_COLEGIO_ID"
  }'
```

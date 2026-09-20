# Referência da API

Documentação interativa (Swagger) disponível em `/docs` com a aplicação em execução.

A coluna **Auth** indica as rotas que exigem o cabeçalho `Authorization: Bearer <access_token>`.

## Conta do personal

| Auth | Método | Rota | Descrição |
|:--:|---|---|---|
| — | `POST` | `/cadastro` | Cria a conta e dispara o e-mail de confirmação. A conta nasce inativa. |
| — | `GET` | `/confirmar-email?token=` | Confirma o e-mail pelo link recebido e ativa a conta. |
| — | `POST` | `/reenviar-email` | Reenvia o e-mail de confirmação. |
| — | `POST` | `/login` | Autentica e devolve o par access/refresh token. |
| ✅ | `PATCH` | `/alterar-nome` | Altera o nome do personal. |

## Sessão

| Auth | Método | Rota | Descrição |
|:--:|---|---|---|
| — | `POST` | `/refresh` | Recebe um refresh token e devolve um novo par. O token usado é revogado. |
| — | `POST` | `/login-form` | Login em formato formulário, usado pela documentação interativa. |

## Senha

| Auth | Método | Rota | Descrição |
|:--:|---|---|---|
| ✅ | `POST` | `/senha/enviar-email-alteracao` | Envia o link de troca de senha para o personal logado. |
| — | `PATCH` | `/senha/alterar-senha?token=` | Define a nova senha pelo link recebido. |
| — | `POST` | `/senha/esqueci-senha` | Inicia a recuperação para quem não está logado. |
| — | `PATCH` | `/senha/redefinir-senha?token=` | Define a nova senha pelo link de recuperação. |

Trocar a senha incrementa o `token_version` do personal, invalidando todas as sessões abertas.

## Exclusão de conta

| Auth | Método | Rota | Descrição |
|:--:|---|---|---|
| ✅ | `POST` | `/deletar-conta` | Valida a senha e envia o link de confirmação por e-mail. Limitado a 5 tentativas. |
| — | `GET` | `/confirmar-exclusao-conta?token=` | Conclui a exclusão lógica e anonimiza telefone e e-mail. |
| ✅ | `POST` | `/deletar-conta/reenviar-email` | Reenvia o link de exclusão. |

## Alunos

| Auth | Método | Rota | Descrição |
|:--:|---|---|---|
| ✅ | `POST` | `/alunos` | Cadastra um aluno. |
| ✅ | `GET` | `/alunos` | Lista os alunos, com filtro opcional por nome. |
| ✅ | `GET` | `/alunos/{aluno_id}` | Busca um aluno pelo id. |
| ✅ | `PATCH` | `/alunos/{aluno_id}` | Altera os dados do aluno. |
| ✅ | `DELETE` | `/alunos/{aluno_id}` | Exclui o aluno. |

## Aulas

| Auth | Método | Rota | Descrição |
|:--:|---|---|---|
| ✅ | `POST` | `/cadastrar-aula` | Cria uma aula fixa (dia, horários e capacidade). |
| ✅ | `GET` | `/buscar-aulas` | Lista as aulas do personal. |
| ✅ | `PATCH` | `/alterar-aula/{aula_id}` | Altera uma aula. |
| ✅ | `DELETE` | `/deletar-aula/{aula_id}` | Exclui uma aula. |

## Alunos nas aulas

| Auth | Método | Rota | Descrição |
|:--:|---|---|---|
| ✅ | `POST` | `/cadastrar/aluno-na-aula` | Vincula um aluno a uma aula fixa. |
| ✅ | `GET` | `/buscar/aluno-nas-aulas?aluno_id=` | Lista as aulas de um aluno. |
| ✅ | `GET` | `/buscar/alunos-na-aula?aula_id=` | Lista os alunos de uma aula. |
| ✅ | `DELETE` | `/deletar/aluno-na-aula` | Remove o aluno da aula. |

## Notificações

| Auth | Método | Rota | Descrição |
|:--:|---|---|---|
| ✅ | `GET` | `/notificacoes` | Lista as notificações do personal (com cache). |
| ✅ | `DELETE` | `/notificacoes/{notificacao_id}` | Exclui uma notificação. |
| ✅ | `PATCH` | `/notificacoes/{notificacao_id}/reagendamento` | Aceita ou recusa um reagendamento e avisa o aluno pelo WhatsApp. |
| ✅ | `PATCH` | `/personal/push-token` | Registra ou atualiza o token de push do dispositivo. |

## Webhook do WhatsApp

| Auth | Método | Rota | Descrição |
|:--:|---|---|---|
| — | `GET` | `/webhooks/whatsapp` | Validação da inscrição do webhook feita pela Meta (`hub.challenge`). |
| — | `POST` | `/webhooks/whatsapp` | Recebe as mensagens dos alunos. |

Essas rotas não usam JWT, mas **não são abertas**: cada evento recebido tem a assinatura `X-Hub-Signature-256` conferida contra o `WHATSAPP_APP_SECRET`. Assinatura ausente ou divergente resulta em `403`.

## Respostas de erro mais comuns

| Código | Quando acontece |
|---|---|
| `401` | Token ausente, inválido, expirado ou invalidado por troca de senha. |
| `403` | Conta sem e-mail confirmado, ou assinatura inválida no webhook. |
| `409` | Conflito: telefone/e-mail já cadastrado, aluno duplicado, sobreposição de horário. |
| `429` | Cooldown de envio de e-mail ainda ativo, ou limite de tentativas atingido. |
| `503` | Dependência indisponível (Redis fora do ar, falha no envio de e-mail). |

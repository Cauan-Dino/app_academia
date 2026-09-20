# Arquitetura

## Containers

O `docker-compose.yml` do back-end descreve os seguintes serviços:

| Serviço | Imagem | Função | Porta |
|---|---|---|---|
| `app` | build local | API FastAPI — atende o aplicativo e o webhook do WhatsApp | `8000` |
| `mysql` | mysql:8.0 | Banco de dados principal | `127.0.0.1:3307` |
| `redis` | redis:7.2-alpine | Cache, sessões do chatbot, rate limit e broker da fila | `127.0.0.1:6379` |
| `taskiq_worker` | build local | Consome a fila e executa as tarefas (envio de e-mails) | — |
| `taskiq_scheduler` | build local | Publica na fila as tarefas agendadas (novas tentativas com atraso) | — |
| `elasticsearch` | elasticsearch:8.11 | Armazena e indexa os logs | `127.0.0.1:9200` |
| `logstash` | logstash:8.11 | Lê o arquivo de log da aplicação e envia ao Elasticsearch | — |
| `kibana` | kibana:8.11 | Interface de consulta dos logs | `127.0.0.1:5601` |

Somente a porta da API é exposta à rede. Banco, cache e ferramentas de observabilidade ficam restritos a `127.0.0.1`, acessíveis apenas na própria máquina — os containers conversam entre si pela rede interna do Compose, usando o nome do serviço como host (`mysql:3306`, `redis:6379`).

> **Worker e scheduler são serviços distintos e ambos são obrigatórios.** O *worker* é quem executa as tarefas; o *scheduler* apenas reenvia à fila, no momento certo, as tarefas que precisam de atraso (as novas tentativas em caso de falha). Sem o worker, os e-mails são enfileirados e nunca chegam ao destinatário.

## Fluxos principais

### Cadastro de personal

```
POST /cadastro
  → valida se telefone/e-mail já existem (qualquer conta, ativa ou não)
  → grava o personal com usuario_ativo = false
  → verifica o cooldown de envio no Redis (síncrono, devolve 429 se ainda estiver ativo)
  → enfileira o envio do e-mail (TaskIQ) e responde imediatamente
  → o worker envia o e-mail de confirmação
GET /confirmar-email?token=...
  → valida o token assinado e ativa a conta
```

O envio do e-mail é assíncrono para não prender a resposta HTTP na conexão SMTP. O que **não** é assíncrono é a verificação de cooldown: ela roda ainda dentro da requisição, para que o usuário receba o erro 429 na hora.

### Reagendamento solicitado pelo aluno

```
Aluno envia mensagem no WhatsApp
  → Meta chama POST /webhooks/whatsapp
  → a assinatura HMAC-SHA256 do corpo é validada (403 se não confere)
  → o estado da conversa é lido no Redis
  → o serviço de reagendamento conduz a conversa, etapa por etapa:
      aula atual → nova data/hora de início → horário de término → motivo
  → grava a SolicitacaoMudanca (status pendente, expira em 24h)
  → grava a Notificacao na mesma transação
  → encerra a sessão no Redis
  → envia push ao personal (Expo) e confirmação ao aluno (WhatsApp)
```

A sessão no Redis é encerrada **antes** dos envios. Isso é intencional: se algum envio falhar, a API responde com erro e a Meta reenvia o webhook — como a sessão já não existe, o reenvio não recria a solicitação em duplicidade.

### Resposta do personal

```
PATCH /notificacoes/{id}/reagendamento  {"status": "aceita" | "recusada"}
  → trava a solicitação no banco (SELECT ... FOR UPDATE)
  → se aceita, valida sobreposição com outras aulas do aluno
  → marca a notificação como lida e invalida o cache
  → envia o resultado ao aluno pelo WhatsApp
  → registra whatsapp_notificada_em para não reenviar em chamadas repetidas
```

## Modelo de dados

```
Personal ──┬──< Alunos ──────────< ParticipanteAula >────── AulaFixa
           │                                                   │
           ├──< AulaFixa ──────────────────────────────────────┘
           │
           ├──< SolicitacaoMudanca >── Alunos, AulaFixa
           │
           └──< Notificacao >── SolicitacaoMudanca
```

| Tabela | Descrição |
|---|---|
| `personal` | Conta do personal trainer. Guarda credenciais, `push_token` do dispositivo e os campos de controle `usuario_ativo`, `email_verificado` e `token_version`. |
| `alunos` | Alunos de um personal. Nome e telefone são únicos **por personal** (dois personais podem ter alunos homônimos). |
| `agendamentos_fixos` | Aula fixa semanal: dia da semana, horário de início e fim e capacidade máxima. Único por personal + dia + horário de início. |
| `alunos_participantes_da_aula` | Liga alunos às aulas fixas (relação muitos-para-muitos). |
| `solicitacoes_mudanca` | Pedido de reagendamento feito pelo aluno. Guarda a aula original, os novos horários, o motivo, o status e o prazo de expiração. |
| `notificacoes` | Histórico das notificações do personal, com marcação de leitura. Serve como fonte da central de notificações no app. |

**Exclusão de conta é lógica, não física.** Ao confirmar a exclusão, o registro permanece no banco (preservando o histórico de alunos e aulas), mas `usuario_ativo` vira `false` e o telefone e o e-mail são anonimizados — liberando esses dados para um cadastro futuro sem que a conta antiga seja reaproveitada por outra pessoa.

**Invalidação de sessão.** O campo `token_version` é incrementado na troca de senha e na exclusão da conta. Como o valor é gravado dentro do JWT, qualquer token emitido antes deixa de ser aceito imediatamente, sem precisar de blacklist.

## Autenticação

- **Access token** (curta duração) e **refresh token** (longa duração), ambos JWT assinados com `SECRET_KEY`.
- O refresh token carrega um `jti` (identificador único). Ao ser usado em `POST /refresh`, ele vai para uma blacklist no Redis e um novo par é emitido — impedindo reutilização.
- O status do usuário é mantido em cache no Redis por 60 segundos, evitando uma consulta ao banco a cada requisição autenticada.
- Links enviados por e-mail (confirmação de cadastro, troca de senha, exclusão de conta) usam tokens assinados com `itsdangerous`, com finalidade e prazo próprios — são independentes do JWT.

## Observabilidade

A aplicação **não** fala diretamente com o Elasticsearch. O caminho é:

```
logger → arquivo em /logs/app.log → Logstash lê o arquivo → Elasticsearch → Kibana
```

Cada processo (API, worker e scheduler) grava em seu próprio arquivo, definido pela variável `LOG_FILE_PATH`.

## Notificações push

O push depende de três peças configuradas fora do código:

1. **Projeto EAS** — o `getExpoPushTokenAsync()` exige um `projectId`, gravado em `front_end/app.json` (`extra.eas.projectId`).
2. **Firebase (FCM)** — desde versões recentes do SDK do Expo, o Android exige um projeto Firebase próprio: o arquivo `google-services.json` na raiz do `front_end/` e a chave de Service Account enviada à EAS (`eas credentials`).
3. **Development build** — o aplicativo Expo Go não recebe mais notificações remotas. É preciso gerar um build de desenvolvimento (`eas build --profile development --platform android`) e instalá-lo no aparelho.

O token gerado é enviado a `PATCH /personal/push-token` sempre que o app abre com sessão válida, mantendo o registro atualizado caso o token mude (reinstalação do app, por exemplo).

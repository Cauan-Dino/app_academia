# Serviços da aplicação

O código é dividido em duas camadas:

- **`services/domain/`** — regras de negócio. Cada pasta corresponde a um assunto do sistema.
- **`services/infra/`** — recursos técnicos compartilhados: banco, cache, e-mail, fila, configuração.

Os serviços recebem suas dependências pelo construtor e são montados pelos arquivos `dependencies.py` de cada pasta, usados como `Depends(...)` do FastAPI.

---

## Domínio

### `domain/personal` — conta do personal trainer

| Serviço | Responsabilidade |
|---|---|
| `PersonalCadastroService` | Cadastra a conta e confirma o e-mail. Recusa telefones ou e-mails já usados por qualquer conta (ativa ou excluída) e valida a força da senha. A conta nasce inativa e só é liberada ao clicar no link de confirmação. |
| `PersonalLoginService` | Autentica por e-mail e senha e emite o par access/refresh token. Bloqueia contas inativas ou com e-mail não confirmado. |
| `UpdatePersonalDetailsService` | Altera o nome e conduz a troca de senha nos dois cenários: logado (pede o e-mail atual como confirmação) e deslogado ("esqueci minha senha"). Ao trocar a senha, incrementa o `token_version`, derrubando as sessões antigas. |
| `DeletePersonalAcountService` | Exclui a conta em duas etapas: valida a senha (com rate limit de 5 tentativas) e envia um link por e-mail; ao confirmar, faz a exclusão lógica e anonimiza telefone e e-mail. |

### `domain/aluno` — alunos do personal

| Serviço | Responsabilidade |
|---|---|
| `AlunoCommandService` | Cadastra, altera e exclui alunos. Cada aluno pertence a um personal. |
| `AlunoQueryService` | Busca alunos (lista completa, por id ou por nome) e verifica duplicidade de nome e telefone dentro daquele personal. |
| `PersonalClientUtils` | Apoio aos dois acima: serializa alunos para resposta, extrai o `personal_id` do token e normaliza o nome informado. |

### `domain/agendamento` — agenda de aulas

| Serviço | Responsabilidade |
|---|---|
| `ClassRegisterService` | Cria, altera, busca e exclui aulas fixas (dia da semana, horários e capacidade). |
| `ClassQueryService` | Impede conflitos de agenda: detecta sobreposição de horários e trava a agenda do personal para que duas requisições simultâneas não criem aulas conflitantes. |
| `StudentAddClassService` | Vincula e desvincula alunos das aulas, e lista tanto as aulas de um aluno quanto os alunos de uma aula. |

### `domain/chatbot` — conversa com o aluno no WhatsApp

| Serviço | Responsabilidade |
|---|---|
| `WhatsappService` | Porta de entrada e saída do WhatsApp. Valida a inscrição do webhook, confere a assinatura HMAC-SHA256 de cada evento recebido, extrai a mensagem e envia respostas pela API da Meta. |
| `ChatbotConversationService` | Ponto de entrada de toda mensagem recebida. Decide se a conversa está no meio de um reagendamento (e repassa ao serviço específico) ou se deve exibir o menu e tratar a opção escolhida. |
| `ChatBotOptionsService` | Textos do menu e das opções: consultar aulas (1), reagendar (2) e encerrar a conversa (0). |
| `SolicitacaoReagendamentoAulaService` | Conduz o reagendamento etapa por etapa — aula atual, nova data, horário de início, horário de término e motivo — validando cada resposta. Ao final, grava a solicitação, notifica o personal e confirma ao aluno. |
| `UtilsChatbotService` | Guarda o estado da conversa no Redis (com expiração curta), converte e valida datas no formato `DD/MM/AAAA às HH:MM` e avisa o aluno quando a sessão expira ou o Redis está indisponível. |

O estado da conversa vive apenas no Redis, com expiração de 30 a 40 segundos: o chatbot não mantém sessão em memória, o que permite rodar várias instâncias da API.

### `domain/notificacao` — avisos ao personal

| Serviço | Responsabilidade |
|---|---|
| `NotificacaoService` | Grava a notificação no banco e dispara o push pela API da Expo. A gravação entra na transação de quem chamou (para salvar junto com a solicitação), e o push só é disparado depois do commit — assim, uma falha de envio não apaga o histórico. Não envia nada se a conta do personal estiver inativa. |
| `VisualizarNotificacaoService` | Lista as notificações do personal, com cache-aside no Redis e filtros opcionais. |
| `GerenciarNotificacaoService` | Processa a decisão do personal (aceitar ou recusar o reagendamento), valida sobreposição de horários no caso de aceite, marca a notificação como lida e avisa o aluno pelo WhatsApp. Registra o instante do envio para não repetir a mensagem se a mesma resposta for enviada de novo. |
| `PushTokenService` | Salva ou atualiza o `push_token` do dispositivo do personal. |

---

## Infraestrutura

### Banco de dados — `infra/database`

- `database.py` — engine assíncrona do SQLAlchemy e a dependência `sessao_db`, que abre uma sessão por requisição.
- `models.py` — as entidades (`Personal`, `Alunos`, `AulaFixa`, `ParticipanteAula`, `SolicitacaoMudanca`, `Notificacao`) e os enums `DiaDaSemana` e `StatusSolicitacao`.

### Cache e sessões — `infra/redis_service`

| Arquivo | Função |
|---|---|
| `redis_config.py` | Cria o cliente Redis compartilhado. |
| `usuario_status_cache.py` | Mantém em cache, por 60 segundos, o status do usuário autenticado (ativo, e-mail verificado, `token_version`), evitando consultar o banco a cada requisição. |
| `notificacao_cache.py` | Chave e invalidação do cache da lista de notificações. |

### E-mail — `infra/email`

`EmailService` centraliza todos os e-mails transacionais: confirmação de cadastro, exclusão de conta e troca de senha (logado e deslogado).

A divisão de responsabilidade é importante:

- **Verificação de cooldown** — roda de forma **síncrona**, dentro da requisição, usando uma chave no Redis com validade de 60 segundos. Assim o usuário recebe o erro `429` imediatamente se pedir outro e-mail cedo demais.
- **Envio propriamente dito** — vai para a **fila**, porque depende de uma conexão SMTP que pode ser lenta.

### Fila de tarefas — `infra/filas`

| Arquivo | Função |
|---|---|
| `taskiq/taskiq_app.py` | Configura o broker (Redis Streams) e o scheduler. Inclui o `SmartRetryMiddleware`: até 3 tentativas por padrão, com espera exponencial (5s, 10s, 20s…) e *jitter* — uma variação aleatória que evita que várias tarefas que falharam juntas voltem a tentar no mesmo instante. |
| `tasks/email_task.py` | A tarefa `fila_enviar_email`, que monta a mensagem e a envia pelo SMTP. Em caso de erro, apaga a chave de cooldown (para o usuário poder tentar de novo) e relança a exceção, sinalizando ao middleware que deve repetir. |

A tarefa precisa **relançar** a exceção: se o erro for capturado e silenciado, o TaskIQ considera a execução bem-sucedida e a nova tentativa nunca acontece.

### Configuração — `infra/config`

`Settings` (Pydantic Settings) carrega as variáveis de ambiente e protege os segredos com `SecretStr`. A instância é criada **no momento do import** — por isso o `main.py` chama `load_dotenv()` antes de qualquer import de `back_end.*`.

### Demais utilitários

| Módulo | Função |
|---|---|
| `infra/criptografia` | Hash e verificação de senhas com bcrypt. |
| `infra/rate_limit` | Contador de tentativas no Redis, usado hoje na exclusão de conta. |
| `infra/sms/telefone_utils.py` | Normaliza números de telefone antes de gravar ou comparar. |
| `infra/utils/texto.py` | Remove acentos, usado nas comparações de nome. |

---

## Autenticação — `auth/`

| Arquivo | Função |
|---|---|
| `jwt_token.py` | Cria e valida os access e refresh tokens, expõe `POST /refresh` (com rotação e blacklist do token anterior) e o `/login-form` usado pela documentação interativa. |
| `usuario_auth.py` | Busca o usuário autorizado, recusando contas inativas ou sem e-mail confirmado. |
| `auth_token_itsdangerous.py` | Gera e valida os tokens assinados dos links enviados por e-mail, cada um com sua finalidade e prazo. |

## Núcleo — `core/`

| Arquivo | Função |
|---|---|
| `http/exception_handlers.py` | Tratamento global de exceções, padronizando as respostas de erro. |
| `http/middleware.py` | Middlewares HTTP da aplicação. |
| `logging/logs_settings.py` | Configura o logger a partir do `logging.yaml` (saída em console e arquivo rotativo). |

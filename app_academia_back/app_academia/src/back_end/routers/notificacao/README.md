# Notificações do personal

Todas as rotas exigem `Authorization: Bearer <access_token>`. O personal é identificado pelo token; não existe parâmetro para consultar ou alterar notificações de outro personal.

## Listagem e filtros

`GET /notificacoes` retorna todas as notificações, da mais recente para a mais antiga. O mesmo endpoint aceita filtros opcionais combinados:

```http
GET /notificacoes?nome_aluno=joao&data=2026-09-14
```

`nome_aluno` faz busca parcial, ignorando acentos e maiúsculas. `data` é um `date` (`YYYY-MM-DD`), aplicado ao dia de criação da notificação. A coluna existente `criada_em` continua sendo `DateTime`; os horários não são removidos do banco. Novas notificações e prazos são gravados em UTC. Os horários das aulas seguem o horário local da academia (UTC−3), como no chatbot existente.

Cada item contém `id`, `solicitacao_id`, `titulo`, `mensagem`, `lida`, `criada_em`, `aluno_nome`, `reagendamento` e `pode_responder`. Notificações gerais têm aluno/reagendamento nulos. O reagendamento inclui o status, o motivo, os horários original/solicitados, o vencimento e a data da resposta.

O cache-aside mantém uma lista por personal no Redis durante 60 segundos. Os filtros usam essa lista. Criação, exclusão, resposta e alteração/exclusão do aluno invalidam o cache. Redis indisponível ou conteúdo inválido levam à consulta ao banco. Se a invalidação falhar, uma lista antiga pode aparecer até o TTL vencer; decisões sempre consultam o banco com bloqueio. `pode_responder` e o status de expiração são recalculados mesmo quando há cache.

## Exclusão permanente

`DELETE /notificacoes/{notificacao_id}` retorna `204`, sem corpo. Exclui apenas a notificação; a solicitação e a decisão de reagendamento permanecem no banco. ID inexistente ou pertencente a outro personal retorna `404`.

## Aceitar ou recusar

`PATCH /notificacoes/{notificacao_id}/reagendamento` recebe:

```json
{"status": "aceita"}
```

Para recusar, use `{"status": "recusada"}`. Outros valores retornam `422`.

A decisão marca a notificação como lida e grava `status` e `respondida_em`. O aceite representa a mudança da ocorrência na própria `SolicitacaoMudanca`, preservando a aula fixa semanal. Valida vínculo do aluno, horário futuro, conflitos com a agenda do personal e solicitações aceitas, além de impedir dois aceites para a mesma ocorrência. Conflitos e tentativa de mudar uma decisão já tomada retornam `409`.

O prazo é `expira_em`, definido na criação como 24 horas. Uma solicitação pendente com `agora >= expira_em` passa para `expirada` e retorna `410`, sem enviar mensagem. Notificações sem solicitação retornam `400`.

Após confirmar a transação, o resultado é enviado ao telefone cadastrado do aluno pela integração WhatsApp existente. A resposta de sucesso contém `solicitacao_id`, `status`, `respondida_em`, `whatsapp_enviado` e `message`. `whatsapp_enviado=true` indica aceitação pela API da Meta, não confirmação de entrega ao aparelho.

Se o envio falhar, retorna `502` com `detail.resposta_salva=true`. Repita o mesmo PATCH, com o mesmo status, para tentar enviar novamente. Isso não altera a decisão nem a data da resposta; essa repetição é permitida após o prazo porque só reenvia uma decisão já registrada. Um envio já confirmado no banco não é repetido. Não há retentativa automática em segundo plano. Se a API aceitar a mensagem e a confirmação se perder por timeout/falha no commit, uma retentativa pode duplicar o texto.

## Banco e validação

Antes de iniciar a aplicação atualizada, aplique a migração `89b5ce041a72`, que adiciona `solicitacoes_mudanca.whatsapp_notificada_em` (nullable). No diretório do backend, usando o ambiente Python do projeto:

```text
python -m alembic upgrade head
```

O chatbot passa a salvar a solicitação e a notificação vinculada na mesma transação, inclusive quando não há push token. Pushes antigos que não foram persistidos não são reconstruídos.

Na raiz do repositório, execute os testes com:

```powershell
& app_academia/src/back_end/.venv/Scripts/python.exe -m pytest app_academia/tests -q -p no:cacheprovider
```

Os testes usam SQLite em memória, Redis simulado e WhatsApp simulado. A concorrência usa `SELECT ... FOR UPDATE` no MySQL; SQLite não reproduz esses bloqueios. A migração é validada em banco isolado, sem alterar o banco configurado no `.env`.

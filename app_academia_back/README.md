# TreinoPro — Back-end

API FastAPI do TreinoPro: contas de personal trainer, alunos, agenda de aulas, chatbot de WhatsApp e notificações push.

Para entender o projeto como um todo, veja o [README principal](../README.md).

## Executar

```bash
cp .env.example .env     # preencha as credenciais
docker compose up -d
docker compose exec -w /app/back_end app poetry run alembic upgrade head
```

- API: `http://localhost:8000`
- Documentação interativa: `http://localhost:8000/docs`
- Kibana (logs): `http://localhost:5601`

> O `-w /app/back_end` é necessário porque o container inicia em `/app`, mas o `alembic.ini` fica em `/app/back_end/`. Sem isso, o Alembic falha com `No 'script_location' key found in configuration`.

## Testes

Os testes são isolados — usam SQLite em memória e não tocam em nenhum serviço externo:

```bash
cd app_academia
pytest tests
```

## Estrutura

```
app_academia/src/back_end/
  main.py               monta a aplicação, CORS e ciclo de vida
  routers/              endpoints HTTP, agrupados por assunto
  services/domain/      regras de negócio (personal, aluno, agendamento, chatbot, notificação)
  services/infra/       banco, cache, e-mail, fila, configuração e criptografia
  auth/                 JWT e tokens assinados dos links de e-mail
  core/                 logging e tratamento global de erros
  schemas/              modelos Pydantic de entrada e saída
  alembic/versions/     migrations (histórico do schema — nunca ignore no git)

app_academia/tests/     testes automatizados
```

A descrição de cada serviço está em [docs/servicos.md](../docs/servicos.md).

## Containers

| Serviço | Função |
|---|---|
| `app` | API FastAPI |
| `mysql` | Banco de dados |
| `redis` | Cache, sessões do chatbot, rate limit e broker da fila |
| `taskiq_worker` | Executa as tarefas da fila (envio de e-mails) |
| `taskiq_scheduler` | Reenfileira as tarefas com atraso (novas tentativas) |
| `elasticsearch` / `logstash` / `kibana` | Coleta e consulta dos logs |

**Worker e scheduler são obrigatórios e têm papéis diferentes.** O worker executa as tarefas; o scheduler apenas as reenvia à fila no momento certo. Sem o worker rodando, os e-mails ficam enfileirados e nunca são enviados.

## Comandos úteis

```bash
# Criar uma migration a partir das mudanças nos models
docker compose exec -w /app/back_end app poetry run alembic revision --autogenerate -m "descricao"

# Ver em qual revisão o banco está
docker compose exec -w /app/back_end app poetry run alembic current

# Acompanhar os logs da API
docker compose logs -f app

# Inspecionar o banco
docker compose exec mysql mysql -u app_academia_user -p app_academia
```

> O worker do TaskIQ **não recarrega sozinho** quando o código muda (diferente da API em modo desenvolvimento). Depois de editar qualquer arquivo em `services/infra/filas/`, rode `docker compose restart taskiq_worker`.

## Variáveis de ambiente

Todas estão listadas e comentadas no [.env.example](.env.example). Os pontos de atenção:

- `SECRET_KEY` e `PEPPER` — gere valores próprios para produção; nunca reaproveite os de desenvolvimento.
- `SQLALCHEMY_DATABASE_URL` — dentro do Docker o host é `mysql`; fora, use `127.0.0.1:3307`.
- `CORS_ORIGINS` — deixe vazio se só o app mobile consome a API; preencha apenas se houver um front web.
- `WHATSAPP_APP_SECRET` — usado para validar a assinatura dos webhooks recebidos da Meta.

## Documentação

- [docs/arquitetura.md](../docs/arquitetura.md) — containers, fluxos e modelo de dados.
- [docs/servicos.md](../docs/servicos.md) — o que cada serviço faz.
- [docs/api.md](../docs/api.md) — referência dos endpoints.

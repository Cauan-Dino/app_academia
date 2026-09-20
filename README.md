# TreinoPro

Sistema de gestão para personal trainers: cadastro de alunos, agenda semanal de aulas fixas e um chatbot de WhatsApp pelo qual o aluno consulta suas aulas e solicita reagendamentos — que o personal aprova ou recusa pelo aplicativo, recebendo notificações push em tempo real.

## O que o sistema faz

**Para o personal trainer** (aplicativo mobile)
- Cadastro de conta com confirmação por e-mail, login com JWT e recuperação de senha.
- Gestão de alunos: cadastro, busca, alteração e exclusão.
- Agenda semanal: criação de aulas fixas com dia, horário e capacidade, e controle de quem participa de cada aula.
- Central de notificações: recebe um push sempre que um aluno solicita reagendamento e responde aceitando ou recusando.

**Para o aluno** (WhatsApp, sem precisar instalar nada)
- Consulta as próprias aulas conversando com o bot.
- Solicita o reagendamento de uma aula: informa a aula atual, a nova data, os horários de início e fim e o motivo.
- Recebe a resposta do personal automaticamente pelo WhatsApp.

## Arquitetura em resumo

```
  Aluno (WhatsApp)                     Personal (app mobile)
        │                                       │
        │ mensagem                              │ HTTP + JWT
        ▼                                       ▼
  WhatsApp Cloud API  ──webhook──►   API FastAPI   ──push──►  Expo Push Service
                                          │
                 ┌────────────────────────┼────────────────────────┐
                 ▼                        ▼                        ▼
              MySQL                     Redis                 TaskIQ worker
        (dados do negócio)     (cache, sessões do bot,       (envio de e-mails
                                rate limit, fila)             em segundo plano)
```

Os logs da aplicação são gravados em arquivo, coletados pelo Logstash e indexados no Elasticsearch para consulta no Kibana.

## Stack

| Camada | Tecnologias |
|---|---|
| API | Python 3.13, FastAPI, SQLAlchemy (async), Alembic, Pydantic |
| Dados | MySQL 8, Redis 7 |
| Fila | TaskIQ (broker Redis Streams) |
| Observabilidade | Elasticsearch, Logstash, Kibana |
| Mobile | Expo / React Native, Expo Notifications |
| Integrações | WhatsApp Cloud API (Meta), Expo Push Service, SMTP |

## Estrutura do repositório

```
app_academia_back/           back-end e infraestrutura
  docker-compose.yml         containers da aplicação
  Dockerfile                 imagem da API, do worker e do scheduler
  app_academia/
    src/back_end/            código da API
      routers/               endpoints HTTP
      services/domain/       regras de negócio
      services/infra/        banco, cache, e-mail, fila, configuração
      auth/                  JWT e tokens assinados de e-mail
      core/                  logging e tratamento global de erros
      alembic/               migrations do banco
    tests/                   testes automatizados

front_end/                   aplicativo Expo / React Native

docs/                        documentação detalhada
```

## Como executar

Pré-requisitos: Docker (ou Podman) e Node.js.

**1. Back-end**

```bash
cd app_academia_back
cp .env.example .env     # preencha as credenciais
docker compose up -d
docker compose exec -w /app/back_end app poetry run alembic upgrade head
```

A API fica disponível em `http://localhost:8000` e a documentação interativa em `http://localhost:8000/docs`.

**2. Aplicativo mobile**

```bash
cd front_end
npm install
npx expo start
```

Configure o endereço da API no arquivo `front_end/.env`:

```
EXPO_PUBLIC_API_URL=http://SEU_IP:8000
```

> Notificações push exigem um *development build* (o Expo Go não suporta push remoto) e um projeto Firebase configurado. O passo a passo está em [docs/arquitetura.md](docs/arquitetura.md).

**3. Testes**

```bash
cd app_academia_back/app_academia
pytest tests
```

## Documentação

- [docs/arquitetura.md](docs/arquitetura.md) — containers, fluxos de requisição e modelo de dados.
- [docs/servicos.md](docs/servicos.md) — o que cada serviço da aplicação faz.
- [docs/api.md](docs/api.md) — referência dos endpoints HTTP.

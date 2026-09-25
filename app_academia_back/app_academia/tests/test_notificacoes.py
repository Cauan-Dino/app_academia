from datetime import date, datetime, time, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient
import httpx2
import pytest
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy import MetaData, String, event, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from back_end.auth.jwt_token import verificar_access_token
from back_end.routers.notificacao.notificacoes import router
from back_end.schemas.notificacao_schema import ResponderReagendamento
from back_end.services.domain.notificacao.dependencies import (
    get_gerenciar_notificacao_service, get_visualizar_notificacao_service,
)
from back_end.services.domain.notificacao.enviar_notificaco_service import NotificacaoService
from back_end.services.domain.notificacao.gerenciar_notificacao_service import GerenciarNotificacaoService
from back_end.services.domain.notificacao import gerenciar_notificacao_service as comandos
from back_end.services.domain.notificacao import visualizar_notificacao_service as consultas
from back_end.services.domain.notificacao.visualizar_notificacao_service import VisualizarNotificacaoService
from back_end.services.infra.database.database import Base
from back_end.services.infra.database.models import (
    Alunos, AulaFixa, DiaDaSemana, Notificacao, ParticipanteAula,
    Personal, SolicitacaoMudanca, StatusSolicitacao,
)
from back_end.services.infra.redis_service.notificacao_cache import chave_notificacoes

pytestmark = pytest.mark.anyio
AGORA = datetime(2026, 9, 14, 12)


class RedisMemoria:
    def __init__(self):
        self.dados = {}
        self.ttls = {}
        self.indisponivel = False

    def verificar(self):
        if self.indisponivel:
            raise RedisConnectionError("Redis de teste indisponível")

    async def get(self, chave):
        self.verificar()
        return self.dados.get(chave)

    async def set(self, chave, valor, ex=None):
        self.verificar()
        self.dados[chave] = valor
        self.ttls[chave] = ex

    async def delete(self, *chaves):
        self.verificar()
        for chave in chaves:
            self.dados.pop(chave, None)


@pytest.fixture
async def cenario(monkeypatch):
    monkeypatch.setattr(consultas, "agora_utc", lambda: AGORA)
    monkeypatch.setattr(comandos, "agora_utc", lambda: AGORA)
    # Mantém o relógio local da validação previsível em qualquer data de execução.
    class Relogio(datetime):
        @classmethod
        def now(cls, tz=None):
            return AGORA.replace(tzinfo=timezone.utc).astimezone(tz)
    monkeypatch.setattr(comandos, "datetime", Relogio)

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    @event.listens_for(engine.sync_engine, "connect")
    def habilitar_fks(conexao, _):
        cursor = conexao.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    # A collation específica do MySQL só precisa ser removida do DDL de teste.
    metadata = MetaData()
    for tabela in Base.metadata.sorted_tables:
        tabela.to_metadata(metadata)
    metadata.tables["alunos"].c.nome.type = String(100)
    async with engine.begin() as conexao:
        await conexao.run_sync(metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    async with factory() as db:
        db.add_all([
            Personal(id=1, nome="Personal um", senha="test", usuario_ativo=True),
            Personal(id=2, nome="Personal dois", senha="test", usuario_ativo=True),
        ])
        await db.flush()
        db.add_all([
            Alunos(id=1, nome="João Silva", telefone="5585999990001", personal_id=1),
            Alunos(id=2, nome="Ana", telefone="5585999990002", personal_id=2),
            AulaFixa(id=1, dia_da_semana=DiaDaSemana.TERCA, horario_inicio=time(8), horario_fim=time(9), personal_id=1, capacidade_max=3),
            AulaFixa(id=2, dia_da_semana=DiaDaSemana.TERCA, horario_inicio=time(8), horario_fim=time(9), personal_id=2, capacidade_max=3),
        ])
        await db.flush()
        db.add_all([
            ParticipanteAula(aula_fixa_id=1, aluno_id=1),
            ParticipanteAula(aula_fixa_id=2, aluno_id=2),
        ])
        for id in (1, 2):
            db.add(SolicitacaoMudanca(
                id=id, personal_id=id, aluno_id=id, aula_fixa_id=id,
                data_hora_aula_original=datetime(2026, 9, 15, 8),
                nova_data_hora_inicio=datetime(2026, 9, 16, 10),
                nova_data_hora_fim=datetime(2026, 9, 16, 11),
                status=StatusSolicitacao.PENDENTE, motivo="Trabalho",
                criada_em=AGORA, expira_em=AGORA + timedelta(days=1),
            ))
        await db.flush()
        db.add_all([
            Notificacao(id=1, personal_id=1, solicitacao_id=1, titulo="Reagendamento", mensagem="Pedido João", criada_em=AGORA),
            Notificacao(id=2, personal_id=2, solicitacao_id=2, titulo="Reagendamento", mensagem="Pedido Ana", criada_em=AGORA),
            Notificacao(id=3, personal_id=1, titulo="Aviso", mensagem="Aviso geral", criada_em=AGORA - timedelta(days=1)),
        ])
        await db.commit()
        redis = RedisMemoria()
        whatsapp = SimpleNamespace(enviar_mensagem_texto=AsyncMock(return_value={"messages": [{"id": "test"}]}))
        query = VisualizarNotificacaoService(db, redis)
        command = GerenciarNotificacaoService(db, redis, whatsapp)
        yield SimpleNamespace(db=db, redis=redis, whatsapp=whatsapp, query=query, command=command, factory=factory)
    await engine.dispose()


async def test_lista_isola_personais_e_reaproveita_cache_com_filtros(cenario, monkeypatch):
    lista = await cenario.query.buscar_notificacoes(1)
    assert [item.id for item in lista] == [1, 3]
    assert lista[0].pode_responder
    assert not lista[1].pode_responder
    assert cenario.redis.ttls[chave_notificacoes(1)] == 60
    assert [item.id for item in await cenario.query.buscar_notificacoes(2)] == [2]
    monkeypatch.setattr(cenario.db, "execute", AsyncMock(side_effect=AssertionError("Cache deveria evitar consulta")))
    assert [item.id for item in await cenario.query.buscar_notificacoes(1, "  JOAO  ", date(2026, 9, 14))] == [1]
    assert [item.id for item in await cenario.query.buscar_notificacoes(1, data=date(2026, 9, 13))] == [3]
    assert await cenario.query.buscar_notificacoes(1, "Ana") == []
    assert await cenario.query.buscar_notificacoes(1, data=date(2026, 9, 12)) == []


@pytest.mark.parametrize("cache", [b"json quebrado", b'[{"id": 123}]', b'null'])
async def test_cache_invalido_consulta_banco(cenario, cache):
    cenario.redis.dados[chave_notificacoes(1)] = cache
    assert len(await cenario.query.buscar_notificacoes(1)) == 2


async def test_redis_indisponivel_nao_bloqueia_leitura_ou_exclusao(cenario):
    cenario.redis.indisponivel = True
    assert len(await cenario.query.buscar_notificacoes(1)) == 2
    await cenario.command.deletar_notificacao(1, 3)
    assert await cenario.db.get(Notificacao, 3) is None


async def test_lista_vazia_tambem_e_cacheada(cenario, monkeypatch):
    assert await cenario.query.buscar_notificacoes(999) == []
    monkeypatch.setattr(cenario.db, "execute", AsyncMock(side_effect=AssertionError("Não deveria consultar")))
    assert await cenario.query.buscar_notificacoes(999) == []


async def test_expiracao_recalculada_ate_em_cache(cenario, monkeypatch):
    await cenario.query.buscar_notificacoes(1)
    monkeypatch.setattr(consultas, "agora_utc", lambda: AGORA + timedelta(days=1))
    lista = await cenario.query.buscar_notificacoes(1)
    assert lista[0].reagendamento.status == StatusSolicitacao.EXPIRADA
    assert not lista[0].pode_responder


async def test_delete_e_permanente_mas_preserva_solicitacao(cenario):
    await cenario.query.buscar_notificacoes(1)
    await cenario.command.deletar_notificacao(1, 1)
    assert chave_notificacoes(1) not in cenario.redis.dados
    assert await cenario.db.get(Notificacao, 1) is None
    assert await cenario.db.get(SolicitacaoMudanca, 1) is not None
    with pytest.raises(HTTPException) as erro:
        await cenario.command.deletar_notificacao(1, 1)
    assert erro.value.status_code == 404


@pytest.mark.parametrize("acao", ["deletar", "responder"])
async def test_outro_personal_nao_pode_alterar_notificacao(cenario, acao):
    with pytest.raises(HTTPException) as erro:
        if acao == "deletar":
            await cenario.command.deletar_notificacao(1, 2)
        else:
            await cenario.command.responder_reagendamento(1, 2, ResponderReagendamento(status="aceita"))
    assert erro.value.status_code == 404
    assert await cenario.db.get(Notificacao, 2) is not None
    assert (await cenario.db.get(SolicitacaoMudanca, 2)).status == StatusSolicitacao.PENDENTE
    cenario.whatsapp.enviar_mensagem_texto.assert_not_awaited()


@pytest.mark.parametrize("status,trecho", [("aceita", "confirmou"), ("recusada", "recusou")])
async def test_responde_e_envia_ao_aluno_apenas_uma_vez(cenario, status, trecho):
    await cenario.query.buscar_notificacoes(1)
    body = ResponderReagendamento(status=status)
    resposta = await cenario.command.responder_reagendamento(1, 1, body)
    assert resposta.status == status and resposta.whatsapp_enviado
    solicitacao = await cenario.db.get(SolicitacaoMudanca, 1)
    assert solicitacao.respondida_em == AGORA
    assert solicitacao.whatsapp_notificada_em == AGORA
    assert (await cenario.db.get(Notificacao, 1)).lida
    assert (await cenario.db.get(AulaFixa, 1)).horario_inicio == time(8)
    assert chave_notificacoes(1) not in cenario.redis.dados
    envio = cenario.whatsapp.enviar_mensagem_texto.call_args.kwargs
    assert envio["telefone"] == "5585999990001"
    assert trecho in envio["texto"] and "16/09/2026 às 10:00" in envio["texto"]
    assert "15/09/2026 às 08:00" in envio["texto"]
    await cenario.command.responder_reagendamento(1, 1, body)
    cenario.whatsapp.enviar_mensagem_texto.assert_awaited_once()
    with pytest.raises(HTTPException) as erro:
        await cenario.command.responder_reagendamento(1, 1, ResponderReagendamento(status="recusada" if status == "aceita" else "aceita"))
    assert erro.value.status_code == 409


@pytest.mark.parametrize("prazo", [AGORA, AGORA - timedelta(seconds=1), AGORA.replace(tzinfo=timezone.utc)])
async def test_nao_responde_no_vencimento_ou_depois(cenario, prazo):
    solicitacao = await cenario.db.get(SolicitacaoMudanca, 1)
    solicitacao.expira_em = prazo
    await cenario.db.commit()
    await cenario.query.buscar_notificacoes(1)
    with pytest.raises(HTTPException) as erro:
        await cenario.command.responder_reagendamento(1, 1, ResponderReagendamento(status="recusada"))
    assert erro.value.status_code == 410
    assert (await cenario.db.get(SolicitacaoMudanca, 1)).status == StatusSolicitacao.EXPIRADA
    assert solicitacao.respondida_em is None
    assert chave_notificacoes(1) not in cenario.redis.dados
    cenario.whatsapp.enviar_mensagem_texto.assert_not_awaited()


@pytest.mark.parametrize("status,codigo", [(StatusSolicitacao.CANCELADA, 409), (StatusSolicitacao.EXPIRADA, 410)])
async def test_estado_final_nao_permite_resposta(cenario, status, codigo):
    solicitacao = await cenario.db.get(SolicitacaoMudanca, 1)
    solicitacao.status = status
    await cenario.db.commit()
    with pytest.raises(HTTPException) as erro:
        await cenario.command.responder_reagendamento(1, 1, ResponderReagendamento(status="aceita"))
    assert erro.value.status_code == codigo
    cenario.whatsapp.enviar_mensagem_texto.assert_not_awaited()


async def test_notificacao_sem_reagendamento(cenario):
    with pytest.raises(HTTPException) as erro:
        await cenario.command.responder_reagendamento(1, 3, ResponderReagendamento(status="aceita"))
    assert erro.value.status_code == 400


async def test_falha_whatsapp_preserva_decisao_e_permite_reenvio_apos_prazo(cenario, monkeypatch):
    cenario.whatsapp.enviar_mensagem_texto.side_effect = httpx2.ConnectError("Falha simulada")
    body = ResponderReagendamento(status="aceita")
    with pytest.raises(HTTPException) as erro:
        await cenario.command.responder_reagendamento(1, 1, body)
    assert erro.value.status_code == 502
    assert erro.value.detail["resposta_salva"] is True
    solicitacao = await cenario.db.get(SolicitacaoMudanca, 1)
    assert solicitacao.status == StatusSolicitacao.ACEITA
    assert solicitacao.respondida_em == AGORA
    assert solicitacao.whatsapp_notificada_em is None
    cenario.whatsapp.enviar_mensagem_texto.side_effect = None
    monkeypatch.setattr(comandos, "agora_utc", lambda: AGORA + timedelta(days=2))
    resposta = await cenario.command.responder_reagendamento(1, 1, body)
    assert resposta.whatsapp_enviado and resposta.respondida_em == AGORA
    assert cenario.whatsapp.enviar_mensagem_texto.await_count == 2


async def test_falha_commit_nao_envia_whatsapp(cenario, monkeypatch):
    monkeypatch.setattr(cenario.db, "commit", AsyncMock(side_effect=SQLAlchemyError("Falha simulada")))
    with pytest.raises(HTTPException) as erro:
        await cenario.command.responder_reagendamento(1, 1, ResponderReagendamento(status="aceita"))
    assert erro.value.status_code == 500
    assert (await cenario.db.get(SolicitacaoMudanca, 1)).status == StatusSolicitacao.PENDENTE
    cenario.whatsapp.enviar_mensagem_texto.assert_not_awaited()


async def test_conflito_de_aula_fixa_impede_aceite_mas_permite_recusa(cenario):
    cenario.db.add(AulaFixa(
        personal_id=1, dia_da_semana=DiaDaSemana.QUARTA,
        horario_inicio=time(10, 30), horario_fim=time(11, 30), capacidade_max=2,
    ))
    await cenario.db.commit()
    with pytest.raises(HTTPException) as erro:
        await cenario.command.responder_reagendamento(1, 1, ResponderReagendamento(status="aceita"))
    assert erro.value.status_code == 409
    assert (await cenario.db.get(SolicitacaoMudanca, 1)).status == StatusSolicitacao.PENDENTE
    cenario.whatsapp.enviar_mensagem_texto.assert_not_awaited()
    assert (await cenario.command.responder_reagendamento(1, 1, ResponderReagendamento(status="recusada"))).whatsapp_enviado


async def test_envio_persiste_notificacao_mesmo_sem_push_token(cenario):
    await cenario.query.buscar_notificacoes(1)
    service = NotificacaoService(cenario.db, cenario.redis)
    service.disparar_a_notificaca_pro_celular_do_personal = AsyncMock()
    assert await service.enviar_notificacao(1, "Novo pedido", "Corpo", solicitacao_id=1)
    assert await cenario.db.scalar(select(func.count()).select_from(Notificacao)) == 4
    assert chave_notificacoes(1) not in cenario.redis.dados
    service.disparar_a_notificaca_pro_celular_do_personal.assert_not_awaited()


@pytest.mark.parametrize("falhar_registro", [False, True])
async def test_chatbot_grava_solicitacao_e_notificacao_na_mesma_transacao(cenario, falhar_registro):
    from back_end.services.domain.chatbot.chatbot_solicitacao_mudanca_aula_service import SolicitacaoReagendamentoAulaService

    sessao = {
        "personal_id": 1, "aluno_id": 1, "aluno_nome": "João Silva", "aula_fixa_id": 1,
        "data_hora_aula_original": "2026-09-15T08:00:00",
        "nova_data_hora_inicio": "2026-09-16T12:00:00",
        "nova_data_hora_fim": "2026-09-16T13:00:00",
    }
    notificacoes = NotificacaoService(cenario.db, cenario.redis)
    if falhar_registro:
        notificacoes.registrar_notificacao = AsyncMock(side_effect=SQLAlchemyError("Falha simulada"))
    service = SolicitacaoReagendamentoAulaService(
        cenario.db, cenario.whatsapp, cenario.redis,
        SimpleNamespace(obter_sessao_ativa_ou_avisar=AsyncMock(return_value=sessao)),
        notificacoes,
    )
    await service._adicionar_motivo_de_reagendamento_aula("Consulta médica", "5585999990001")
    quantidade = await cenario.db.scalar(select(func.count()).select_from(SolicitacaoMudanca))
    quantidade_notificacoes = await cenario.db.scalar(select(func.count()).select_from(Notificacao))
    if falhar_registro:
        assert quantidade == 2 and quantidade_notificacoes == 3
    else:
        assert quantidade == 3 and quantidade_notificacoes == 4
        solicitacao = await cenario.db.scalar(select(SolicitacaoMudanca).order_by(SolicitacaoMudanca.id.desc()))
        notificacao = await cenario.db.scalar(select(Notificacao).order_by(Notificacao.id.desc()))
        assert notificacao.solicitacao_id == solicitacao.id
        assert solicitacao.expira_em - solicitacao.criada_em == timedelta(days=1)


@pytest.mark.parametrize("caso", ["passado", "desvinculado", "mesma_ocorrencia", "sobreposicao"])
async def test_aceite_revalida_aula_e_agenda(cenario, caso):
    solicitacao = await cenario.db.get(SolicitacaoMudanca, 1)
    if caso == "passado":
        solicitacao.nova_data_hora_inicio = datetime(2026, 9, 13, 10)
        solicitacao.nova_data_hora_fim = datetime(2026, 9, 13, 11)
    elif caso == "desvinculado":
        participante = await cenario.db.scalar(select(ParticipanteAula).where(ParticipanteAula.aluno_id == 1))
        await cenario.db.delete(participante)
    else:
        cenario.db.add(SolicitacaoMudanca(
            personal_id=1, aluno_id=1, aula_fixa_id=1,
            data_hora_aula_original=(datetime(2026, 9, 15, 8) if caso == "mesma_ocorrencia" else datetime(2026, 9, 22, 8)),
            nova_data_hora_inicio=datetime(2026, 9, 16, 10, 30),
            nova_data_hora_fim=datetime(2026, 9, 16, 11, 30),
            status=StatusSolicitacao.ACEITA, expira_em=AGORA + timedelta(days=1),
        ))
    await cenario.db.commit()
    with pytest.raises(HTTPException) as erro:
        await cenario.command.responder_reagendamento(1, 1, ResponderReagendamento(status="aceita"))
    assert erro.value.status_code == 409
    assert (await cenario.db.get(SolicitacaoMudanca, 1)).status == StatusSolicitacao.PENDENTE
    cenario.whatsapp.enviar_mensagem_texto.assert_not_awaited()


@pytest.fixture
async def cliente(cenario):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[verificar_access_token] = lambda: {"id": 1}
    app.dependency_overrides[get_visualizar_notificacao_service] = lambda: cenario.query
    app.dependency_overrides[get_gerenciar_notificacao_service] = lambda: cenario.command
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


async def test_rotas_get_patch_delete(cliente):
    resposta = await cliente.get("/notificacoes", params={"nome_aluno": "joao", "data": "2026-09-14"})
    assert resposta.status_code == 200
    assert [item["id"] for item in resposta.json()] == [1]
    assert resposta.json()[0]["criada_em"] == "2026-09-14T12:00:00"
    resposta = await cliente.patch("/notificacoes/1/reagendamento", json={"status": "aceita"})
    assert resposta.status_code == 200 and resposta.json()["status"] == "aceita"
    resposta = await cliente.delete("/notificacoes/1")
    assert resposta.status_code == 204 and resposta.content == b""


@pytest.mark.parametrize("data", ["14/09/2026", "2026-02-30", "2026-09-14T12:00:00"])
async def test_get_valida_date(cliente, data):
    assert (await cliente.get("/notificacoes", params={"data": data})).status_code == 422


@pytest.mark.parametrize("status", ["pendente", "expirada", "confirmada", True, None])
async def test_patch_valida_decisao(cliente, status):
    assert (await cliente.patch("/notificacoes/1/reagendamento", json={"status": status})).status_code == 422


async def test_rotas_exigem_autenticacao():
    app = FastAPI()
    app.include_router(router)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.get("/notificacoes")).status_code == 401
        assert (await client.delete("/notificacoes/1")).status_code == 401
        assert (await client.patch("/notificacoes/1/reagendamento", json={"status": "aceita"})).status_code == 401

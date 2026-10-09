"""Número sem WhatsApp avisado depois, pelo webhook de status da Meta."""

import hashlib
import hmac
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx2
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import MetaData, String, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from back_end.routers.chatbot.webhook import router as rotas_webhook
from back_end.services.domain.aluno.verificacao_telefone_service import VerificacaoTelefoneService
from back_end.services.domain.chatbot import whatsapp_service as modulo_whatsapp
from back_end.services.domain.chatbot.chatbot_conversation_service import ChatbotConversationService
from back_end.services.domain.chatbot.dependencies import get_chat_bot_conversation_service
from back_end.services.domain.chatbot.whatsapp_service import FalhaDeEntrega, WhatsappService
from back_end.services.domain.notificacao.enviar_notificaco_service import NotificacaoService
from back_end.services.infra.database.database import Base
from back_end.services.infra.database.models import Alunos, Notificacao, Personal

pytestmark = pytest.mark.anyio

WAMID = "wamid.HBgMNTU4NTk5OTk5MDAwMRUCABEYEjQ2"


def payload_de_status(*statuses):
    """Formato do webhook da Meta para status de mensagens enviadas."""
    return {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "1329112898881143",
            "changes": [{
                "field": "messages",
                "value": {
                    "messaging_product": "whatsapp",
                    "metadata": {"phone_number_id": "1236018086254673"},
                    "statuses": list(statuses),
                },
            }],
        }],
    }


def status_falho(mensagem_id=WAMID, codigo=131026):
    return {
        "id": mensagem_id,
        "status": "failed",
        "timestamp": "1791500000",
        "recipient_id": "5585999990001",
        "errors": [{"code": codigo, "title": "Message undeliverable"}],
    }


# --------------------------------------------------------------------------
# leitura do webhook e envio do template
# --------------------------------------------------------------------------


def test_extrai_so_os_status_falhos_com_os_codigos():
    payload = payload_de_status(
        status_falho(),
        {"id": "wamid.entregue", "status": "delivered", "recipient_id": "5585999990002"},
    )

    falhas = WhatsappService().extrair_falhas_de_entrega(payload)

    assert falhas == [FalhaDeEntrega(mensagem_id=WAMID, codigos=frozenset({131026}))]


def test_status_nao_e_confundido_com_mensagem_de_texto():
    service = WhatsappService()
    assert service.extrair_mensagem_texto(payload_de_status(status_falho())) is None

    mensagem = {"entry": [{"changes": [{"field": "messages", "value": {"messages": [
        {"from": "5585999990001", "type": "text", "text": {"body": " Oi "}},
    ]}}]}]}
    assert service.extrair_falhas_de_entrega(mensagem) == []
    assert service.extrair_mensagem_texto(mensagem)["texto"] == "oi"


async def test_template_aceito_devolve_o_id_da_mensagem(monkeypatch):
    resposta = httpx2.Response(
        200,
        json={"messaging_product": "whatsapp", "messages": [{"id": WAMID}]},
        request=httpx2.Request("POST", "https://graph.facebook.com"),
    )
    monkeypatch.setattr(modulo_whatsapp, "cliente_http", SimpleNamespace(post=AsyncMock(return_value=resposta)))

    resultado = await WhatsappService().enviar_template(
        telefone="5585999990001", nome_template="boas_vindas", parametros={},
    )

    assert resultado.aceito is True
    assert resultado.mensagem_id == WAMID


def test_webhook_assinado_com_status_falho_aciona_a_verificacao():
    verificacao = SimpleNamespace(registrar_falhas_de_entrega=AsyncMock())
    conversa = ChatbotConversationService(
        whatzap_service=WhatsappService(),
        db=MagicMock(),
        redis_client=MagicMock(),
        chatbot_options_service=MagicMock(),
        chatbot_solicitacao_mudanca_service=MagicMock(),
        utils_chatbot_service=MagicMock(),
        verificacao_telefone_service=verificacao,
    )
    app = FastAPI()
    app.include_router(rotas_webhook)
    app.dependency_overrides[get_chat_bot_conversation_service] = lambda: conversa

    corpo = json.dumps(payload_de_status(status_falho())).encode()
    # O segredo "test" vem do conftest.
    assinatura = "sha256=" + hmac.new(b"test", corpo, hashlib.sha256).hexdigest()
    resposta = TestClient(app).post(
        "/webhooks/whatsapp",
        content=corpo,
        headers={"X-Hub-Signature-256": assinatura, "Content-Type": "application/json"},
    )

    assert resposta.status_code == 200
    verificacao.registrar_falhas_de_entrega.assert_awaited_once_with(
        [FalhaDeEntrega(mensagem_id=WAMID, codigos=frozenset({131026}))]
    )


# --------------------------------------------------------------------------
# marcação do aluno e aviso ao personal
# --------------------------------------------------------------------------


class RedisMemoria:
    def __init__(self):
        self.apagadas = []

    async def delete(self, *chaves):
        self.apagadas.extend(chaves)


@pytest.fixture
async def cenario():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    # A collation específica do MySQL só precisa ser removida do DDL de teste.
    metadata = MetaData()
    for tabela in Base.metadata.sorted_tables:
        tabela.to_metadata(metadata)
    metadata.tables["alunos"].c.nome.type = String(100)
    async with engine.begin() as conexao:
        await conexao.run_sync(metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    async with factory() as db:
        db.add(Personal(id=1, nome="Carlos", senha="test", usuario_ativo=True, push_token="ExponentPushToken[x]"))
        db.add(Alunos(
            id=1, nome="João Silva", telefone="5585999990001", personal_id=1,
            telefone_verificado=True, whatsapp_mensagem_verificacao_id=WAMID,
        ))
        await db.commit()

        redis = RedisMemoria()
        notificacao = NotificacaoService(db=db, redis_client=redis)
        notificacao.disparar_a_notificaca_pro_celular_do_personal = AsyncMock()
        service = VerificacaoTelefoneService(db=db, redis_client=redis, notificacao_service=notificacao)
        yield service, db, notificacao, redis

    await engine.dispose()


async def notificacoes(db):
    return (await db.execute(select(Notificacao))).scalars().all()


async def test_falha_de_destinatario_marca_o_aluno_e_avisa_o_personal(cenario):
    service, db, notificacao, redis = cenario

    await service.registrar_falhas_de_entrega([FalhaDeEntrega(WAMID, frozenset({131026}))])

    aluno = await db.get(Alunos, 1)
    assert aluno.telefone_verificado is False
    assert aluno.whatsapp_mensagem_verificacao_id is None
    [aviso] = await notificacoes(db)
    assert aviso.personal_id == 1
    assert "João Silva" in aviso.mensagem
    push = notificacao.disparar_a_notificaca_pro_celular_do_personal.call_args.kwargs
    assert push["data"]["tipo"] == "telefone_sem_whatsapp"
    assert push["data"]["aluno_id"] == 1
    # O app passa a mostrar o aviso sem esperar o cache expirar.
    assert "alunos:personal:1:todos" in redis.apagadas
    assert "alunos:personal:1:aluno:1" in redis.apagadas


async def test_reentrega_do_mesmo_webhook_nao_repete_o_aviso(cenario):
    service, db, _, _ = cenario
    falha = FalhaDeEntrega(WAMID, frozenset({131026}))

    await service.registrar_falhas_de_entrega([falha])
    await service.registrar_falhas_de_entrega([falha])

    assert len(await notificacoes(db)) == 1


async def test_falha_por_outro_motivo_nao_marca_o_numero(cenario):
    service, db, _, _ = cenario

    # 131047: janela de 24 h expirada; não diz nada sobre o número.
    await service.registrar_falhas_de_entrega([FalhaDeEntrega(WAMID, frozenset({131047}))])

    aluno = await db.get(Alunos, 1)
    assert aluno.telefone_verificado is True
    assert await db.scalar(select(func.count()).select_from(Notificacao)) == 0


async def test_falha_de_mensagem_que_nao_e_de_verificacao_e_ignorada(cenario):
    service, db, _, _ = cenario

    # Ex.: um lembrete ou uma resposta do bot, ou o número antigo já trocado.
    await service.registrar_falhas_de_entrega([FalhaDeEntrega("wamid.outra", frozenset({131026}))])

    aluno = await db.get(Alunos, 1)
    assert aluno.telefone_verificado is True
    assert await db.scalar(select(func.count()).select_from(Notificacao)) == 0

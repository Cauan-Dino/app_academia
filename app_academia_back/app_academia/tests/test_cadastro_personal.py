"""Cadastro do personal: refazer um cadastro pendente e o link de confirmação."""

from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from sqlalchemy import MetaData, String, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from back_end.auth.auth_token_itsdangerous import serializer
from back_end.schemas.personal_schema import CadastroPersonal
from back_end.services.domain.personal.cadastro_personal_service import PersonalCadastroService
from back_end.services.infra.config.settings import settings
from back_end.services.infra.criptografia.criptografia_de_senhas import verificar_senha
from back_end.services.infra.database.database import Base
from back_end.services.infra.database.models import Personal

pytestmark = pytest.mark.anyio

EMAIL = "ana@example.com"


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
        service = PersonalCadastroService(db)
        # Guarda os tokens que iriam no e-mail, sem Redis nem fila.
        service.email_service.enviar_email_confirmacao = AsyncMock()
        yield service, db

    await engine.dispose()


async def cadastrar(service, nome="Ana", senha="senha-um"):
    await service.cadastro_personal(
        CadastroPersonal(nome=nome, email=EMAIL, senha=senha, confirmar_senha=senha)
    )
    return service.email_service.enviar_email_confirmacao.call_args.kwargs["token"]


async def personais(db):
    return (await db.execute(select(Personal).where(Personal.email == EMAIL))).scalars().all()


async def test_refazer_cadastro_pendente_atualiza_os_dados(cenario):
    service, db = cenario
    await cadastrar(service, nome="Ana", senha="senha-um")

    await cadastrar(service, nome="Ana Souza", senha="senha-dois")

    [usuario] = await personais(db)
    assert usuario.nome == "Ana Souza"
    assert verificar_senha("senha-dois", usuario.senha)
    assert usuario.email_verificado is False
    assert service.email_service.enviar_email_confirmacao.await_count == 2


async def test_conta_confirmada_nao_e_sobrescrita(cenario):
    service, db = cenario
    token = await cadastrar(service, senha="senha-um")
    await service.confirmar_email(token)

    with pytest.raises(HTTPException) as erro:
        await cadastrar(service, nome="Outra pessoa", senha="senha-dois")

    assert erro.value.status_code == 409
    [usuario] = await personais(db)
    assert usuario.nome == "Ana"
    assert verificar_senha("senha-um", usuario.senha)


async def test_link_do_cadastro_atual_confirma_a_conta(cenario):
    service, db = cenario
    token = await cadastrar(service)

    await service.confirmar_email(token)

    [usuario] = await personais(db)
    assert usuario.email_verificado is True and usuario.usuario_ativo is True


async def test_link_de_cadastro_refeito_nao_ativa_a_conta(cenario):
    service, db = cenario
    token_antigo = await cadastrar(service, senha="senha-um")
    token_novo = await cadastrar(service, senha="senha-dois")

    with pytest.raises(HTTPException) as erro:
        await service.confirmar_email(token_antigo)
    assert erro.value.status_code == 400
    [usuario] = await personais(db)
    assert usuario.email_verificado is False

    await service.confirmar_email(token_novo)
    assert usuario.email_verificado is True


async def test_link_no_formato_antigo_e_recusado(cenario):
    service, db = cenario
    await cadastrar(service)
    # Antes, o token carregava só o e-mail.
    token_antigo = serializer.dumps(EMAIL, salt="confirmacao-email")

    with pytest.raises(HTTPException) as erro:
        await service.confirmar_email(token_antigo)

    assert erro.value.status_code == 400


# --------------------------------------------------------------------------
# e-mails permitidos
# --------------------------------------------------------------------------


async def test_email_fora_da_lista_nao_cadastra(cenario, monkeypatch):
    service, db = cenario
    monkeypatch.setattr(settings, "EMAILS_PERMITIDOS", "outra@example.com")

    with pytest.raises(HTTPException) as erro:
        await cadastrar(service)

    assert erro.value.status_code == 403
    assert await personais(db) == []
    service.email_service.enviar_email_confirmacao.assert_not_awaited()


async def test_email_da_lista_cadastra_mesmo_com_maiusculas_e_espacos(cenario, monkeypatch):
    service, db = cenario
    monkeypatch.setattr(settings, "EMAILS_PERMITIDOS", " outra@example.com , ANA@Example.com ")

    await cadastrar(service)

    assert len(await personais(db)) == 1


def test_lista_aceita_o_formato_com_colchetes(monkeypatch):
    monkeypatch.setattr(settings, "EMAILS_PERMITIDOS", '["a@gmail.com", "B@gmail.com"]')

    assert settings.emails_permitidos == {"a@gmail.com", "b@gmail.com"}


async def test_lista_vazia_deixa_o_cadastro_aberto(cenario, monkeypatch):
    service, db = cenario
    monkeypatch.setattr(settings, "EMAILS_PERMITIDOS", "")

    await cadastrar(service)

    assert len(await personais(db)) == 1

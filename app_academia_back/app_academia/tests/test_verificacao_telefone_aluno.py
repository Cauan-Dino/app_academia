"""Verificação do telefone do aluno pelo template de boas-vindas do WhatsApp."""

from unittest.mock import AsyncMock

import pytest
from sqlalchemy import MetaData, String, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from back_end.schemas.cadastrar_aluno import CadastrarAluno
from back_end.services.domain.aluno.aluno_command_service import AlunoCommandService
from back_end.services.infra.database.database import Base
from back_end.services.infra.database.models import Alunos, Personal

pytestmark = pytest.mark.anyio

ACCESS_TOKEN = {"id": 1, "nome": "Carlos"}


class RedisMemoria:
    def __init__(self):
        self.dados = {}

    async def get(self, chave):
        return self.dados.get(chave)

    async def set(self, chave, valor, ex=None):
        self.dados[chave] = valor

    async def delete(self, *chaves):
        for chave in chaves:
            self.dados.pop(chave, None)


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
        db.add(Personal(id=1, nome="Carlos", senha="test", usuario_ativo=True))
        await db.commit()

        whatsapp = AsyncMock()
        service = AlunoCommandService(
            db=db,
            redis_client=RedisMemoria(),
            whatsapp_service=whatsapp,
        )
        yield service, db, whatsapp

    await engine.dispose()


async def cadastrar(service, telefone="5585999990001"):
    return await service.cadastrar_aluno(
        body=CadastrarAluno(nome="João Silva", telefone=telefone),
        access_token=ACCESS_TOKEN,
    )


async def test_numero_valido_marca_verificado(cenario):
    service, db, whatsapp = cenario
    whatsapp.enviar_template.return_value = True

    resposta = await cadastrar(service)

    assert resposta["telefone_verificado"] is True
    assert "boas-vindas" in resposta["message"]
    aluno = await db.scalar(select(Alunos).where(Alunos.nome == "João Silva"))
    assert aluno.telefone_verificado is True


async def test_numero_sem_whatsapp_avisa_o_personal(cenario):
    service, db, whatsapp = cenario
    whatsapp.enviar_template.return_value = False

    resposta = await cadastrar(service)

    # O aluno continua cadastrado: só o aviso muda.
    assert resposta["telefone_verificado"] is False
    assert "não recebe WhatsApp" in resposta["message"]
    aluno = await db.scalar(select(Alunos).where(Alunos.nome == "João Silva"))
    assert aluno is not None
    assert aluno.telefone_verificado is False


async def test_falha_na_meta_nao_marca_numero_como_invalido(cenario):
    service, db, whatsapp = cenario
    whatsapp.enviar_template.return_value = None

    resposta = await cadastrar(service)

    # Indeterminado nunca pode virar "número inválido".
    assert resposta["telefone_verificado"] is None
    aluno = await db.scalar(select(Alunos).where(Alunos.nome == "João Silva"))
    assert aluno.telefone_verificado is None


async def test_template_recebe_nome_do_aluno_e_do_personal(cenario):
    service, _, whatsapp = cenario
    whatsapp.enviar_template.return_value = True

    await cadastrar(service, telefone="5585988887777")

    argumentos = whatsapp.enviar_template.call_args.kwargs
    assert argumentos["telefone"] == "5585988887777"
    # Os nomes precisam bater com as variáveis declaradas no template aprovado.
    assert argumentos["parametros"] == {
        "nome_do_aluno": "João Silva",
        "nome_do_personal": "Carlos",
    }

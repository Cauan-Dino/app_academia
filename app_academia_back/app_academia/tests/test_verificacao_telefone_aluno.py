"""Verificação do telefone do aluno pelo template de boas-vindas do WhatsApp."""

from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from sqlalchemy import MetaData, String, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from pydantic import ValidationError

from back_end.schemas.cadastrar_aluno import AlterarInformacoesAluno, CadastrarAluno
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


async def test_numero_sem_whatsapp_recusa_o_cadastro(cenario):
    """Número inválido não pode deixar aluno fantasma: a verificação roda antes do commit."""
    service, db, whatsapp = cenario
    whatsapp.enviar_template.return_value = False

    with pytest.raises(HTTPException) as erro:
        await cadastrar(service)

    assert erro.value.status_code == 400
    assert "não recebe WhatsApp" in erro.value.detail
    # Sem linha no banco, o personal pode corrigir o número e tentar de novo
    # sem esbarrar no 409 do nome duplicado.
    assert await db.scalar(select(func.count()).select_from(Alunos)) == 0


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


# --------------------------------------------------------------------------
# normalização do telefone
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "digitado, esperado",
    [
        ("85999990001", "5585999990001"),        # celular sem DDI
        ("(85) 99999-0001", "5585999990001"),    # com máscara
        ("8533334444", "558533334444"),          # fixo sem DDI
        ("5585999990001", "5585999990001"),      # já tem DDI: não duplica
        ("+55 85 99999-0001", "5585999990001"),  # com + e espaços
        ("351912345678", "351912345678"),        # estrangeiro: passa intacto
    ],
)
def test_telefone_recebe_o_ddi_do_brasil(digitado, esperado):
    assert CadastrarAluno(nome="João", telefone=digitado).telefone == esperado


@pytest.mark.parametrize("invalido", ["999990001", "abc", "", "1" * 16])
def test_telefone_fora_do_tamanho_e_recusado(invalido):
    with pytest.raises(ValidationError):
        CadastrarAluno(nome="João", telefone=invalido)


def test_alteracao_normaliza_igual_ao_cadastro():
    assert AlterarInformacoesAluno(telefone="(85) 99999-0001").telefone == "5585999990001"
    assert AlterarInformacoesAluno(nome="João").telefone is None


# --------------------------------------------------------------------------
# alteração do aluno
# --------------------------------------------------------------------------


@pytest.fixture
async def aluno_existente(cenario):
    """Um aluno já cadastrado e com o número confirmado, pronto para ser alterado."""
    service, db, whatsapp = cenario
    aluno = Alunos(
        nome="João Silva",
        telefone="5585999990001",
        telefone_verificado=True,
        personal_id=1,
    )
    db.add(aluno)
    await db.commit()
    return service, db, whatsapp, aluno


async def alterar(service, aluno_id, **campos):
    return await service.alterar_informacoes_aluno(
        aluno_id=aluno_id,
        body=AlterarInformacoesAluno(**campos),
        access_token=ACCESS_TOKEN,
    )


async def test_alterar_para_numero_sem_whatsapp_recusa_e_nao_altera(aluno_existente):
    """A verificação roda antes do commit: número recusado deixa o aluno intacto."""
    service, db, whatsapp, aluno = aluno_existente
    whatsapp.enviar_template.return_value = False

    with pytest.raises(HTTPException) as erro:
        await alterar(service, aluno.id, telefone="85988887777")

    assert erro.value.status_code == 400
    assert "não recebe WhatsApp" in erro.value.detail
    await db.refresh(aluno)
    assert aluno.telefone == "5585999990001"
    assert aluno.telefone_verificado is True


async def test_alterar_nome_e_telefone_juntos_envia_uma_mensagem_so(aluno_existente):
    """A verificação fica fora do laço que aplica os campos."""
    service, db, whatsapp, aluno = aluno_existente
    whatsapp.enviar_template.return_value = True

    await alterar(service, aluno.id, nome="João Pereira", telefone="85988887777")

    assert whatsapp.enviar_template.await_count == 1
    argumentos = whatsapp.enviar_template.call_args.kwargs
    # O número verificado é o mesmo que será gravado, já com o DDI.
    assert argumentos["telefone"] == "5585988887777"
    # E o nome do payload, não o que ainda está no banco.
    assert argumentos["parametros"]["nome_do_aluno"] == "João Pereira"
    await db.refresh(aluno)
    assert aluno.telefone == "5585988887777"


async def test_alterar_so_o_nome_nao_dispara_envio(aluno_existente):
    service, db, whatsapp, aluno = aluno_existente

    await alterar(service, aluno.id, nome="João Pereira")

    whatsapp.enviar_template.assert_not_awaited()
    await db.refresh(aluno)
    assert aluno.nome == "João Pereira"
    # Sem troca de número, a confirmação anterior continua valendo.
    assert aluno.telefone_verificado is True


async def test_meta_indisponivel_altera_e_marca_como_pendente(aluno_existente):
    """None é 'não deu para confirmar', não 'número inválido': não pode bloquear."""
    service, db, whatsapp, aluno = aluno_existente
    whatsapp.enviar_template.return_value = None

    await alterar(service, aluno.id, telefone="85988887777")

    await db.refresh(aluno)
    assert aluno.telefone == "5585988887777"
    assert aluno.telefone_verificado is None


async def test_alterar_so_o_telefone_usa_o_nome_do_banco(aluno_existente):
    """body.nome é None quando só o telefone muda: o template precisa do nome gravado."""
    service, db, whatsapp, aluno = aluno_existente
    whatsapp.enviar_template.return_value = True

    await alterar(service, aluno.id, telefone="85988887777")

    argumentos = whatsapp.enviar_template.call_args.kwargs
    assert argumentos["parametros"]["nome_do_aluno"] == "João Silva"


async def test_editar_nome_reenviando_o_mesmo_telefone_nao_dispara_envio(aluno_existente):
    """O app sempre manda nome e telefone juntos: o número igual não é uma troca."""
    service, db, whatsapp, aluno = aluno_existente

    await alterar(service, aluno.id, nome="João Pereira", telefone="5585999990001")

    whatsapp.enviar_template.assert_not_awaited()
    await db.refresh(aluno)
    assert aluno.nome == "João Pereira"
    assert aluno.telefone_verificado is True


async def test_mesmo_telefone_com_outra_formatacao_nao_dispara_envio(aluno_existente):
    """A comparação acontece depois da normalização feita pelo schema."""
    service, db, whatsapp, aluno = aluno_existente

    await alterar(service, aluno.id, telefone="(85) 99999-0001")

    whatsapp.enviar_template.assert_not_awaited()
    await db.refresh(aluno)
    assert aluno.telefone == "5585999990001"
    assert aluno.telefone_verificado is True


async def test_telefone_gravado_no_formato_antigo_envia_uma_vez_e_normaliza(aluno_existente):
    """Número salvo antes da normalização conta como troca: verifica e grava no formato novo."""
    service, db, whatsapp, aluno = aluno_existente
    aluno.telefone = "85999990001"
    await db.commit()
    whatsapp.enviar_template.return_value = True

    await alterar(service, aluno.id, telefone="85999990001")

    assert whatsapp.enviar_template.await_count == 1
    await db.refresh(aluno)
    assert aluno.telefone == "5585999990001"

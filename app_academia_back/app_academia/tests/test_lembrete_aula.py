"""Pipeline de lembretes de aula: varredura, reserva, envio e as tasks da fila."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import MetaData, String, event, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from back_end.services.domain.chatbot.utils_chatbot_service import FUSO_HORARIO_ACADEMIA
from back_end.services.domain.notificacao.lembrete_aula_service import LembrenteAulaService
from back_end.services.infra.database.database import Base
from back_end.services.infra.database.models import (
    Alunos,
    AulaFixa,
    DiaDaSemana,
    LembreteAula,
    ParticipanteAula,
    Personal,
    SolicitacaoMudanca,
    StatusLembrete,
    StatusSolicitacao,
)

pytestmark = pytest.mark.anyio

PUSH_TOKEN = "ExponentPushToken[xxxxxxxxxxxxxxxxxxxxxx]"


def naive_utc(momento: datetime) -> datetime:
    """Converte para o formato gravado no banco: UTC sem fuso."""
    return momento.astimezone(timezone.utc).replace(tzinfo=None)


@pytest.fixture
async def cenario(tmp_path):
    # Banco em arquivo, não :memory:. Com :memory: o SQLAlchemy usa StaticPool e
    # todas as sessões compartilham uma conexão — o que esconderia dados ainda
    # não commitados de outra sessão, justamente o que alguns testes verificam.
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'teste.db'}")

    @event.listens_for(engine.sync_engine, "connect")
    def preparar_conexao(conexao_dbapi, _):
        # O serviço monta o horário da ocorrência com TIMESTAMP(data, hora), que
        # só existe no MySQL. Registrar o equivalente exercita a query real.
        conexao_dbapi.create_function("timestamp", 2, lambda data, hora: f"{data} {hora}")
        # WAL permite ler enquanto outra conexão mantém uma escrita aberta.
        conexao_dbapi.execute("PRAGMA journal_mode=WAL")

    # A collation específica do MySQL só precisa ser removida do DDL de teste.
    metadata = MetaData()
    for tabela in Base.metadata.sorted_tables:
        tabela.to_metadata(metadata)
    metadata.tables["alunos"].c.nome.type = String(100)
    async with engine.begin() as conexao:
        await conexao.run_sync(metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    async with factory() as db:
        db.add(Personal(id=1, nome="Carlos", senha="test", usuario_ativo=True, push_token=PUSH_TOKEN))
        db.add(Alunos(id=1, nome="João Silva", telefone="5585999990001", personal_id=1))
        await db.commit()

        notificacao = AsyncMock()
        service = LembrenteAulaService(db=db, notificacao_service=notificacao)
        yield service, db, notificacao, factory

    await engine.dispose()


async def criar_aula_daqui(db, minutos: int, *, com_participante: bool = True) -> AulaFixa:
    """Cria uma aula fixa que começa daqui a N minutos, no horário local."""
    inicio = datetime.now(FUSO_HORARIO_ACADEMIA) + timedelta(minutes=minutos)
    aula = AulaFixa(
        id=1,
        dia_da_semana=tuple(DiaDaSemana)[inicio.weekday()],
        horario_inicio=inicio.time().replace(microsecond=0),
        horario_fim=(inicio + timedelta(hours=1)).time().replace(microsecond=0),
        personal_id=1,
        capacidade_max=5,
    )
    db.add(aula)
    await db.flush()
    if com_participante:
        db.add(ParticipanteAula(aula_fixa_id=aula.id, aluno_id=1))
    await db.commit()
    return aula


async def criar_lembrete(db, *, minutos: int, status=StatusLembrete.PENDENTE, chave="fixa:1:hoje") -> LembreteAula:
    inicio = datetime.now(timezone.utc) + timedelta(minutes=minutos)
    lembrete = LembreteAula(
        personal_id=1,
        aula_fixa_id=1,
        chave_ocorrencia=chave,
        inicio_da_aula=inicio.replace(tzinfo=None),
        programado_para=(inicio - timedelta(minutes=10)).replace(tzinfo=None),
        status=status,
        tentativas=0,
        enviado_em=inicio.replace(tzinfo=None) if status is StatusLembrete.ENVIADO else None,
    )
    db.add(lembrete)
    await db.commit()
    return lembrete


# --------------------------------------------------------------------------
# preparar_lembretes
# --------------------------------------------------------------------------


async def test_aula_nos_proximos_10_minutos_vira_lembrete(cenario):
    service, db, _, _ = cenario
    await criar_aula_daqui(db, minutos=5)

    ids = await service.preparar_lembretes()

    assert len(ids) == 1
    lembrete = await db.get(LembreteAula, ids[0])
    assert lembrete.status is StatusLembrete.PENDENTE
    assert lembrete.tentativas == 0
    assert lembrete.chave_ocorrencia.startswith("fixa:1:")
    # programado_para é sempre 10 minutos antes do início.
    assert lembrete.inicio_da_aula - lembrete.programado_para == timedelta(minutes=10)


async def test_aula_fora_da_janela_nao_vira_lembrete(cenario):
    service, db, _, _ = cenario
    await criar_aula_daqui(db, minutos=40)

    assert await service.preparar_lembretes() == []


async def test_aula_sem_participante_nao_vira_lembrete(cenario):
    service, db, _, _ = cenario
    await criar_aula_daqui(db, minutos=5, com_participante=False)

    assert await service.preparar_lembretes() == []


async def test_personal_inativo_nao_entra_na_varredura(cenario):
    service, db, _, _ = cenario
    await criar_aula_daqui(db, minutos=5)
    personal = await db.get(Personal, 1)
    personal.usuario_ativo = False
    await db.commit()

    assert await service.preparar_lembretes() == []


async def test_varredura_e_idempotente(cenario):
    """Rodar de novo no minuto seguinte não pode duplicar o lembrete."""
    service, db, _, _ = cenario
    await criar_aula_daqui(db, minutos=5)

    primeira = await service.preparar_lembretes()
    segunda = await service.preparar_lembretes()

    assert primeira == segunda
    assert await db.scalar(select(func.count()).select_from(LembreteAula)) == 1


async def test_aula_reagendada_gera_lembrete_proprio(cenario):
    service, db, _, _ = cenario
    aula = await criar_aula_daqui(db, minutos=120)
    novo_inicio = (datetime.now(FUSO_HORARIO_ACADEMIA) + timedelta(minutes=5)).replace(tzinfo=None)
    solicitacao = SolicitacaoMudanca(
        id=7,
        personal_id=1,
        aluno_id=1,
        aula_fixa_id=aula.id,
        data_hora_aula_original=datetime.now().replace(microsecond=0),
        nova_data_hora_inicio=novo_inicio,
        nova_data_hora_fim=novo_inicio + timedelta(hours=1),
        status=StatusSolicitacao.ACEITA,
        expira_em=novo_inicio + timedelta(days=1),
    )
    db.add(solicitacao)
    await db.commit()

    ids = await service.preparar_lembretes()

    assert len(ids) == 1
    lembrete = await db.get(LembreteAula, ids[0])
    assert lembrete.chave_ocorrencia == "reagendamento:7"
    assert lembrete.solicitacao_id == 7


async def test_aluno_que_reagendou_nao_recebe_lembrete_do_horario_original(cenario):
    """O único participante saiu da ocorrência: a aula original não deve lembrar."""
    service, db, _, _ = cenario
    aula = await criar_aula_daqui(db, minutos=5)
    inicio_original = datetime.combine(
        datetime.now(FUSO_HORARIO_ACADEMIA).date(),
        aula.horario_inicio,
    )
    novo_inicio = (datetime.now(FUSO_HORARIO_ACADEMIA) + timedelta(hours=3)).replace(tzinfo=None)
    db.add(
        SolicitacaoMudanca(
            id=9,
            personal_id=1,
            aluno_id=1,
            aula_fixa_id=aula.id,
            data_hora_aula_original=inicio_original,
            nova_data_hora_inicio=novo_inicio,
            nova_data_hora_fim=novo_inicio + timedelta(hours=1),
            status=StatusSolicitacao.ACEITA,
            expira_em=novo_inicio + timedelta(days=1),
        )
    )
    await db.commit()

    assert await service.preparar_lembretes() == []


# --------------------------------------------------------------------------
# processar_lembrete
# --------------------------------------------------------------------------


async def test_lembrete_pendente_vira_enviado(cenario):
    service, db, notificacao, _ = cenario
    lembrete = await criar_lembrete(db, minutos=8)

    await service.processar_lembrete(lembrete_id=lembrete.id)

    await db.refresh(lembrete)
    assert lembrete.status is StatusLembrete.ENVIADO
    assert lembrete.tentativas == 1
    assert lembrete.enviado_em is not None
    argumentos = notificacao.disparar_a_notificaca_pro_celular_do_personal.call_args.kwargs
    assert argumentos["push_token"] == PUSH_TOKEN
    assert argumentos["propagar_erro"] is True
    assert argumentos["data"]["lembrete_id"] == lembrete.id


async def test_lembrete_inexistente_nao_levanta_erro(cenario):
    service, _, notificacao, _ = cenario

    await service.processar_lembrete(lembrete_id=999)

    notificacao.disparar_a_notificaca_pro_celular_do_personal.assert_not_awaited()


async def test_lembrete_ja_enviado_nao_reenvia(cenario):
    """Mensagem duplicada na fila não pode virar notificação duplicada."""
    service, db, notificacao, _ = cenario
    lembrete = await criar_lembrete(db, minutos=8, status=StatusLembrete.ENVIADO)

    await service.processar_lembrete(lembrete_id=lembrete.id)

    await db.refresh(lembrete)
    assert lembrete.status is StatusLembrete.ENVIADO
    assert lembrete.tentativas == 0
    notificacao.disparar_a_notificaca_pro_celular_do_personal.assert_not_awaited()


async def test_lembrete_que_falhou_pode_ser_retentado(cenario):
    service, db, notificacao, _ = cenario
    lembrete = await criar_lembrete(db, minutos=8, status=StatusLembrete.FALHOU)

    await service.processar_lembrete(lembrete_id=lembrete.id)

    await db.refresh(lembrete)
    assert lembrete.status is StatusLembrete.ENVIADO
    notificacao.disparar_a_notificaca_pro_celular_do_personal.assert_awaited_once()


async def test_personal_sem_push_token_cancela(cenario):
    service, db, notificacao, _ = cenario
    personal = await db.get(Personal, 1)
    personal.push_token = None
    await db.commit()
    lembrete = await criar_lembrete(db, minutos=8)

    await service.processar_lembrete(lembrete_id=lembrete.id)

    await db.refresh(lembrete)
    assert lembrete.status is StatusLembrete.CANCELADO
    notificacao.disparar_a_notificaca_pro_celular_do_personal.assert_not_awaited()


async def test_personal_que_excluiu_a_conta_cancela(cenario):
    service, db, notificacao, _ = cenario
    personal = await db.get(Personal, 1)
    personal.usuario_ativo = False
    await db.commit()
    lembrete = await criar_lembrete(db, minutos=8)

    await service.processar_lembrete(lembrete_id=lembrete.id)

    await db.refresh(lembrete)
    assert lembrete.status is StatusLembrete.CANCELADO
    notificacao.disparar_a_notificaca_pro_celular_do_personal.assert_not_awaited()


async def test_aula_que_ja_comecou_cancela(cenario):
    """Um lembrete atrasado na fila não pode avisar de uma aula já iniciada."""
    service, db, notificacao, _ = cenario
    lembrete = await criar_lembrete(db, minutos=-5)

    await service.processar_lembrete(lembrete_id=lembrete.id)

    await db.refresh(lembrete)
    assert lembrete.status is StatusLembrete.CANCELADO
    notificacao.disparar_a_notificaca_pro_celular_do_personal.assert_not_awaited()


async def test_falha_no_envio_marca_falhou_e_propaga(cenario):
    """O status precisa sobreviver, e a exceção precisa subir para o TaskIQ retentar."""
    service, db, notificacao, factory = cenario
    notificacao.disparar_a_notificaca_pro_celular_do_personal.side_effect = RuntimeError("expo fora do ar")
    lembrete = await criar_lembrete(db, minutos=8)

    with pytest.raises(RuntimeError):
        await service.processar_lembrete(lembrete_id=lembrete.id)

    # Lê em outra sessão: o FALHOU tem que estar commitado, não só na memória.
    async with factory() as outra:
        salvo = await outra.get(LembreteAula, lembrete.id)
        assert salvo.status is StatusLembrete.FALHOU
        assert salvo.tentativas == 1


async def test_processando_nunca_fica_gravado_no_banco(cenario):
    """A reserva é a própria transação: PROCESSANDO não pode vazar para o banco."""
    service, db, notificacao, factory = cenario
    lembrete = await criar_lembrete(db, minutos=8)

    async def espiar_o_banco(*_, **__):
        async with factory() as outra:
            visto = await outra.get(LembreteAula, lembrete.id)
            espiar_o_banco.status_visto = visto.status

    notificacao.disparar_a_notificaca_pro_celular_do_personal.side_effect = espiar_o_banco

    await service.processar_lembrete(lembrete_id=lembrete.id)

    assert espiar_o_banco.status_visto is StatusLembrete.PENDENTE


# --------------------------------------------------------------------------
# as tasks da fila
# --------------------------------------------------------------------------


async def test_task_de_varredura_enfileira_um_envio_por_lembrete(cenario, monkeypatch):
    """Garante que a varredura chama a task de ENVIO, não a si mesma."""
    service, db, _, factory = cenario
    from back_end.services.infra.filas.tasks import lembrete_aula_task as tarefas

    await criar_aula_daqui(db, minutos=5)

    monkeypatch.setattr(tarefas, "SessionLocal", factory)
    monkeypatch.setattr(tarefas, "NotificacaoService", lambda db: AsyncMock())
    enfileirados = AsyncMock()
    monkeypatch.setattr(tarefas.fila_enviar_lembrete, "kiq", enfileirados)

    await tarefas.fila_processar_lembrete()

    assert enfileirados.await_count == 1
    lembrete_id = enfileirados.await_args.kwargs["lembrete_id"]
    assert await db.get(LembreteAula, lembrete_id) is not None


async def test_task_de_envio_processa_o_lembrete(cenario, monkeypatch):
    service, db, _, factory = cenario
    from back_end.services.infra.filas.tasks import lembrete_aula_task as tarefas

    lembrete = await criar_lembrete(db, minutos=8)
    monkeypatch.setattr(tarefas, "SessionLocal", factory)
    monkeypatch.setattr(tarefas, "NotificacaoService", lambda db: AsyncMock())

    await tarefas.fila_enviar_lembrete(lembrete_id=lembrete.id)

    async with factory() as outra:
        salvo = await outra.get(LembreteAula, lembrete.id)
        assert salvo.status is StatusLembrete.ENVIADO


def test_labels_das_tasks_estao_registrados():
    from back_end.services.infra.filas.tasks import lembrete_aula_task as tarefas

    # Sem retry_on_error o TaskIQ ignora max_retries: o envio nunca seria retentado.
    assert tarefas.fila_enviar_lembrete.labels["retry_on_error"] is True
    assert tarefas.fila_enviar_lembrete.labels["max_retries"] == 5
    # O timeout precisa ficar abaixo do idle_timeout de 60s do broker,
    # senão outro worker reclama a mensagem e processa o mesmo lembrete.
    assert tarefas.fila_enviar_lembrete.labels["timeout"] < 60
    assert tarefas.fila_processar_lembrete.labels["timeout"] < 60
    assert tarefas.fila_processar_lembrete.labels["schedule"] == [{"interval": 60}]


async def test_scheduler_reconhece_o_agendamento():
    """Uma chave errada em schedule é ignorada em silêncio: só um get_schedules prova."""
    from taskiq.schedule_sources import LabelScheduleSource

    from back_end.services.infra.filas.taskiq.taskiq_app import broker
    from back_end.services.infra.filas.tasks import lembrete_aula_task  # noqa: F401

    fonte = LabelScheduleSource(broker)
    await fonte.startup()
    agendadas = {
        agenda.task_name: agenda.interval
        for agenda in await fonte.get_schedules()
    }

    assert agendadas.get(lembrete_aula_task.fila_processar_lembrete.task_name) == 60


# --------------------------------------------------------------------------
# janela que cruza a meia-noite
# --------------------------------------------------------------------------


@pytest.fixture
def relogio_fixo(monkeypatch):
    """Congela o relógio visto pelo serviço."""
    from back_end.services.domain.notificacao import lembrete_aula_service as servico

    def fixar(momento: datetime):
        class DatetimeFixo(datetime):
            @classmethod
            def now(cls, tz=None):
                return momento.astimezone(tz) if tz else momento.replace(tzinfo=None)

        monkeypatch.setattr(servico, "datetime", DatetimeFixo)

    return fixar


@pytest.mark.xfail(
    reason="A janela compara só a parte de hora: às 23:55 o filtro vira "
           "'> 23:55 AND <= 00:05', que nenhum horário satisfaz.",
)
async def test_aula_fixa_logo_apos_a_meia_noite_gera_lembrete(cenario, relogio_fixo):
    service, db, _, _ = cenario
    agora = datetime.now(FUSO_HORARIO_ACADEMIA).replace(hour=23, minute=55, second=0, microsecond=0)
    amanha = agora + timedelta(minutes=10)
    relogio_fixo(agora)

    db.add(
        AulaFixa(
            id=1,
            dia_da_semana=tuple(DiaDaSemana)[amanha.weekday()],
            horario_inicio=amanha.time().replace(minute=3),
            horario_fim=amanha.time().replace(minute=3, hour=1),
            personal_id=1,
            capacidade_max=5,
        )
    )
    await db.flush()
    db.add(ParticipanteAula(aula_fixa_id=1, aluno_id=1))
    await db.commit()

    assert len(await service.preparar_lembretes()) == 1


async def test_aula_reagendada_logo_apos_a_meia_noite_gera_lembrete(cenario, relogio_fixo):
    """Contraste: o caminho do reagendamento compara datetime completo e funciona."""
    service, db, _, _ = cenario
    agora = datetime.now(FUSO_HORARIO_ACADEMIA).replace(hour=23, minute=55, second=0, microsecond=0)
    novo_inicio = (agora + timedelta(minutes=8)).replace(tzinfo=None)
    relogio_fixo(agora)

    db.add(
        AulaFixa(
            id=1,
            dia_da_semana=DiaDaSemana.SEGUNDA,
            horario_inicio=agora.time(),
            horario_fim=agora.time().replace(hour=23, minute=59),
            personal_id=1,
            capacidade_max=5,
        )
    )
    await db.flush()
    db.add(
        SolicitacaoMudanca(
            id=11,
            personal_id=1,
            aluno_id=1,
            aula_fixa_id=1,
            data_hora_aula_original=agora.replace(tzinfo=None),
            nova_data_hora_inicio=novo_inicio,
            nova_data_hora_fim=novo_inicio + timedelta(hours=1),
            status=StatusSolicitacao.ACEITA,
            expira_em=novo_inicio + timedelta(days=1),
        )
    )
    await db.commit()

    ids = await service.preparar_lembretes()

    assert len(ids) == 1
    lembrete = await db.get(LembreteAula, ids[0])
    assert lembrete.chave_ocorrencia == "reagendamento:11"

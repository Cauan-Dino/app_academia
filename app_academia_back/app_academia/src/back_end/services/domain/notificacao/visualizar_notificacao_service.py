"""Consulta as notificações do personal, com cache-aside e filtros opcionais."""

from datetime import date, datetime, timezone

from pydantic import TypeAdapter, ValidationError
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from back_end.core.logging.logs_settings import logger
from back_end.schemas.notificacao_schema import NotificacaoResposta, ReagendamentoNotificacao
from back_end.services.infra.database.models import Alunos, Notificacao, SolicitacaoMudanca, StatusSolicitacao
from back_end.services.infra.redis_service.notificacao_cache import TTL_NOTIFICACOES, chave_notificacoes
from back_end.services.infra.utils.texto import remover_acentos

NOTIFICACOES_ADAPTER = TypeAdapter(list[NotificacaoResposta])


def agora_utc() -> datetime:
    # DATETIME do MySQL não mantém tzinfo; os prazos são gravados em UTC.
    return datetime.now(timezone.utc).replace(tzinfo=None)


def em_utc_sem_fuso(valor: datetime) -> datetime:
    if valor.tzinfo is not None:
        return valor.astimezone(timezone.utc).replace(tzinfo=None)
    return valor


class VisualizarNotificacaoService:
    def __init__(self, db: AsyncSession, redis_client: Redis):
        self.db = db
        self.redis_client = redis_client


    async def buscar_notificacoes(
        self,
        personal_id: int,
        nome_aluno: str | None = None,
        data: date | None = None,
    ) -> list[NotificacaoResposta]:
        chave = chave_notificacoes(personal_id)
        notificacoes = None
        try:
            cache = await self.redis_client.get(chave)
            if cache is not None:
                notificacoes = NOTIFICACOES_ADAPTER.validate_json(cache)
        except (RedisError, ValidationError, ValueError):
            logger.warning("Cache de notificações indisponível ou inválido; consultando o banco.")

        # Salva no cache
        if notificacoes is None:
            query = (
                select(Notificacao, SolicitacaoMudanca, Alunos.nome)
                .outerjoin(SolicitacaoMudanca, and_(
                    SolicitacaoMudanca.id == Notificacao.solicitacao_id,
                    SolicitacaoMudanca.personal_id == personal_id,
                ))
                .outerjoin(Alunos, and_(
                    Alunos.id == SolicitacaoMudanca.aluno_id,
                    Alunos.personal_id == personal_id,
                ))
                .where(Notificacao.personal_id == personal_id)
                .order_by(Notificacao.criada_em.desc(), Notificacao.id.desc())
            )
            resultado = await self.db.execute(query)
            notificacoes = [
                NotificacaoResposta(
                    id=notificacao.id,
                    solicitacao_id=notificacao.solicitacao_id,
                    titulo=notificacao.titulo,
                    mensagem=notificacao.mensagem,
                    lida=notificacao.lida,
                    criada_em=notificacao.criada_em,
                    aluno_nome=aluno_nome,
                    reagendamento=(
                        ReagendamentoNotificacao.model_validate(solicitacao)
                        if solicitacao is not None else None
                    ),
                )
                for notificacao, solicitacao, aluno_nome in resultado.all()
            ]
            try:
                await self.redis_client.set(
                    chave, NOTIFICACOES_ADAPTER.dump_json(notificacoes), ex=TTL_NOTIFICACOES,
                )
            except RedisError:
                logger.warning("Não foi possível salvar as notificações no cache.")

        # Retorna as notificações
        nome_normalizado = remover_acentos(nome_aluno.strip()) if nome_aluno else ""
        agora = agora_utc()
        filtradas = []
        for notificacao in notificacoes:
            if nome_normalizado and nome_normalizado not in remover_acentos(notificacao.aluno_nome or ""):
                continue
            if data is not None and notificacao.criada_em.date() != data:
                continue
            solicitacao = notificacao.reagendamento
            notificacao.pode_responder = False
            # O tempo pode vencer mesmo durante o TTL: nunca confie no cache para isso.
            if solicitacao is not None and solicitacao.status == StatusSolicitacao.PENDENTE:
                if em_utc_sem_fuso(solicitacao.expira_em) <= agora:
                    solicitacao.status = StatusSolicitacao.EXPIRADA
                else:
                    notificacao.pode_responder = True
            filtradas.append(notificacao)

        return filtradas

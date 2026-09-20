"""Exclusão de notificações e decisão do personal sobre reagendamentos."""

from datetime import datetime

from fastapi import HTTPException
import httpx2
from redis.asyncio import Redis
from sqlalchemy import and_, delete, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from back_end.core.logging.logs_settings import logger
from back_end.schemas.notificacao_schema import ResponderReagendamento, RespostaReagendamento
from back_end.services.domain.chatbot.utils_chatbot_service import FUSO_HORARIO_ACADEMIA
from back_end.services.domain.chatbot.whatsapp_service import WhatsappService
from back_end.services.infra.database.models import (
    Alunos, AulaFixa, DiaDaSemana, Notificacao, ParticipanteAula,
    Personal, SolicitacaoMudanca, StatusSolicitacao,
)
from back_end.services.infra.redis_service.notificacao_cache import invalidar_cache_notificacoes
from .visualizar_notificacao_service import agora_utc, em_utc_sem_fuso


class GerenciarNotificacaoService:
    def __init__(self, db: AsyncSession, redis_client: Redis, whatsapp_service: WhatsappService):
        self.db = db
        self.redis_client = redis_client
        self.whatsapp_service = whatsapp_service


    async def deletar_notificacao(self, personal_id: int, notificacao_id: int) -> None:
        try:
            resultado = await self.db.execute(delete(Notificacao).where(
                Notificacao.id == notificacao_id,
                Notificacao.personal_id == personal_id,
            ))
            if resultado.rowcount == 0:
                raise HTTPException(404, "Notificação não encontrada.")
            await self.db.commit()
        except HTTPException:
            await self.db.rollback()
            raise
        except SQLAlchemyError as erro:
            await self.db.rollback()
            raise HTTPException(500, "Não foi possível excluir a notificação.") from erro
        await invalidar_cache_notificacoes(self.redis_client, personal_id)


    async def responder_reagendamento(
        self, personal_id: int, notificacao_id: int, body: ResponderReagendamento,
    ) -> RespostaReagendamento:
        expirou = False
        try:
            # Mesma trava usada no cadastro de aulas: serializa alterações da agenda.
            personal = await self.db.scalar(select(Personal.id).where(
                Personal.id == personal_id, Personal.usuario_ativo.is_(True),
            ).with_for_update())  

            if personal is None:
                raise HTTPException(401, "Personal não autorizado.")

            notificacao = await self.db.scalar(select(Notificacao).where(
                Notificacao.id == notificacao_id,
                Notificacao.personal_id == personal_id,
            ).with_for_update().execution_options(populate_existing=True))
            if notificacao is None:
                raise HTTPException(404, "Notificação não encontrada.")
            if notificacao.solicitacao_id is None:
                raise HTTPException(400, "Esta notificação não possui solicitação de reagendamento.")

            solicitacao = await self.db.scalar(select(SolicitacaoMudanca).where(
                SolicitacaoMudanca.id == notificacao.solicitacao_id,
                SolicitacaoMudanca.personal_id == personal_id,
            ).with_for_update().execution_options(populate_existing=True))
            if solicitacao is None:
                raise HTTPException(404, "Solicitação de reagendamento não encontrada.")

            agora = agora_utc()
            if solicitacao.status == StatusSolicitacao.EXPIRADA:
                raise HTTPException(410, "O prazo de 24 horas para responder ao reagendamento expirou.")
            if solicitacao.status == StatusSolicitacao.PENDENTE:
                if em_utc_sem_fuso(solicitacao.expira_em) <= agora:
                    solicitacao.status = StatusSolicitacao.EXPIRADA
                    expirou = True
                else:
                    if body.status == StatusSolicitacao.ACEITA:
                        await self._validar_aceite(solicitacao)
                    solicitacao.status = body.status
                    solicitacao.respondida_em = agora
                    notificacao.lida = True
            elif solicitacao.status != body.status:
                raise HTTPException(409, "Esta solicitação já foi respondida ou cancelada e não pode ser alterada.")

            solicitacao_id = solicitacao.id
            await self.db.commit()
        except HTTPException:
            await self.db.rollback()
            raise
        except SQLAlchemyError as erro:
            await self.db.rollback()
            raise HTTPException(500, "Não foi possível salvar a resposta do reagendamento.") from erro

        await invalidar_cache_notificacoes(self.redis_client, personal_id)
        if expirou:
            raise HTTPException(410, "O prazo de 24 horas para responder ao reagendamento expirou.")

        # Somente uma decisão já confirmada no banco pode ser comunicada ao aluno.
        return await self._enviar_resultado_whatsapp(personal_id, solicitacao_id)


    async def _validar_aceite(self, solicitacao: SolicitacaoMudanca) -> None:
        inicio = solicitacao.nova_data_hora_inicio
        fim = solicitacao.nova_data_hora_fim
        agora_local = datetime.now(FUSO_HORARIO_ACADEMIA).replace(tzinfo=None)
        if inicio <= agora_local:
            raise HTTPException(409, "O novo horário da aula já passou.")
        if fim <= inicio or inicio.date() != fim.date():
            raise HTTPException(409, "O intervalo solicitado para a aula é inválido.")

        participante = await self.db.scalar(select(ParticipanteAula.id)
            .join(AulaFixa, AulaFixa.id == ParticipanteAula.aula_fixa_id)
            .join(Alunos, Alunos.id == ParticipanteAula.aluno_id)
            .where(
                ParticipanteAula.aula_fixa_id == solicitacao.aula_fixa_id,
                ParticipanteAula.aluno_id == solicitacao.aluno_id,
                AulaFixa.personal_id == solicitacao.personal_id,
                Alunos.personal_id == solicitacao.personal_id,
            ).with_for_update())
        if participante is None:
            raise HTTPException(409, "O aluno não está mais vinculado à aula solicitada.")

        ja_reagendada = await self.db.scalar(select(SolicitacaoMudanca.id).where(
            SolicitacaoMudanca.id != solicitacao.id,
            SolicitacaoMudanca.aluno_id == solicitacao.aluno_id,
            SolicitacaoMudanca.aula_fixa_id == solicitacao.aula_fixa_id,
            SolicitacaoMudanca.data_hora_aula_original == solicitacao.data_hora_aula_original,
            SolicitacaoMudanca.status == StatusSolicitacao.ACEITA,
        ).limit(1).with_for_update())
        if ja_reagendada is not None:
            raise HTTPException(409, "Esta ocorrência da aula já foi reagendada.")

        aula_fixa = select(AulaFixa.id).where(
            AulaFixa.personal_id == solicitacao.personal_id,
            AulaFixa.dia_da_semana == tuple(DiaDaSemana)[inicio.weekday()],
            AulaFixa.horario_inicio < fim.time(),
            AulaFixa.horario_fim > inicio.time(),
        )
        # Apenas a ocorrência que está sendo movida deixa o seu horário original.
        if inicio.date() == solicitacao.data_hora_aula_original.date():
            aula_fixa = aula_fixa.where(AulaFixa.id != solicitacao.aula_fixa_id)
        if await self.db.scalar(aula_fixa.limit(1).with_for_update()) is not None:
            raise HTTPException(409, "O personal já possui uma aula no período solicitado.")

        sobreposicao = await self.db.scalar(select(SolicitacaoMudanca.id).where(
            SolicitacaoMudanca.id != solicitacao.id,
            or_(
                SolicitacaoMudanca.personal_id == solicitacao.personal_id,
                SolicitacaoMudanca.aluno_id == solicitacao.aluno_id,
            ),
            SolicitacaoMudanca.status == StatusSolicitacao.ACEITA,
            SolicitacaoMudanca.nova_data_hora_inicio < fim,
            SolicitacaoMudanca.nova_data_hora_fim > inicio,
        ).limit(1).with_for_update())
        if sobreposicao is not None:
            raise HTTPException(409, "Já existe uma aula reagendada no período solicitado.")


    async def _enviar_resultado_whatsapp(self, personal_id: int, solicitacao_id: int) -> RespostaReagendamento:
        try:
            # A trava também evita dois envios simultâneos ao repetir o PATCH.
            resultado = await self.db.execute(select(SolicitacaoMudanca, Alunos)
                .join(Alunos, and_(
                    Alunos.id == SolicitacaoMudanca.aluno_id,
                    Alunos.personal_id == personal_id,
                ))
                .where(
                    SolicitacaoMudanca.id == solicitacao_id,
                    SolicitacaoMudanca.personal_id == personal_id,
                ).with_for_update().execution_options(populate_existing=True))
            registro = resultado.first()
            if registro is None:
                raise HTTPException(404, "Solicitação ou aluno não encontrado para envio do WhatsApp.")
            solicitacao, aluno = registro
            if solicitacao.whatsapp_notificada_em is None:
                original = solicitacao.data_hora_aula_original.strftime("%d/%m/%Y às %H:%M")
                novo_inicio = solicitacao.nova_data_hora_inicio.strftime("%d/%m/%Y às %H:%M")
                novo_fim = solicitacao.nova_data_hora_fim.strftime("%H:%M")
                if solicitacao.status == StatusSolicitacao.ACEITA:
                    texto = (
                        f"Olá, {aluno.nome}! Seu personal confirmou o reagendamento da aula "
                        f"de {original} para {novo_inicio}, com término às {novo_fim}."
                    )
                else:
                    texto = (
                        f"Olá, {aluno.nome}! Seu personal recusou o reagendamento da aula "
                        f"para {novo_inicio}, com término às {novo_fim}. "
                        f"Sua aula continua em {original}."
                    )
                await self.whatsapp_service.enviar_mensagem_texto(texto=texto, telefone=aluno.telefone)
                solicitacao.whatsapp_notificada_em = agora_utc()
            resposta = RespostaReagendamento(
                solicitacao_id=solicitacao.id,
                status=solicitacao.status,
                respondida_em=solicitacao.respondida_em,
                whatsapp_enviado=True,
                message="Resposta registrada e envio ao WhatsApp confirmado pela API.",
            )
            await self.db.commit()
            return resposta
        except HTTPException:
            await self.db.rollback()
            raise
        except (httpx2.HTTPError, ValueError, SQLAlchemyError) as erro:
            await self.db.rollback()
            logger.warning("Resposta salva, mas o envio ao WhatsApp não pôde ser confirmado.", extra={
                "solicitacao_id": solicitacao_id, "tipo_erro": type(erro).__name__,
            })
            raise HTTPException(502, {
                "message": "Resposta salva, mas não foi possível confirmar o envio ao WhatsApp. Repita a mesma resposta para tentar novamente.",
                "solicitacao_id": solicitacao_id,
                "resposta_salva": True,
                "whatsapp_enviado": False,
            }) from erro

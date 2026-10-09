"""Marca o telefone do aluno como sem WhatsApp quando a Meta avisa pelo webhook."""

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from back_end.core.logging.logs_settings import logger
from back_end.services.domain.chatbot.whatsapp_service import CODIGOS_DESTINATARIO_INVALIDO, FalhaDeEntrega
from back_end.services.domain.notificacao.enviar_notificaco_service import NotificacaoService
from back_end.services.infra.database.models import Alunos


class VerificacaoTelefoneService:
    """A Meta aceita a mensagem de boas-vindas na hora e só depois informa, pelo
    status "failed", que o número não recebe WhatsApp. Este serviço liga esse
    status ao aluno e avisa o personal."""

    def __init__(self, db: AsyncSession, redis_client: Redis, notificacao_service: NotificacaoService):
        self.db = db
        self.redis_client = redis_client
        self.notificacao_service = notificacao_service


    async def registrar_falhas_de_entrega(self, falhas: list[FalhaDeEntrega]) -> None:
        for falha in falhas:
            if not falha.codigos & CODIGOS_DESTINATARIO_INVALIDO:
                continue

            aluno = await self.db.scalar(
                select(Alunos).where(Alunos.whatsapp_mensagem_verificacao_id == falha.mensagem_id)
            )
            # Falha de outra mensagem (lembrete, resposta do bot) ou de um número
            # que o personal já trocou: não há verificação a atualizar.
            if aluno is None:
                continue

            aluno.telefone_verificado = False
            # Sem o id, uma reentrega do mesmo webhook pela Meta não repete o aviso.
            aluno.whatsapp_mensagem_verificacao_id = None
            # A notificação entra na mesma transação: ou as duas ficam salvas ou nenhuma.
            notificacao = await self.notificacao_service.registrar_notificacao(
                personal_id=aluno.personal_id,
                title="Número sem WhatsApp",
                body=(
                    f"O número de {aluno.nome} não recebe WhatsApp, então ele não vai "
                    "receber as mensagens. Confira o telefone no cadastro do aluno."
                ),
            )
            await self.db.commit()

            logger.info("Telefone do aluno marcado como sem WhatsApp", extra={"aluno_id": aluno.id})
            await self._invalidar_cache_do_aluno(aluno)
            await self.notificacao_service.enviar_notificacao_registrada(
                notificacao,
                data={"tipo": "telefone_sem_whatsapp", "aluno_id": aluno.id},
            )


    async def _invalidar_cache_do_aluno(self, aluno: Alunos) -> None:
        try:
            await self.redis_client.delete(
                f"alunos:personal:{aluno.personal_id}:todos",
                f"alunos:personal:{aluno.personal_id}:aluno:{aluno.id}",
            )
        except Exception as erro:
            logger.warning(
                "Não foi possível invalidar o cache dos alunos",
                extra={"tipo_erro": type(erro).__name__},
                exc_info=False,
            )

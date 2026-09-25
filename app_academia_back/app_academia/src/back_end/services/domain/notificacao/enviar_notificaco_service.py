from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from back_end.core.logging.logs_settings import logger
from back_end.services.infra.database.models import Notificacao, Personal
from back_end.services.infra.redis_service.redis_config import redis_client as redis_padrao
from back_end.services.infra.redis_service.notificacao_cache import invalidar_cache_notificacoes
from redis.asyncio import Redis
from .visualizar_notificacao_service import agora_utc
import httpx2

class NotificacaoService:
    def __init__(self, db: AsyncSession, redis_client: Redis = redis_padrao):
        self.db = db
        self.redis_client = redis_client

    async def disparar_a_notificaca_pro_celular_do_personal(
        self,
        push_token: str, 
        title: str, 
        body: str, 
        data: dict = None,
        propagar_erro: bool = False,
    ) -> None:
        """
        Envia uma push notification ao celular do personal via API da Expo.
        """
        try:
            async with httpx2.AsyncClient() as client:
                response = await client.post(
                    "https://exp.host/--/api/v2/push/send",
                    json={
                        'to': push_token,
                        'title': title,
                        'body': body,
                        'data': data or {}
                    }
                )

                response.raise_for_status()
                result = response.json()
                ticket = result.get('data', {})
                if ticket.get("status") != "ok":
                    raise RuntimeError(
                        "A Expo não confirmou a aceitação do push."
                    )

        except Exception:
            logger.warning(
                'Não foi possível enviar a notificação pro personal',
                exc_info=False
            )
            if propagar_erro:
                raise


    async def _verifica_se_personal_excluiu_a_conta(
        self,
        personal_id: int
    ) -> Personal | None:
        """Verifica se o personal existe e está com a conta ativa."""
        personal = (
                select(Personal)
                .where(
                    Personal.id == personal_id,
                    Personal.usuario_ativo == True,
            )
        )
        return (await self.db.execute(personal)).scalar_one_or_none()
        


    async def enviar_notificacao(
        self,
        personal_id: int, 
        title: str, 
        body: str, 
        data: dict = None,
        solicitacao_id: int | None = None,
    ) -> bool | None:
        """
        Salva a notificação e envia o push, se a conta ainda estiver ativa.

        Retorna False sem enviar nada se o personal não existir/estiver inativo,
        para que o chamador decida como avisar o aluno.
        """
        personal_ativo = await self._verifica_se_personal_excluiu_a_conta(personal_id=personal_id)
        if personal_ativo is None:
            return False

        try:
            notificacao = await self.registrar_notificacao(
                personal_id=personal_id, title=title, body=body, solicitacao_id=solicitacao_id,
            )
            await self.db.commit()
        except Exception:
            await self.db.rollback()
            raise
        await self.enviar_notificacao_registrada(notificacao, data=data)
        return True


    async def registrar_notificacao(
        self, personal_id: int, title: str, body: str, solicitacao_id: int | None = None,
    ) -> Notificacao:
        """Inclui na transação do chamador, permitindo salvar junto à solicitação."""
        notificacao = Notificacao(
            personal_id=personal_id,
            solicitacao_id=solicitacao_id,
            titulo=title,
            mensagem=body,
            criada_em=agora_utc(),
        )
        self.db.add(notificacao)
        await self.db.flush()
        return notificacao


    async def enviar_notificacao_registrada(self, notificacao: Notificacao, data: dict | None = None) -> None:
        """Dispara somente após o commit; a ausência de push token não perde o histórico."""
        await invalidar_cache_notificacoes(self.redis_client, notificacao.personal_id)
        personal = await self._verifica_se_personal_excluiu_a_conta(notificacao.personal_id)
        if personal is None or not personal.push_token:
            return
        await self.disparar_a_notificaca_pro_celular_do_personal(
            push_token=personal.push_token,
            title=notificacao.titulo,
            body=notificacao.mensagem,
            data={
                **(data or {}),
                "notificacao_id": notificacao.id,
                "solicitacao_id": notificacao.solicitacao_id,
            },
        )

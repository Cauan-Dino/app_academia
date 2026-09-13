from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from back_end.core.logging.logs_settings import logger
from back_end.services.infra.database.models import Personal
import httpx2

class NotificacaoService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _disparar_a_notificaca_pro_celular_do_personal(
        self,
        push_token: str, 
        title: str, 
        body: str, 
        data: dict = None
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

                result = response.json()
                ticket = result.get('data', {})
                if ticket.get('status') == 'error':
                    logger.warning(
                        'Expo recusou a notificação: %s',
                        ticket.get('message'),
                    )

        except Exception:
            logger.warning(
                'Não foi possível enviar a notificação pro personal',
                exc_info=False
            )


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
    ) -> bool | None:
        """
        Envia a push notification ao personal, se a conta dele ainda estiver ativa.

        Retorna False sem enviar nada se o personal não existir/estiver inativo,
        para que o chamador decida como avisar o aluno.
        """
        personal_ativo = await self._verifica_se_personal_excluiu_a_conta(personal_id=personal_id)
        if personal_ativo is None:
            return False

        await self._disparar_a_notificaca_pro_celular_do_personal(
            push_token=personal_ativo.push_token,
            title=title,
            body=body,
            data=data
        )
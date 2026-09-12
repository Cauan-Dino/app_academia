from sqlalchemy import select
from back_end.services.infra.database.models import Personal
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from back_end.core.logging.logs_settings import logger

class PushTokenService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def salvar_push_token(self, push_token: str, personal_id: int) -> None:
        """
        Atualiza o push_token do personal autenticado.

        Levanta 404 se o personal não existir ou estiver inativo, e 500 se
        o commit falhar no banco de dados.
        """
        query = select(Personal).where(
            Personal.id == personal_id,
            Personal.usuario_ativo == True,
        )
        personal = (await self.db.execute(query)).scalar_one_or_none()

        if personal is None:
            raise HTTPException(
                status_code=404,
                detail='Esse personal não existe.'
            )

        personal.push_token = push_token

        try:
            await self.db.commit()
        except Exception:
            await self.db.rollback()
            logger.warning(
                f'Ocorreu um erro ao salvar o push_token do personal {personal.id}',
                exc_info=False
            )
            raise HTTPException(
                status_code=500,
                detail='Ocorreu um erro ao salvar o push_token no banco de dados.'
            )
        
        logger.info(f'push_token salvo com sucesso do personal {personal.id}')



        
from .salvar_push_token_service import PushTokenService
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from back_end.services.infra.database.database import sessao_db

def get_push_token_service(
    db: AsyncSession = Depends(sessao_db)
) -> PushTokenService:
    return PushTokenService(db=db)

from redis.asyncio import Redis
from fastapi import Depends
from back_end.services.infra.redis_service.redis_config import get_redis
from back_end.services.infra.database.database import sessao_db
from sqlalchemy.ext.asyncio import AsyncSession
from .aluno_command_service import AlunoCommandService
from .aluno_query_service import AlunoQueryService

def get_personal_client_register_service(
    redis_client: Redis = Depends(get_redis),
    db: AsyncSession = Depends(sessao_db)
    ) -> AlunoCommandService:
    return AlunoCommandService(db=db, redis_client=redis_client)


def get_personal_client_query_service(
    db: AsyncSession = Depends(sessao_db),
    redis_client: Redis = Depends(get_redis)
    ):
    return AlunoQueryService(db=db, redis_client=redis_client)
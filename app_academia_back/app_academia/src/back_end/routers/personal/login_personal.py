from fastapi import Depends, APIRouter, Request
from back_end.services.infra.database.database import sessao_db
from sqlalchemy.ext.asyncio import AsyncSession
from back_end.schemas.personal_schema import LoginPersonal
from back_end.services.domain.personal.login_personal_service import PersonalLoginService
from back_end.services.infra.redis_service.redis_config import redis_client

router = APIRouter(tags=['Login Personal'])

# Login do personal
@router.post('/login')
async def login_personal(
    request: Request,
    body: LoginPersonal,
    db: AsyncSession = Depends(sessao_db),
    ):
    service = PersonalLoginService(db, redis_client)
    return await service.login_personal(body, request=request)
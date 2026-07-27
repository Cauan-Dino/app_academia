from fastapi import Depends, APIRouter
from back_end.services.infra.database.database import sessao_db
from sqlalchemy.ext.asyncio import AsyncSession
from back_end.schemas.personal_schema import LoginPersonal
from back_end.services.domain.personal.login_personal_service import PersonalLoginService

router = APIRouter(tags=['Login Personal'])

# Login do personal
@router.post('/login')
async def login_personal(
    body: LoginPersonal,
    db: AsyncSession = Depends(sessao_db)
    ):
    service = PersonalLoginService(db)
    return await service.login_personal(body)
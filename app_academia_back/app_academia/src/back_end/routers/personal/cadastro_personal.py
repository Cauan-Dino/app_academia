from fastapi import APIRouter, Depends
from back_end.services.infra.database.database import sessao_db
from sqlalchemy.ext.asyncio import AsyncSession
from back_end.schemas.personal_schema import CadastroPersonal
from back_end.services.domain.personal.cadastro_personal_service import PersonalCadastroService

router = APIRouter(tags=['Cadastro Personal'])

@router.post('/cadastro')
async def cadastro_personal(
    body: CadastroPersonal,
    db: AsyncSession = Depends(sessao_db)
    ):
    service = PersonalCadastroService(db)
    return await service.cadastro_personal(body)
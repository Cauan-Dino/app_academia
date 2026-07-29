from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from back_end.services.infra.database.database import sessao_db
from back_end.services.domain.personal.delete_personal_service import DeletePersonalAcountService
from back_end.schemas.personal_schema import DeletarContaPersonal
from back_end.auth.jwt_token import verificar_access_token
from back_end.services.infra.database.models import Usuario

router = APIRouter(tags=['Excluir conta do Personal'])

@router.patch('/deletar-conta')
async def deletar_conta(
    body: DeletarContaPersonal, 
    db: AsyncSession = Depends(sessao_db),
    token: Usuario = Depends(verificar_access_token)
    ):
    service = DeletePersonalAcountService(db)
    return await service.deletar_conta_personal(body=body, access_token=token)

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from back_end.services.infra.database.database import sessao_db
from back_end.services.domain.personal.delete_personal_service import DeletePersonalAcountService
from back_end.services.infra.email.email_service import EmailService
from back_end.schemas.personal_schema import DeletarContaPersonal
from back_end.auth.jwt_token import verificar_access_token
from back_end.services.infra.database.models import Usuario

router = APIRouter(tags=['Excluir conta do Personal'])

@router.post('/deletar-conta')
async def deletar_conta(
    body: DeletarContaPersonal, 
    db: AsyncSession = Depends(sessao_db),
    token: Usuario = Depends(verificar_access_token)
    ):
    service = DeletePersonalAcountService(db)
    return await service.deletar_conta_personal(body=body, access_token=token)



@router.get('/confirmar-exclusao-conta')
async def confirmar_exclusao_conta(
    token: str,
    db: AsyncSession = Depends(sessao_db)
    ):
    service = EmailService(db=db)
    return await service.confirmar_exclusao_de_conta(token)



@router.post('/deletar-conta/reenviar-email')
async def reenviar_email_exclusao_conta(
    access_token: Usuario = Depends(verificar_access_token),
    db: AsyncSession = Depends(sessao_db)
    ):
    service = EmailService(db=db)
    return await service.reenviar_email_exclusao_conta(access_token=access_token)
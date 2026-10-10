from fastapi import APIRouter, Depends
from back_end.services.infra.database.database import sessao_db
from sqlalchemy.ext.asyncio import AsyncSession
from back_end.schemas.personal_schema import CadastroPersonal, ReenviarEmailConfirmacao
from back_end.services.domain.personal.cadastro_personal_service import PersonalCadastroService
from back_end.services.infra.email.email_service import EmailService

router = APIRouter(tags=['Cadastro Personal'])

@router.post('/cadastro')
async def cadastro_personal(
    body: CadastroPersonal,
    db: AsyncSession = Depends(sessao_db)
    ):
    service = PersonalCadastroService(db)
    return await service.cadastro_personal(body)

# Endpoint do link do email enviado
@router.get('/confirmar-email')
async def confirmar_email(
    token: str,
    db: AsyncSession = Depends(sessao_db)
    ):
    service = PersonalCadastroService(db)
    return await service.confirmar_email(token)


@router.post('/reenviar-email')
async def reenviar_email(
    body: ReenviarEmailConfirmacao,
    db: AsyncSession = Depends(sessao_db)
    ):
    service = EmailService(db)
    return await service.reenviar_email(body)

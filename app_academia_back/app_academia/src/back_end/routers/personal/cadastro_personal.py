from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from back_end.services.infra.database.database import sessao_db
from sqlalchemy.ext.asyncio import AsyncSession
from back_end.schemas.personal_schema import CadastroPersonal, ReenviarEmailConfirmacao
from back_end.services.domain.personal.cadastro_personal_service import PersonalCadastroService
from back_end.services.infra.email.email_service import EmailService
from back_end.core.paginas_html import pagina_email_confirmado, pagina_erro

router = APIRouter(tags=['Cadastro Personal'])

@router.post('/cadastro')
async def cadastro_personal(
    body: CadastroPersonal,
    db: AsyncSession = Depends(sessao_db)
    ):
    service = PersonalCadastroService(db)
    return await service.cadastro_personal(body)

# Endpoint do link do email enviado
@router.get('/confirmar-email', response_class=HTMLResponse)
async def confirmar_email(
    token: str,
    db: AsyncSession = Depends(sessao_db)
    ):
    service = PersonalCadastroService(db)
    try:
        await service.confirmar_email(token)
    except HTTPException as erro:
        # Mesmo status code e mensagem de antes, só que em página HTML
        return pagina_erro(erro)

    return pagina_email_confirmado()


@router.post('/reenviar-email')
async def reenviar_email(
    body: ReenviarEmailConfirmacao,
    db: AsyncSession = Depends(sessao_db)
    ):
    service = EmailService(db)
    return await service.reenviar_email(body)

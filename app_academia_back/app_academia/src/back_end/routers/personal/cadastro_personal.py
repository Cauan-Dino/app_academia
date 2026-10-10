from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from back_end.services.infra.database.database import sessao_db
from sqlalchemy.ext.asyncio import AsyncSession
from back_end.schemas.personal_schema import CadastroPersonal, ReenviarEmailConfirmacao
from back_end.services.domain.personal.cadastro_personal_service import PersonalCadastroService
from back_end.services.infra.email.email_service import EmailService
from .pagina_link_email import pagina_email_confirmado, pagina_erro_confirmar_email

router = APIRouter(tags=['Cadastro Personal'])

@router.post('/cadastro')
async def cadastro_personal(
    body: CadastroPersonal,
    db: AsyncSession = Depends(sessao_db)
    ):
    service = PersonalCadastroService(db)
    return await service.cadastro_personal(body)

# Endpoint do link do email enviado: abre no navegador, então responde com uma página
@router.get('/confirmar-email', response_class=HTMLResponse, include_in_schema=False)
async def confirmar_email(
    token: str,
    db: AsyncSession = Depends(sessao_db)
    ) -> HTMLResponse:
    service = PersonalCadastroService(db)
    try:
        resultado = await service.confirmar_email(token)
    except HTTPException as erro:
        return pagina_erro_confirmar_email(erro.status_code)
    return pagina_email_confirmado(ja_confirmado=resultado.get("status") == "ja_confirmado")


@router.post('/reenviar-email')
async def reenviar_email(
    body: ReenviarEmailConfirmacao,
    db: AsyncSession = Depends(sessao_db)
    ):
    service = EmailService(db)
    return await service.reenviar_email(body)

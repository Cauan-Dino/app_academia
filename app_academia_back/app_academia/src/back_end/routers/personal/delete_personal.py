from fastapi import APIRouter, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from back_end.services.infra.database.database import sessao_db
from back_end.services.domain.personal.delete_personal_service import DeletePersonalAcountService
from back_end.services.infra.email.email_service import EmailService
from back_end.schemas.personal_schema import DeletarContaPersonal
from back_end.auth.jwt_token import verificar_access_token
from back_end.auth.auth_token_itsdangerous import validar_token_exclusao_conta
from .pagina_link_email import pagina_confirmar_exclusao, pagina_conta_excluida, pagina_erro_exclusao

router = APIRouter(tags=['Excluir conta do Personal'])

@router.post('/deletar-conta')
async def deletar_conta(
    body: DeletarContaPersonal, 
    db: AsyncSession = Depends(sessao_db),
    token: dict = Depends(verificar_access_token)
    ):
    service = DeletePersonalAcountService(db)
    return await service.solicitar_conta_personal(body=body, access_token=token)



# Link do e-mail: só mostra a confirmação. A exclusão acontece no POST do botão,
# porque alguns provedores de e-mail abrem os links sozinhos para checar segurança.
@router.get('/confirmar-exclusao-conta', response_class=HTMLResponse, include_in_schema=False)
async def pagina_confirmar_exclusao_conta(token: str) -> HTMLResponse:
    try:
        validar_token_exclusao_conta(token=token)
    except HTTPException as erro:
        return pagina_erro_exclusao(erro.status_code)
    return pagina_confirmar_exclusao(token=token, form_action='/confirmar-exclusao-conta')


@router.post('/confirmar-exclusao-conta', response_class=HTMLResponse, include_in_schema=False)
async def confirmar_exclusao_conta(
    token: str = Form(...),
    db: AsyncSession = Depends(sessao_db)
    ) -> HTMLResponse:
    service = DeletePersonalAcountService(db=db)
    try:
        resultado = await service.confirmar_exclusao_de_conta(token)
    except HTTPException as erro:
        return pagina_erro_exclusao(erro.status_code)
    return pagina_conta_excluida(ja_excluida=resultado.get("status") == "ja_excluida")



@router.post('/deletar-conta/reenviar-email')
async def reenviar_email_exclusao_conta(
    access_token: dict = Depends(verificar_access_token),
    db: AsyncSession = Depends(sessao_db)
    ):
    service = EmailService(db=db)
    return await service.reenviar_email_exclusao_conta(access_token=access_token)

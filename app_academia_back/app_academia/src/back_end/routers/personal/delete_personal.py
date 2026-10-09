from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from back_end.services.infra.database.database import sessao_db
from back_end.services.domain.personal.delete_personal_service import DeletePersonalAcountService
from back_end.services.infra.email.email_service import EmailService
from back_end.schemas.personal_schema import DeletarContaPersonal
from back_end.auth.jwt_token import verificar_access_token
from back_end.core.paginas_html import pagina_conta_excluida, pagina_erro

router = APIRouter(tags=['Excluir conta do Personal'])

@router.post('/deletar-conta')
async def deletar_conta(
    body: DeletarContaPersonal, 
    db: AsyncSession = Depends(sessao_db),
    token: dict = Depends(verificar_access_token)
    ):
    service = DeletePersonalAcountService(db)
    return await service.solicitar_conta_personal(body=body, access_token=token)



# Endpoint do link do email enviado
@router.get('/confirmar-exclusao-conta', response_class=HTMLResponse)
async def confirmar_exclusao_conta(
    token: str,
    db: AsyncSession = Depends(sessao_db)
    ):
    service = DeletePersonalAcountService(db=db)
    try:
        await service.confirmar_exclusao_de_conta(token)
    except HTTPException as erro:
        # Mesmo status code e mensagem de antes, só que em página HTML
        return pagina_erro(erro)

    return pagina_conta_excluida()



@router.post('/deletar-conta/reenviar-email')
async def reenviar_email_exclusao_conta(
    access_token: dict = Depends(verificar_access_token),
    db: AsyncSession = Depends(sessao_db)
    ):
    service = EmailService(db=db)
    return await service.reenviar_email_exclusao_conta(access_token=access_token)

from fastapi import APIRouter, Depends
from back_end.services.domain.notificacao.dependencies import get_push_token_service
from back_end.services.domain.notificacao.salvar_push_token_service import PushTokenService
from back_end.auth.jwt_token import verificar_access_token
from back_end.schemas.notificacao_schema import AtualizarPushToken

router = APIRouter(tags=['Salvar/Atualizar o push_token na tabela Personal'])

@router.patch('/personal/push-token')
async def atualizar_push_token(
    body: AtualizarPushToken,
    access_token: dict = Depends(verificar_access_token),
    service: PushTokenService = Depends(get_push_token_service)
) -> dict:
    personal_email = access_token.get('id')
    await service.salvar_push_token(push_token=body.push_token, personal_id=personal_email)
    return {"message": "Token de notificação atualizado."}
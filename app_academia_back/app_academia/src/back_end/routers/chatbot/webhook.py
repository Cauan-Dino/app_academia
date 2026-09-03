from fastapi import APIRouter, Header, Request
from back_end.services.domain.chatbot.webhook_service import WebHook
from fastapi import Response
from fastapi.responses import PlainTextResponse
from back_end.services.domain.chatbot.dependencies import get_webhook_service
from fastapi import Query, Depends

router = APIRouter(
    prefix="/webhooks/whatsapp",
    tags=["Webhook do WhatsApp"],
)


@router.get('')
async def testar_webhook(
    mode: str = Query(alias='hub.mode'),
    verify_token: str = Query(alias='hub.verify_token'),
    challenge: str = Query(alias='hub.challenge'),
    service: WebHook = Depends(get_webhook_service)
    ) -> PlainTextResponse:

    return service.validar_url(
        mode=mode,
        verify_token=verify_token,
        challenge=challenge
    )

@router.post('')
async def receber_webhook(
    request: Request,
    assinatura: str | None = Header(
        default=None,
        alias="X-Hub-Signature-256",
    ),
    service: WebHook = Depends(get_webhook_service),
    ) -> Response:
    
    return await service.receber_webhook(
        request=request,
        assinatura=assinatura
    )
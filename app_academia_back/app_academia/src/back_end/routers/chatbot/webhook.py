from fastapi import APIRouter, Header, Request
from back_end.services.domain.chatbot.whatsapp_service import WhatsappService
from back_end.services.domain.chatbot.chatbot_conversation_service import ChatbotConversationService
from fastapi import Response
from fastapi.responses import PlainTextResponse
from back_end.services.domain.chatbot.dependencies import get_whatsapp_service, get_chat_bot_conversation_service
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
    service: WhatsappService = Depends(get_whatsapp_service)
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
    service: ChatbotConversationService = Depends(get_chat_bot_conversation_service),
    ) -> Response:
    
    return await service.main(
        request=request,
        assinatura=assinatura
    )
from .whatsapp_service import WhatsappService
from .chatbot_conversation_service import ChatbotConversationService
from back_end.services.infra.database.database import sessao_db
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends
from redis.asyncio import Redis
from back_end.services.infra.redis_service.redis_config import get_redis
from .chatbot_opcoes_de_escolha_service import ChatBotOptionsService
from .chatbot_solicitacao_mudanca_aula_service import SolicitacaoReagendamentoAulaService

def get_whatsapp_service() -> WhatsappService:
    return WhatsappService(
        whatsapp_service=WhatsappService()
    )

def get_chat_bot_conversation_service(
        db: AsyncSession = Depends(sessao_db),
        redis_client: Redis = Depends(get_redis)
    ) -> ChatbotConversationService:
    whatsapp_service = WhatsappService()
    return ChatbotConversationService(
        whatzap_service=whatsapp_service,
        db=db,
        redis_client=redis_client,
        chatbot_options_service=ChatBotOptionsService(
            db=db,
            redis_client=redis_client
        ),
        chatbot_solicitacao_mudanca_service=SolicitacaoReagendamentoAulaService(
            db=db, 
            whatsapp_service=whatsapp_service, 
            redis_client=redis_client
        )
    )
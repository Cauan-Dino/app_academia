"""Construção das dependências compartilhadas pelos serviços do chatbot."""

from .whatsapp_service import WhatsappService
from .chatbot_conversation_service import ChatbotConversationService
from back_end.services.infra.database.database import sessao_db
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends
from redis.asyncio import Redis
from back_end.services.infra.redis_service.redis_config import get_redis
from .chatbot_opcoes_de_escolha_service import ChatBotOptionsService
from .chatbot_solicitacao_mudanca_aula_service import SolicitacaoReagendamentoAulaService
from .utils_chatbot_service import UtilsChatbotService
from back_end.services.domain.notificacao.enviar_notificaco_service import NotificacaoService

def get_whatsapp_service() -> WhatsappService:
    """Cria o serviço que valida webhooks e envia mensagens pela API da Meta."""
    return WhatsappService()

def get_chat_bot_conversation_service(
        db: AsyncSession = Depends(sessao_db),
        redis_client: Redis = Depends(get_redis)
    ) -> ChatbotConversationService:
    """Monta a conversa compartilhando Redis, WhatsApp e utilitários.

    A conversa e o reagendamento recebem a mesma instância de
    UtilsChatbotService, vinculada às dependências desta requisição.
    """
    whatsapp_service = get_whatsapp_service()
    utils_chatbot_service = UtilsChatbotService(
        redis_client=redis_client,
        whatsapp_service=whatsapp_service,
    )
    return ChatbotConversationService(
        whatzap_service=whatsapp_service,
        db=db,
        redis_client=redis_client,
        utils_chatbot_service=utils_chatbot_service,
        chatbot_options_service=ChatBotOptionsService(
            db=db,
            redis_client=redis_client
        ),
        chatbot_solicitacao_mudanca_service=SolicitacaoReagendamentoAulaService(
            db=db, 
            whatsapp_service=whatsapp_service, 
            redis_client=redis_client,
            utils_chatbot_service=utils_chatbot_service,
            notificacao_service=NotificacaoService(db=db, redis_client=redis_client),
        )
    )

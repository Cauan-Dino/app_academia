from .salvar_push_token_service import PushTokenService
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from back_end.services.infra.database.database import sessao_db
from redis.asyncio import Redis
from back_end.services.infra.redis_service.redis_config import get_redis
from back_end.services.domain.chatbot.whatsapp_service import WhatsappService
from .visualizar_notificacao_service import VisualizarNotificacaoService
from .gerenciar_notificacao_service import GerenciarNotificacaoService

def get_push_token_service(
    db: AsyncSession = Depends(sessao_db)
) -> PushTokenService:
    return PushTokenService(db=db)


def get_visualizar_notificacao_service(
    db: AsyncSession = Depends(sessao_db),
    redis_client: Redis = Depends(get_redis),
) -> VisualizarNotificacaoService:
    return VisualizarNotificacaoService(db=db, redis_client=redis_client)


def get_gerenciar_notificacao_service(
    db: AsyncSession = Depends(sessao_db),
    redis_client: Redis = Depends(get_redis),
) -> GerenciarNotificacaoService:
    return GerenciarNotificacaoService(db=db, redis_client=redis_client, whatsapp_service=WhatsappService())

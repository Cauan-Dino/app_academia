"""Cache compartilhado pela listagem e pelos pontos que alteram notificações."""

from redis.asyncio import Redis
from redis.exceptions import RedisError

from back_end.core.logging.logs_settings import logger

TTL_NOTIFICACOES = 60


def chave_notificacoes(personal_id: int) -> str:
    return f"notificacoes:personal:{personal_id}:todas"


async def invalidar_cache_notificacoes(redis_client: Redis, personal_id: int) -> None:
    try:
        await redis_client.delete(chave_notificacoes(personal_id))
    except RedisError:
        logger.warning("Não foi possível invalidar o cache de notificações.")

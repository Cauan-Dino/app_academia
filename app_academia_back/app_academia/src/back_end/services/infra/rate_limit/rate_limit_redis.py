from back_end.services.infra.redis_service.redis_config import redis_client
from fastapi import HTTPException

class RateLimitService:

    async def verificar_rate_limit(self, chave: str, limite: int):
        tentativas = await redis_client.get(chave)
        tentativas = int(tentativas) if tentativas else 0

        if tentativas >= limite:
            raise HTTPException(status_code=429, detail='Muitas tentativas. Tente novamente mais tarde.')

        return tentativas



    async def incrementar_rate_limit(self, chave: str, janela_segundos: int):
        novo_valor = await redis_client.incr(chave)
        if novo_valor == 1:
            await redis_client.expire(chave, janela_segundos)
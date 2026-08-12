from redis.asyncio import Redis
from back_end.services.infra.database.models import Personal
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from back_end.auth.usuario_auth import buscar_usuario_autorizado
from back_end.core.logging.logs_settings import logger
import json

async def salvar_status_usuario_cache(
    usuario: Personal,
    redis_client: Redis
    ) -> dict:
    """
    Salva no redis o status do usuario
    Serve para verificar se a conta do usuário ainda está ativa
    A cada 60 segundos verifica se a conta do usuário ainda está ativa
    """

    status = {
        'ativo': usuario.usuario_ativo,
        'email_verificado': usuario.email_verificado,
        'nome': usuario.nome,
        'id': usuario.id,
        'email': usuario.email,
        'token_version': usuario.token_version
    }
    try:
        await redis_client.set(f'usuario_status:{usuario.email}', json.dumps(status), ex=60)
    except Exception:
        logger.exception("Não foi possível salvar o status do usuário no cache")

    return status


async def obter_status_usuario(
    email: str, 
    db: AsyncSession,
    redis_client: Redis
    ) -> dict:
    """
    Retorna um mini objeto de Personal com email/id etc
    Verifica se existe no redis salvo, se sim retorna o valor da chave do redis
    Se não faz uma query 
    """

    chave_redis = f'usuario_status:{email}'
    try:
        cached = await redis_client.get(chave_redis)
    except Exception:
        cached = None

    if cached is not None:
        # existe no Redis → não bate no banco
        status = json.loads(cached)
        if not status['ativo'] or not status['email_verificado']:
            raise HTTPException(status_code=401, detail="Usuário não autorizado.")
        # monta um objeto Personal "leve" com o que precisa, como id/email
    
    else:
        # não existe (expirou ou é a primeira vez) → consulta o banco
        usuario = await buscar_usuario_autorizado(email=email, db=db)

        # Salva no redis uma próxima vez após expirar os status do usuario
        status = await salvar_status_usuario_cache(usuario=usuario, redis_client=redis_client)

    return status
from jose import JWTError, jwt, ExpiredSignatureError
from fastapi import Depends
import os
SECRET_KEY = os.getenv('SECRET_KEY')
from app_academia.src.back_end.services.infra.redis_service.redis_config import redis_client
from fastapi.security import OAuth2PasswordBearer
from datetime import datetime, timezone
import json


from app_academia.src.back_end.services.infra.redis_service.redis_config import redis_client
from app_academia.src.back_end.services.infra.database.models import Usuario
from app_academia.src.back_end.services.infra.database.database import sessao_db
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app_academia.src.back_end.services.infra.database.models import Usuario
from app_academia.src.back_end.auth.usuario_auth import buscar_usuario_autorizado

oauth = OAuth2PasswordBearer(tokenUrl='/login-form')

async def criar_access(
    token_version: int,
    usuario_id: int    
    ):
    payload = {
        'usuario_id': usuario_id,
        'token_version': token_version,
        'exp': datetime.now(timezone.utc) + 30,
        'type':'access'
    }

    token = jwt.encode(payload,SECRET_KEY, algorithm=["HS256"])

    return token



async def verificar_access(
    token: str = Depends(oauth),    
    db: AsyncSession = Depends(sessao_db)
    ):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        id = payload.get('usuario_id')
        type = payload.get('type')
    except JWTError:
        print('token invalido')
    except ExpiredSignatureError:
        print('token expirou')

    if type != 'access':
        raise JWTError('erro')

    redis = await redis_client.get(f'status:{id}')
    if redis is not None:
        payload_redis = json.loads(redis)
        if payload_redis['token_version'] != payload['token_version'] \
        or not payload_redis['ativo'] or not payload_redis['confirmado']:
            print('erro')

    else:
        query = select(Usuario).where(Usuario.id == payload['id'])
        resultado = await db.execute(query)
        usuario = resultado.scalar_one_or_none()

        if usuario is None or not usuario.usuario_ativo or not usuario.email_verificado:
            print('erro')

        payload_redis = {
            'id': usuario.id,
            'email': usuario.email,
            'email_verificado': usuario.email_verificado,
            'ativo': usuario.usuario_ativo,
            'token_version': usuario.token_version
        }

        await redis_client.set(name=f'status:{usuario.id}', value=json.dumps(payload_redis), ex=60)



    if payload_redis['token_version'] != payload['token_version'] \
       or not payload_redis['ativo'] or not payload_redis['confirmado']:
        print('erro')

    return payload_redis  



async def criar_refresh(
        usuario_id: int,
        token_version: int,
        db: AsyncSession = Depends(sessao_db)
    ):
    query = select(Usuario).where(Usuario.id == usuario_id)
    resultado = await db.execute(query)
    usuario = resultado.scalar_one_or_none()
    
    if usuario is None or not usuario.usuario_ativo or not usuario.email_verificado:
        print('erro') 

    payload = {
        'usuario_id': usuario_id,
        'token_version': token_version,
        'exp': datetime.now(timezone.utc) + 30,
        'type':'access'
    }

    token = jwt.encode(payload, SECRET_KEY, algorithm=['HS256'])

    return token


async def verificar_refresh(
    token: str = Depends(oauth),
    db: AsyncSession = Depends(sessao_db)
    ):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
    except JWTError:
        print('erro')
    except ExpiredSignatureError:
        print('erro')

    if payload['type'] != 'refresh':
        print('erro')

    query = select(Usuario).where(Usuario.id == payload['usuario_id'])
    resultado = await db.execute(query)
    usuario = resultado.scalar_one_or_none()
    
    if usuario is None or not usuario.usuario_ativo or not usuario.email_verificado:
        print('erro') 

    if payload['token_version'] != usuario.token_version:
        print('erro')

    return usuario

    
from jose import JWTError,jwt,ExpiredSignatureError
from datetime import datetime,timezone,timedelta
import os
from fastapi import Depends,APIRouter,HTTPException
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm 
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import EmailStr
from back_end.services.infra.database.database import sessao_db
from back_end.services.infra.database.models import Usuario
from back_end.services.infra.redis_service.redis_config import redis_client
import uuid
from back_end.services.infra.criptografia.criptografia_de_senhas import verificar_senha
from back_end.services.infra.redis_service.usuario_status_cache import obter_status_usuario
from back_end.auth.usuario_auth import buscar_usuario_autorizado

oauth = OAuth2PasswordBearer(tokenUrl='/login-form')

router = APIRouter(tags=['JWt Token'])


SECRET_KEY = os.getenv('SECRET_KEY')
TEMPO_REFRESH_TOKEN = int(os.getenv('TEMPO_REFRESH_TOKEN'))
TEMPO_ACCESS_TOKEN = int(os.getenv('TEMPO_ACCESS_TOKEN'))
ALGORITHM = os.getenv('ALGORITHM')


async def criar_refresh_token(
    email: EmailStr,
    token_version: int,
    tempo=timedelta(minutes=TEMPO_REFRESH_TOKEN)
    ) -> str:
    time =  datetime.now(timezone.utc) + tempo
    
    payload = {
        'sub': email,
        'exp': time, # Data de expiração,
        'ver': token_version,
        'jti': str(uuid.uuid4()), # ID único desse token específico
        'iat': datetime.now(timezone.utc), # Data de criação/emissão
        'type': 'refresh'
    }

    token = jwt.encode(payload,SECRET_KEY,ALGORITHM)

    return token



async def criar_access_token(
    email: EmailStr,
    token_version: int,
    time=timedelta(minutes=TEMPO_ACCESS_TOKEN)
    ) -> str:
    tempo = datetime.now(timezone.utc) + time

    payload = {
        'sub': email,
        'ver': token_version,
        'exp': tempo,
        'iat': datetime.now(timezone.utc), # Data de criação/emissão
        'type':'access'
    }
   
    token = jwt.encode(payload,SECRET_KEY,ALGORITHM)

    return token


# Verifica se o token do tipo refresh ainda ta valido
async def verificar_refresh_token(
    db: AsyncSession = Depends(sessao_db), 
    token: str = Depends(oauth)    
    ) -> Usuario:
    try:

        payload = jwt.decode(token,SECRET_KEY,algorithms=[ALGORITHM])
        email = payload.get('sub')
        token_type = payload.get('type')    

    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail='Token expirado!')
    except JWTError:
        raise HTTPException(status_code=401, detail='Token inválido!')

    if email is None or token_type != 'refresh':
        raise HTTPException(
            status_code=401,
            detail='O token precisa ser do tipo refresh.'
        )

    # Exibe mensagem de erro se o token estiver na BLACKLIST (jti so existe no refresh token)
    if await redis_client.get(f'blacklist:{payload.get("jti")}'):
        raise HTTPException(status_code=401, detail='Token revogado')

    usuario = await buscar_usuario_autorizado(email=email, db=db)

    # Verifica se o token_version salvo no banco de dados é o mesmo que foi enviado no payload
    if payload.get('ver') != usuario.token_version:
        raise HTTPException(
            status_code=401,
            detail="Sessão expirada. Faça login novamente."
        )
    
    return usuario



async def verificar_access_token(
    token: str = Depends(oauth),
    db: AsyncSession = Depends(sessao_db) 
    ) -> dict:
    try:

        payload = jwt.decode(token,SECRET_KEY,algorithms=[ALGORITHM])
        email = payload.get('sub')
        token_type = payload.get('type')

    except ExpiredSignatureError:
        raise HTTPException(status_code=401,detail='Token expirado!')
    except JWTError:
        raise HTTPException(status_code=401,detail='Token inválido!')
    
    if email is None or token_type != 'access':
        raise HTTPException(
            status_code=401,
            detail='O token precisa ser do tipo access.'
        )

    status = await obter_status_usuario(email=email, db=db) # Faz uma query buscando pelo email

    # Verifica se o token_version no cache é o mesmo que esta no payload
    if status.get("token_version") != payload.get("ver"):
        raise HTTPException(
            status_code=401,
            detail="Sessão expirada. Faça login novamente."
        )

    return status

        

@router.post('/refresh')
async def gerar_access_token(
    token: str = Depends(oauth),
    db: AsyncSession = Depends(sessao_db),
    usuario: Usuario = Depends(verificar_refresh_token)
    ) -> dict:
    """
    Cria um novo refresh e access token e coloca o antigo na blacklist, invalidando ele
    Se não tiver o jti (id do token) ou Tiver expirado o tempo do token, o usuário precisa fazer login novamente
    """

    try:
        # invalida o refresh token atual (rotation)
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        jti = payload.get('jti') # Pega o id do refresh token
        exp_timestamp = payload.get('exp') 

    except ExpiredSignatureError:
        raise HTTPException(status_code=401,detail='Token expirado!')
    except JWTError:
        raise HTTPException(status_code=401, detail='Token inválido!')

    if jti is None or exp_timestamp is None:
        # Obriga o usuario a fazer login novamente pra Renovar o Refresh token
        raise HTTPException(status_code=401, detail='Token inválido para renovação!')
    
    tempo_restante = max(int(exp_timestamp - datetime.now(timezone.utc).timestamp()), 0) # Tempo restante pra expirar o token - horario atual

    try:
        if tempo_restante > 0:
            # Coloca o antigo refresh token na blacklist
            salvo = await redis_client.set(f'blacklist:{jti}', 'true', ex=tempo_restante, nx=True) # Impede de implementar o mesmo jti na blacklist
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail='Erro ao gerar novos tokens.'
        ) from e

    # Erro: Caso o jti já esteja no Redis
    if not salvo:
        raise HTTPException(
            status_code=401, 
            detail="Token revogado."
        )
    
    access_token = await criar_access_token(email=usuario.email, token_version=usuario.token_version)
    refresh_token = await criar_refresh_token(email=usuario.email, token_version=usuario.token_version, db=db)

    return {
        'access_token':access_token,
        'refresh_token': refresh_token,
        'type':'bearer'
    }



@router.post('/login-form')
async def login_form(
    formulario: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(sessao_db)
    ):
    """Permite utilizar o jwt token na documentação Swagger"""

    # Verifica se o email existe e se o usuario esta ativo
    query = select(Usuario).where(Usuario.email == formulario.username, Usuario.usuario_ativo == True)
    resultado = await db.execute(query)
    usuario = resultado.scalar_one_or_none()

    if not usuario or not verificar_senha(formulario.password, usuario.senha):
        raise HTTPException(
            status_code=401,
            detail='Senha ou email incorretos!'
        )

    if not usuario.usuario_ativo or not usuario.email_verificado:
        raise HTTPException(
            status_code=403,
            detail="Confirme seu e-mail antes de entrar."
        )
    
    access_token = await criar_access_token(email=usuario.email, token_version=usuario.token_version)
    refresh_token = await criar_refresh_token(email=usuario.email, token_version=usuario.token_version)

    return {
        "access_token": access_token,
        "refresh_token":refresh_token,
        "token_type": "Bearer"
    }
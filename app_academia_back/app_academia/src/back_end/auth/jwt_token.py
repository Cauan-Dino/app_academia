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

oauth = OAuth2PasswordBearer(tokenUrl='/login-form')

router = APIRouter(tags=['JWt Token'])


SECRET_KEY = os.getenv('SECRET_KEY')
TEMPO_REFRESH_TOKEN = int(os.getenv('TEMPO_REFRESH_TOKEN'))
TEMPO_ACCESS_TOKEN = int(os.getenv('TEMPO_ACCESS_TOKEN'))
ALGORITHM = os.getenv('ALGORITHM')



async def criar_refresh_token(
    db: AsyncSession,
    email: EmailStr,
    tempo=timedelta(minutes=TEMPO_REFRESH_TOKEN)
    ) -> str:
    time =  datetime.now(timezone.utc) + tempo

    query = select(Usuario).filter(Usuario.email == email)
    resultado = await db.execute(query)
    usuario = resultado.scalar_one_or_none()  

    if usuario is None or not usuario.usuario_ativo or not usuario.email_verificado:
        raise HTTPException(
            status_code=401,
            detail="Usuário não autorizado."
        )
    
    payload = {
        'sub': email,
        'exp': time, # Data de expiração
        'jti': str(uuid.uuid4()), # ID único desse token específico
        'iat': datetime.now(timezone.utc), # Data de criação/emissão
        'type': 'refresh'
    }

    token = jwt.encode(payload,SECRET_KEY,ALGORITHM)

    return token



async def criar_access_token(
    email: EmailStr,
    db: AsyncSession,
    time=timedelta(minutes=TEMPO_ACCESS_TOKEN)
    ) -> str:
    tempo = datetime.now(timezone.utc) + time
    
    query = select(Usuario).filter(Usuario.email == email)
    resultado = await db.execute(query)
    usuario = resultado.scalar_one_or_none() 

    if usuario is None or not usuario.usuario_ativo or not usuario.email_verificado:
        raise HTTPException(
            status_code=401,
            detail="Usuário não autorizado."
        )
    
    payload = {
        'sub': email,
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

    # Verifica se o token esta na BLACKLIST
    if await redis_client.get(f'blacklist:{payload.get("jti")}'):
        raise HTTPException(status_code=401, detail='Token revogado')

    query = select(Usuario).filter(Usuario.email == email)
    resultado = await db.execute(query)
    usuario = resultado.scalar_one_or_none()
    
    if usuario is None or not usuario.usuario_ativo or not usuario.email_verificado:
        raise HTTPException(
            status_code=401,
            detail="Usuário não autorizado."
        )
    
    return usuario



async def verificar_access_token(
    db: AsyncSession = Depends(sessao_db),
    token: str = Depends(oauth),   
    ) -> Usuario:
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
    
    query = select(Usuario).filter(Usuario.email == email)
    resultado = await db.execute(query)
    usuario = resultado.scalar_one_or_none() 

    if usuario is None or not usuario.usuario_ativo or not usuario.email_verificado:
        raise HTTPException(
            status_code=401,
            detail="Usuário não autorizado."
        )
    
    return usuario



@router.get('/refresh')
async def gerar_access_token(
    token: str = Depends(oauth),
    db: AsyncSession = Depends(sessao_db),
    usuario: Usuario = Depends(verificar_refresh_token)
    ) -> dict:
    try:
        # invalida o refresh token atual (rotation)
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        jti = payload.get('jti')
        exp_timestamp = payload.get('exp')

        if jti is None or exp_timestamp is None:
            raise HTTPException(status_code=401, detail='Token inválido para renovação!')
        
        tempo_restante = max(int(exp_timestamp - datetime.now(timezone.utc).timestamp()), 0)

        try:
            if tempo_restante > 0:
                await redis_client.set(f'blacklist:{jti}', 'true', ex=tempo_restante)
        except Exception as e:
            # logger.error(f'Erro ao revogar refresh token no Redis: {e}')
            # DEIXA PASSAR SEM REVOGAR SE DER ERRO NO REDIS
            pass

    except JWTError:
        raise HTTPException(status_code=401, detail='Token inválido!')

    access_token = await criar_access_token(usuario.email,db=db)
    refresh_token = await criar_refresh_token(usuario.email,db=db)

    return {
        'access_token':access_token,
        'refresh_token': refresh_token,
        'type':'bearer'
    }


# Permite utilizar o jwt token na documentação Swagger
@router.post('/login-form')
async def login_form(
    formulario: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(sessao_db)
    ):
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
    
    access_token = await criar_access_token(email=usuario.email,db=db)
    refresh_token = await criar_refresh_token(email=usuario.email,db=db)

    return {
        "access_token": access_token,
        "refresh_token":refresh_token,
        "token_type": "Bearer"
    }
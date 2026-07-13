from jose import JWTError,jwt,ExpiredSignatureError
from datetime import datetime,timezone,timedelta
import os
from fastapi import Depends,APIRouter,HTTPException,status
from dotenv import load_dotenv
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from pydantic import EmailStr
from back_end.database import sessao_db
from back_end.models import Usuario

oauth = OAuth2PasswordBearer(tokenUrl='/login-form')

router = APIRouter(tags=['JWt Token'])

# load_dotenv()

SECRET_KEY = os.getenv('SECRET_KEY')
TEMPO_REFRESH_TOKEN = int(os.getenv('TEMPO_REFRESH_TOKEN'))
TEMPO_ACCESS_TOKEN = int(os.getenv('TEMPO_ACCESS_TOKEN'))
ALGORITHM = os.getenv('ALGORITHM')



def criar_refresh_token(
        email: EmailStr,
        tempo=timedelta(minutes=TEMPO_REFRESH_TOKEN),
        db: Session = Depends(sessao_db)
    ):
    time =  datetime.now(timezone.utc) + tempo

    usuario = db.query(Usuario).filter(Usuario.email == email).first()
    
    # Verifica se o usuario existe e esta ativo
    if usuario is None or usuario.usuario_ativo is False:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Esse usuário não existe!'
        )
    
    payload = {
        'sub': email,
        'exp': time,
        'type': 'refresh'
    }

    token = jwt.encode(payload,SECRET_KEY,ALGORITHM)

    return token



def criar_access_token(
        email: EmailStr,
        time=timedelta(minutes=TEMPO_ACCESS_TOKEN),
        db: Session = Depends(sessao_db)
    ):
    tempo = datetime.now(timezone.utc) + time
    # Verifica se o usuario existe
    usuario = db.query(Usuario).filter(Usuario.email == email).first()
    if usuario is None or usuario.usuario_ativo is False:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Esse usuário não existe!'
        )
    
    payload = {
        'sub': email,
        'exp': tempo,
        'type':'access'
    }

    token = jwt.encode(payload,SECRET_KEY,ALGORITHM)

    return token



# Verifica se o token do tipo refresh ainda ta valido
def verificar_refresh_token(
    token: str = Depends(oauth),
    db: Session = Depends(sessao_db)    
    ):
    try:
        payload = jwt.decode(token,SECRET_KEY,algorithms=[ALGORITHM])
        email = payload.get('sub')
        token_type = payload.get('type')    
    except ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Token expirado!')
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Token inválido!')
    
    # Verifica se o token é do tipo refresh
    if token_type != 'refresh':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='O token precisa ser do tipo refresh.'
        )
    
    # Verifica se o usuario existe e está ativo
    usuario = db.query(Usuario).filter(Usuario.email == email).first()
    if usuario is None or usuario.usuario_ativo is False:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Esse usuário não existe!'
        )
    
    return usuario




def verificar_access_token(
    token: str = Depends(oauth),
    db: Session = Depends(sessao_db)    
    ):
    try:
        payload = jwt.decode(token,SECRET_KEY,algorithms=[ALGORITHM])
        email = payload.get('sub')
        token_type = payload.get('type')
    except ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail='Token expirado!')
    except JWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED,detail='Token inválido!')
    
    # Verifica se o token é do tipo refresh
    if token_type != 'refresh':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='O token precisa ser do tipo refresh.'
        )
    
    # Verifica se o usuario existe e está ativo
    usuario = db.query(Usuario).filter(Usuario.email == email).first()
    if usuario is None or usuario.usuario_ativo is False:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Esse usuário não existe!'
        )
    
    return usuario



@router.get('/refresh')
async def gerar_access_token(
    db: Session = Depends(sessao_db),
    usuario: Usuario = Depends(verificar_refresh_token)
    ):
    token = criar_refresh_token(usuario.email,db=db)
    return {
        'access_token':token,
        'type':'Bearer'
    }
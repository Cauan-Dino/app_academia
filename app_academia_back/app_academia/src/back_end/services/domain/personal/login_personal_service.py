from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from back_end.services.infra.database.models import Usuario
from back_end.schemas.personal_schema import LoginPersonal
from sqlalchemy import select
from back_end.auth.jwt_token import criar_access_token, criar_refresh_token
from back_end.services.infra.criptografia.criptografia_de_senhas import verificar_senha

class PersonalLoginService:
    def __init__(self, db: AsyncSession):
        self.db = db


    async def login_personal(self, body: LoginPersonal) -> dict:
        # Verifica se o usuario EXISTE e está ATIVO
        query = select(Usuario).filter(Usuario.email == body.email, Usuario.usuario_ativo == True)
        resultado = await self.db.execute(query)
        usuario = resultado.scalar_one_or_none()

        if usuario is None:
            raise HTTPException(
                status_code=401,
                detail='Senha ou email incorretos!'
            )
        
        # Verifica se as senhas coincidem
        if not verificar_senha(body.senha, usuario.senha):
            raise HTTPException(
                status_code=401,
                detail='Senha ou email incorretos!'
            )
        
        refresh_token = await criar_refresh_token(email=usuario.email,db=self.db) # Cria o refresh token
        access_token = await criar_access_token(email=usuario.email,db=self.db) # Cria access token

        return {
            'access_token':access_token,
            'refresh_token':refresh_token,
            'type':'Bearer'
        }
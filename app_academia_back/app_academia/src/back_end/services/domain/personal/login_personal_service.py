from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from back_end.services.infra.database.models import Usuario
from back_end.schemas.personal_schema import LoginPersonal
from sqlalchemy import select
from back_end.auth.jwt_token import criar_access_token, criar_refresh_token
from back_end.services.infra.criptografia.criptografia_de_senhas import verificar_senha
from back_end.core.logging.logs_settings import logger

class PersonalLoginService:
    def __init__(self, db: AsyncSession):
        self.db = db


    async def login_personal(self, body: LoginPersonal) -> dict:
        # Verifica se o usuario EXISTE e está ATIVO
        query = select(Usuario).where(Usuario.email == body.email)
        resultado = await self.db.execute(query)
        usuario = resultado.scalar_one_or_none()

        if usuario is None or not verificar_senha(body.senha, usuario.senha):
            raise HTTPException(status_code=401, detail='Senha ou email incorretos!')
        # Impede o usuario de entrar se o email NÃO estiver VERIFICADO
        if not usuario.usuario_ativo or not usuario.email_verificado:
            raise HTTPException(status_code=403, detail="Confirme seu e-mail antes de entrar.")
        
        access_token = await criar_access_token(email=usuario.email, token_version=usuario.token_version)
        refresh_token = await criar_refresh_token(email=usuario.email, token_version=usuario.token_version, db=self.db)

        logger.info('Login personal realizado', extra={'usuario_id': usuario.id})
        return {
            'access_token':access_token,
            'refresh_token':refresh_token,
            'type':'Bearer'
        }
from back_end.services.infra.database.models import Usuario
from datetime import datetime, timezone
from fastapi import HTTPException, APIRouter
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from back_end.auth.auth_token_itsdangerous import validar_token_confirmacao_email, gerar_token_confirmacao_email, gerar_token_exclusao_conta, validar_token_exclusao_conta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from back_end.services.infra.redis_service.redis_config import redis_client
import os
from back_end.schemas.personal_schema import ReenviarEmailConfirmacao
from back_end.core.logging.logs_settings import logger

router = APIRouter(tags=['Envio de email'])

conf = ConnectionConfig(
    MAIL_USERNAME=os.getenv('EMAIL_USERNAME'),
    MAIL_PASSWORD=os.getenv('EMAIL_PASSWORD'),
    MAIL_FROM=os.getenv('EMAIL_FROM'),
    MAIL_PORT=465,
    MAIL_SERVER=os.getenv('EMAIL_SERVER'), 
    MAIL_STARTTLS=False,
    MAIL_SSL_TLS=True,
)

class EmailService:
    def __init__(self, db: AsyncSession):
        self.db = db


    # Verifica se o usuário pode enviar outro email
    async def verificar_cooldown_de_envio_email(self, chave_redis: str, cooldown_segundos: int = 60) -> None:
        """Verifica o cooldown pra poder reenviar o email"""
        tempo_restante = await redis_client.ttl(chave_redis)

        if tempo_restante > 0:
            raise HTTPException(status_code=429, detail=f"Aguarde {tempo_restante}s para solicitar outro e-mail.")

        # Salva no redis o cooldown, impedindo o Reenvio até a chave ser apagada
        await redis_client.set(chave_redis, 'enviado', ex=cooldown_segundos) 


    # Envia de fato o email
    async def enviar_email_confirmacao(self, token: str, email: str, usuario_id: int) -> None:
        """Envia o email de confirmação de criação de conta"""
        chave_redis = f'cooldown:email_confirmacao:{usuario_id}'
        await self.verificar_cooldown_de_envio_email(chave_redis=chave_redis)

        try:
            link_confirmacao = f"https://seuapp.com/confirmar-email?token={token}"

            mensagem = MessageSchema(
                subject='Confirme seu e-mail',
                recipients=[email],
                body=f"Clique no link para confirmar seu e-mail: {link_confirmacao}",
                subtype=MessageType.html
            )

            fm = FastMail(conf)
            await fm.send_message(mensagem) # Dispara o email
            logger.info('E-mail de confirmação enviado', extra={'usuario_id': usuario_id})

        # Trata algum possível erro na hora de enviar o email
        except Exception:
            await redis_client.delete(chave_redis) # Deleta a chave salva no redis no inicio
            raise HTTPException(status_code=503, detail="Não foi possível enviar o e-mail. Tente novamente.")



    async def confirmar_email(self, token: str) -> dict:
        """Confirma o email clicando no link enviado no email"""
        email = validar_token_confirmacao_email(token=token)

        # Verifica se o email existe    
        query = select(Usuario).where(Usuario.email == email)
        resultado = await self.db.execute(query)
        usuario = resultado.scalar_one_or_none()

        if usuario is None:
            raise HTTPException(
                status_code=404,
                detail='Usuário não encontrado.'
            )

        # Verifica se o email já tá verificado
        if usuario.email_verificado is True:
            return {"detail": "E-mail já confirmado anteriormente."}

        usuario.email_verificado = True # Confirma o email
        usuario.usuario_ativo = True # Ativa a conta do usuario

        await self.db.commit()
        await self.db.refresh(usuario)

        logger.info('E-mail confirmado', extra={'usuario_id': usuario.id})
        return {'message':"E-mail confirmado com sucesso!"}



    async def reenviar_email(self, body: ReenviarEmailConfirmacao) -> dict:
        """Reenvia o email pra confirmar a conta"""
        query = select(Usuario).where(Usuario.email == body.email)
        resultado = await self.db.execute(query)
        usuario = resultado.scalar_one_or_none()

        if usuario is None or usuario.email_verificado == True:
            logger.info('Conta inexistente ou email já verificado')
            return {"message": "Se existir uma conta pendente, enviaremos um novo link de confirmação."}

        token = gerar_token_confirmacao_email(body.email)

        await self.enviar_email_confirmacao(
            token=token, 
            email=body.email, 
            usuario_id=usuario.id
        )

        return {"message": "Se existir uma conta pendente, enviaremos um novo link de confirmação."}

    # --- Excluir conta --------------------

    async def enviar_email_confirmacao_exclusao_conta(self, email: str, usuario_id: int, token: str) -> None:
        """Envia email pra confirmar exclusão de conta"""
        chave_redis = f'cooldown:email_confirmacao_exclusao_de_conta:{usuario_id}'
        await self.verificar_cooldown_de_envio_email(chave_redis=chave_redis)

        try:
            link_confirmacao = f"https://seuapp.com/confirmar-exclusao-conta?token={token}"

            mensagem = MessageSchema(
                subject='Exclusão de conta',
                recipients=[email],
                body=f"Clique no link para excluir sua conta: {link_confirmacao}",
                subtype=MessageType.html
            )

            fm = FastMail(conf)
            await fm.send_message(mensagem) # Dispara o email
            logger.info('E-mail de confirmação de exclusão de conta enviado', extra={'usuario_id': usuario_id})

        # Trata algum possível erro na hora de enviar o email
        except Exception:
            await redis_client.delete(chave_redis) # Deleta a chave salva no redis no inicio
            raise HTTPException(status_code=503, detail="Não foi possível enviar o e-mail. Tente novamente.")


    async def confirmar_exclusao_de_conta(self, token: str):
        """Confirma a exclusão da conta no link do email enviado"""
        email = validar_token_exclusao_conta(token=token)

        # Verifica se o email existe  
        query = select(Usuario).where(Usuario.email == email)
        resultado = await self.db.execute(query)
        usuario = resultado.scalar_one_or_none()

        if usuario is None:
            raise HTTPException(
                status_code=404,
                detail='Usuário não encontrado.'
            )

        # Verifica se a conta ja foi excluida
        if usuario.usuario_ativo == False:
            return {'message':'Usuário já está excluido!'}

        # Exclui logicamente a conta do usuario
        usuario.usuario_ativo = False
        usuario.email_verificado = False
        try:
            await self.db.commit()
        except:
            await self.db.rollback()
            raise HTTPException(status_code=500, detail='Ocorreu um erro desconhecido.')

        logger.info('Conta Excluída', extra={'usuario_id': usuario.id})
        return {'message':"Conta Excluída com sucesso!"}



    async def reenviar_email_exclusao_conta(self, access_token: Usuario) -> dict:
        """Reenvia o email pra excluir a conta"""
        query = select(Usuario).where(Usuario.email == access_token.email)
        resultado = await self.db.execute(query)
        usuario = resultado.scalar_one_or_none()

        if usuario is None or usuario.usuario_ativo == False:
            logger.info('Usuário não existe ou já está excluído logicamente', extra={'usuario_id': access_token.id})
            return {"message": "Se existir uma conta pendente, enviaremos um novo link de confirmação."}

        token = gerar_token_exclusao_conta(access_token.email)

        await self.enviar_email_confirmacao_exclusao_conta(
            token=token, 
            email=access_token.email, 
            usuario_id=usuario.id
        )

        return {"message": "Se existir uma conta pendente, enviaremos um novo link de confirmação."}
        
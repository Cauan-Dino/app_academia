from back_end.services.infra.database.models import Usuario
from fastapi import HTTPException, APIRouter
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from back_end.auth.auth_token_itsdangerous import (
    gerar_token_confirmacao_email, 
    gerar_token_exclusao_conta,
    gerar_token_alterar_senha
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from back_end.services.infra.redis_service.redis_config import redis_client
import os
from back_end.schemas.personal_schema import ReenviarEmailConfirmacao, EnviarEmailRedefinirSenha, AlterarSenhaPersonal
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


    async def _enviar_email(
            self, 
            token: str, 
            mensagem_email: str, 
            subject: str, 
            destinatario: str, 
            body: str, 
            usuario_id: int,
            chave_redis: str
        ) -> None:
        """
        Método helper que envia o email e salva a chave de cooldown no redis
        Evitando com que o usuário possa pedir um novo email dentro do tempo de expiração salvo no redis
        """
        redis_key = f'{chave_redis}:{usuario_id}'
        await self.verificar_cooldown_de_envio_email(chave_redis=redis_key)

        try:
            link_confirmacao = f"https://seuapp.com/{mensagem_email}?token={token}"
            mensagem = MessageSchema(
                subject=subject,
                recipients=[destinatario],
                body=f'{body}: {link_confirmacao}',
                subtype=MessageType.html
            )
            fm = FastMail(conf)
            await fm.send_message(mensagem) # Dispara o email

        except Exception:
            await redis_client.delete(redis_key) # Deleta a chave salva no redis no inicio
            raise HTTPException(status_code=503, detail="Não foi possível enviar o e-mail. Tente novamente.")

            

    async def verificar_cooldown_de_envio_email(
            self, 
            chave_redis: str, 
            cooldown_segundos: int = 60
        ) -> None:

        """Verifica o cooldown pra poder reenviar o email"""
        tempo_restante = await redis_client.ttl(chave_redis)
        tentativas = await redis_client.get(chave_redis)

        if tempo_restante > 0:
            raise HTTPException(status_code=429, detail=f"Aguarde {tempo_restante}s para solicitar outro e-mail.")
        tentativas += 1
        # Salva no redis o cooldown, impedindo o Reenvio até a chave ser apagada
        await redis_client.set(chave_redis, 'enviado', ex=cooldown_segundos) 


    # ==============================================
    #   MÉTODOS DE CONFIRMAÇÃO DE CRIAÇÃO DA CONTA
    # ==============================================

    async def enviar_email_confirmacao(
            self, 
            token: str, 
            email: str, 
            usuario_id: int
        ) -> None:
        """Envia o email de confirmação de criação de conta"""

        await self._enviar_email(
            token=token,
            mensagem_email='confirmar-email',
            subject='Confirme seu e-mail',
            destinatario=email,
            body="Clique no link para confirmar seu e-mail",
            usuario_id=usuario_id,
            chave_redis=f'cooldown:email_confirmacao'
        )
        logger.info('E-mail de confirmação enviado', extra={'usuario_id': usuario_id})



    async def reenviar_email(
            self, 
            body: ReenviarEmailConfirmacao
        ) -> dict:
        """Reenvia o email pra confirmar a conta"""
        query = select(Usuario).where(Usuario.email == body.email)
        resultado = await self.db.execute(query)
        usuario = resultado.scalar_one_or_none()

        if usuario is None or usuario.email_verificado == True:
            logger.info('Conta inexistente ou email já verificado')
            return {"message": "Se existir uma conta pendente, enviaremos um novo link de confirmação."}

        # Gera um token itsdangerous pra colocar no link da mensagem enviada
        token = gerar_token_confirmacao_email(body.email)

        await self.enviar_email_confirmacao(
            token=token, 
            email=body.email, 
            usuario_id=usuario.id
        )

        return {"message": "Se existir uma conta pendente, enviaremos um novo link de confirmação."}


    # =============================================
    #     MÉTODOS CONFIRMAÇÃO EXCLUSÃO DE CONTA
    # =============================================

    async def enviar_email_confirmacao_exclusao_conta(
            self, 
            email: str, 
            usuario_id: int, 
            token: str
        ) -> None:
        """Envia email pra confirmar exclusão de conta"""
        
        await self._enviar_email(
            token=token,
            mensagem_email='confirmar-exclusao-conta',
            subject='Exclusão de conta',
            destinatario=email,
            body='Clique no link para excluir sua conta',
            chave_redis=f'cooldown:email_confirmacao_exclusao_de_conta',
            usuario_id=usuario_id
        )
        logger.info('E-mail de confirmação de exclusão de conta enviado', extra={'usuario_id': usuario_id})



    async def reenviar_email_exclusao_conta(
            self, 
            access_token: dict
        ) -> dict:
        """Reenvia o email pra excluir a conta"""

        email = access_token["email"]
        usuario_id = access_token["id"]

        query = select(Usuario).where(Usuario.email == email)
        resultado = await self.db.execute(query)
        usuario = resultado.scalar_one_or_none()

        if usuario is None or usuario.usuario_ativo == False:
            logger.info('Usuário não existe ou já está excluído logicamente', extra={'usuario_id': usuario_id})
            return {"message": "Se existir uma conta pendente, enviaremos um novo link de confirmação."}

        # Gera um token itsdangerous pra colocar no link da mensagem enviada
        token = gerar_token_exclusao_conta(email)

        await self.enviar_email_confirmacao_exclusao_conta(
            token=token, 
            email=email, 
            usuario_id=usuario_id
        )

        return {"message": "Se existir uma conta pendente, enviaremos um novo link de confirmação."}

    # =======================================
    #   Atualiza as Informações do Personal
    # =======================================

    async def enviar_email_pra_mudar_de_senha_logado(
            self,
            body: EnviarEmailRedefinirSenha,
            access_token: dict,
        ) -> None:
        """
        Envia um e-mail pro Personal poder Mudar de Senha
        Envia o e-mail Apenas se o Personal estiver logado
        """

        token = gerar_token_alterar_senha(body.email)

        await self._enviar_email(
            token=token,
            mensagem_email='/senha/alterar-senha',
            subject='Alteração de Senha',
            destinatario=body.email,
            body='Clique no link para alterar a sua senha',
            usuario_id=access_token['id'],
            chave_redis='cooldown:email_alterar_senha_logado'
        )
        logger.info('E-mail de redefinição de senhas (logado) enviado', extra={'usuario_id': access_token['id']})



    async def enviar_email_pra_mudar_de_senha_deslogado(
            self,
            body: EnviarEmailRedefinirSenha,
            usuario_id: int
        ) -> None:
        """
        Envia um e-mail pro Personal poder Mudar de Senha
        Envia o e-mail quando o Personal não Estiver logado no campo do login "esqueci minha senha"
        """

        token = gerar_token_alterar_senha(body.email)

        await self._enviar_email(
            token=token,
            mensagem_email='/senha/redefinir-senha',
            subject='Alteração de Senha',
            destinatario=body.email,
            body='Clique no link para alterar a sua senha',
            usuario_id=usuario_id,
            chave_redis='cooldown:email_alterar_senha_deslogado'
        )

        logger.info('E-mail de redefinição de senhas (deslogado) enviado', extra={'usuario_id': usuario_id})
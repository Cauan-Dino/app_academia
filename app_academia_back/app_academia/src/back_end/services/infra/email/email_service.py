from back_end.services.infra.database.models import Personal
from fastapi import HTTPException, APIRouter
from back_end.auth.auth_token_itsdangerous import (
    gerar_token_confirmacao_email, 
    gerar_token_exclusao_conta,
    gerar_token_alterar_senha
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from back_end.services.infra.redis_service.redis_config import redis_client
import uuid
from urllib.parse import quote
from redis.asyncio import RedisError
from back_end.schemas.personal_schema import ReenviarEmailConfirmacao, EnviarEmailRedefinirSenha, AlterarSenhaPersonal
from back_end.core.logging.logs_settings import logger
from back_end.services.infra.config.settings import settings
from back_end.services.infra.filas.tasks.email_task import fila_enviar_email

router = APIRouter(tags=['Envio de email'])


def montar_link(caminho: str, token: str) -> str:
    """Link de um endpoint GET da API, com o token protegido para ir na URL."""
    base = settings.API_PUBLIC_URL.rstrip('/')
    return f"{base}{caminho}?token={quote(token, safe='')}"


def link_confirmar_email(token: str) -> str:
    return montar_link('/confirmar-email', token)


def link_confirmar_exclusao_conta(token: str) -> str:
    return montar_link('/confirmar-exclusao-conta', token)


def link_redefinir_senha(token: str) -> str:
    # Os endpoints de senha são PATCH e só o app os chama: o link leva a uma
    # página da API que abre o app na tela de nova senha (ver update_personal.py).
    return montar_link('/abrir-app/redefinir-senha', token)

class EmailService:
    def __init__(self, db: AsyncSession):
        self.db = db


    async def _enviar_email(
            self,
            link: str,
            assunto: str,
            destinatario: str,
            texto: str,
            texto_botao: str,
            usuario_id: int,
            chave_redis: str
        ) -> None:
        """
        Método helper que envia o email e salva a chave de cooldown no redis
        Evitando com que o usuário possa pedir um novo email dentro do tempo de expiração salvo no redis
        """
        redis_key = f'{chave_redis}:{usuario_id}'
        await self.verificar_cooldown_de_envio_email(chave_redis=redis_key)
        # Coloca o envio do email em uma fila
        await fila_enviar_email.kiq(
            destinatario=destinatario,
            assunto=assunto,
            texto=texto,
            link=link,
            texto_botao=texto_botao,
            redis_key=redis_key,
            # Uma chave por e-mail: as retentativas da fila não geram cópias.
            chave_idempotencia=uuid.uuid4().hex,
        )
            

    async def verificar_cooldown_de_envio_email(
            self, 
            chave_redis: str, 
            cooldown_segundos: int = 60
        ) -> None:

        """Verifica o cooldown pra poder reenviar o email"""
        try:
            tempo_restante = await redis_client.ttl(chave_redis)

            if tempo_restante > 0:
                raise HTTPException(status_code=429, detail=f"Aguarde {tempo_restante}s para solicitar outro e-mail.")

            # Salva no redis o cooldown, impedindo o Reenvio até a chave ser apagada
            await redis_client.set(chave_redis, 'enviado', ex=cooldown_segundos)

        except RedisError:
            logger.error('Não foi possível verificar o cooldown de envio de e-mail no Redis')
            raise HTTPException(
                status_code=503,
                detail="Serviço temporariamente indisponível. Tente novamente mais tarde."
            )
        
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
            link=link_confirmar_email(token),
            assunto='Confirme seu e-mail',
            destinatario=email,
            texto="Clique no botão abaixo para confirmar seu e-mail e ativar sua conta no TreinoPro.",
            texto_botao="Confirmar e-mail",
            usuario_id=usuario_id,
            chave_redis=f'cooldown:email_confirmacao'
        )
        logger.info('E-mail de confirmação enviado', extra={'usuario_id': usuario_id})



    async def reenviar_email(
            self, 
            body: ReenviarEmailConfirmacao
        ) -> dict:
        """Reenvia o email pra confirmar a conta"""
        query = select(Personal).where(Personal.email == body.email)
        resultado = await self.db.execute(query)
        usuario = resultado.scalar_one_or_none()

        if usuario is None or usuario.email_verificado == True:
            logger.info('Conta inexistente ou email já verificado')
            return {"message": "Se existir uma conta pendente, enviaremos um novo link de confirmação."}

        # Gera um token itsdangerous pra colocar no link da mensagem enviada
        token = gerar_token_confirmacao_email(body.email, usuario.senha)

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
            link=link_confirmar_exclusao_conta(token),
            assunto='Exclusão de conta',
            destinatario=email,
            texto='Recebemos um pedido para excluir sua conta no TreinoPro. Se foi você, clique no botão abaixo.',
            texto_botao='Excluir minha conta',
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

        query = select(Personal).where(Personal.email == email)
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
            link=link_redefinir_senha(token),
            assunto='Alteração de Senha',
            destinatario=body.email,
            texto='Abra este e-mail no celular com o TreinoPro instalado e toque no botão para criar sua nova senha.',
            texto_botao='Alterar senha',
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
            link=link_redefinir_senha(token),
            assunto='Alteração de Senha',
            destinatario=body.email,
            texto='Abra este e-mail no celular com o TreinoPro instalado e toque no botão para criar sua nova senha.',
            texto_botao='Alterar senha',
            usuario_id=usuario_id,
            chave_redis='cooldown:email_alterar_senha_deslogado'
        )

        logger.info('E-mail de redefinição de senhas (deslogado) enviado', extra={'usuario_id': usuario_id})
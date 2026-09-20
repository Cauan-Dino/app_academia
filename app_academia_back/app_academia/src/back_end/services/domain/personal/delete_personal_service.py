from sqlalchemy.ext.asyncio import AsyncSession
from back_end.schemas.personal_schema import DeletarContaPersonal
from back_end.services.infra.database.models import Personal
from back_end.services.domain.personal.cadastro_personal_service import PersonalCadastroService
from back_end.services.infra.criptografia.criptografia_de_senhas import verificar_senha
from fastapi import HTTPException
from back_end.auth.auth_token_itsdangerous import gerar_token_exclusao_conta, validar_token_exclusao_conta
from back_end.services.infra.email.email_service import EmailService
from back_end.services.infra.redis_service.redis_config import redis_client
from back_end.services.infra.rate_limit.rate_limit_redis import RateLimitService
from sqlalchemy import select
from back_end.core.logging.logs_settings import logger

class DeletePersonalAcountService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.persona_cadastro_service = PersonalCadastroService(self.db)
        self.email_service = EmailService(self.db)
        self.rate_limit_service = RateLimitService()


    async def solicitar_conta_personal(
        self, 
        body: DeletarContaPersonal, 
        access_token: dict, 
        ) -> dict:
        """Envia o email pro personal poder excluir a conta dele"""

        self.persona_cadastro_service.validar_senha(body.senha, body.confirmar_senha)

        query = select(Personal).where(Personal.email == access_token['email'])
        resultado = await self.db.execute(query)
        usuario = resultado.scalar_one_or_none()
        
        # --- Rate limit ---
        chave_tentativas = f'delete_attempts:{usuario.id}'
        # Verifica se o usuario erro mais de 5 vezes a senha
        await self.rate_limit_service.verificar_rate_limit(chave=chave_tentativas, limite=5)

        if not verificar_senha(body.senha, usuario.senha):
            # incrementa e define expiração só na primeira tentativa
            await self.rate_limit_service.incrementar_rate_limit(chave=chave_tentativas, janela_segundos=900)
            raise HTTPException(status_code=401, detail='Senha incorreta!')

        # Senha certa -> Reseta o contador de senhas erradas
        await redis_client.delete(chave_tentativas)

        # --- Envia Email de Confirmação pra EXCLUIR Conta ------------------
        token = gerar_token_exclusao_conta(usuario.email)
        try:
            # Criar metodo de eviar_email_confirmar_excluir_conta
            await self.email_service.enviar_email_confirmacao_exclusao_conta(token=token, email=usuario.email, usuario_id=usuario.id) 
        # Pega a exceção de cooldown de segundos
        except HTTPException:
            raise 
        except Exception:
            raise HTTPException(status_code=503, detail="Não foi possível enviar o e-mail de confirmação. Tente novamente mais tarde.")

        return {'message':'Enviamos um Link de Confirmação para Excluir a sua Conta.'}



    async def confirmar_exclusao_de_conta(
            self, 
            token: str
        ) -> dict:
        """Confirma a exclusão da conta no link do email enviado"""
        email = validar_token_exclusao_conta(token=token)

        # Verifica se o email existe  
        query = select(Personal).where(Personal.email == email)
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
        usuario.email = None
        usuario.telefone = f'del:{usuario.id}'
        usuario.token_version += 1 # Invalida o access e refresh token atuais

        try:
            await self.db.commit()
        except:
            await self.db.rollback()
            raise HTTPException(status_code=500, detail='Ocorreu um erro desconhecido.')

        # Deleta a chave do access_token que é salva em "verificar_access_token"
        await redis_client.delete(f"usuario_status:{email}")

        logger.info('Conta Excluída', extra={'usuario_id': usuario.id})
        return {'message':"Conta Excluída com sucesso!"}

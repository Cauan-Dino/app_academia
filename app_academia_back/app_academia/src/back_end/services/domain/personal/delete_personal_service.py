from sqlalchemy.ext.asyncio import AsyncSession
from back_end.schemas.personal_schema import DeletarContaPersonal
from back_end.services.infra.database.models import Usuario
from back_end.services.domain.personal.cadastro_personal_service import PersonalCadastroService
from back_end.services.infra.criptografia.criptografia_de_senhas import verificar_senha
from fastapi import HTTPException
from back_end.auth.auth_token_itsdangerous import gerar_token_exclusao_conta, validar_token_confirmacao_email
from back_end.services.infra.email.email_service import EmailService
from back_end.services.infra.redis_service.redis_config import redis_client
from back_end.services.infra.rate_limit.rate_limit_redis import RateLimitService

class DeletePersonalAcountService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.persona_cadastro_service = PersonalCadastroService(db)
        self.email_service = EmailService(db)
        self.rate_limit_service = RateLimitService()


    async def deletar_conta_personal(self, body: DeletarContaPersonal, access_token: Usuario) -> dict:
        """Envia o email pro personal poder excluir a conta dele"""
        self.persona_cadastro_service.validar_senha(body.senha, body.confirmar_senha)

        # --- Rate limit ---
        chave_tentativas = f'delete_attempts:{access_token.id}'
        # Verifica se o usuario erro mais de 5 vezes a senha
        await self.rate_limit_service.verificar_rate_limit(chave=chave_tentativas, limite=5)

        if not verificar_senha(body.senha, access_token.senha):
            # incrementa e define expiração só na primeira tentativa
            await self.rate_limit_service.incrementar_rate_limit(chave=chave_tentativas, janela_segundos=900)
            raise HTTPException(status_code=401, detail='Senha incorreta!')

        # Senha certa -> Reseta o contador de senhas erradas
        await redis_client.delete(chave_tentativas)

        # --- Envia Email de Confirmação pra EXCLUIR Conta ------------------
        token = gerar_token_exclusao_conta(access_token.email)
        try:
            # Criar metodo de eviar_email_confirmar_excluir_conta
            await self.email_service.enviar_email_confirmacao_exclusao_conta(token=token, email=access_token.email, usuario_id=access_token.id) 
        # Pega a exceção de cooldown de segundos
        except HTTPException:
            raise 
        except Exception:
            raise HTTPException(status_code=503, detail="Não foi possível enviar o e-mail de confirmação. Tente novamente mais tarde.")

        return {'message':'Enviamos um Link de Confirmação para Excluir a sua Conta.'}

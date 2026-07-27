from sqlalchemy.ext.asyncio import AsyncSession
from back_end.schemas.personal_schema import DeletarContaPersonal
from back_end.services.infra.database.models import Usuario
from back_end.services.domain.personal.cadastro_personal_service import PersonalCadastroService
from sqlalchemy import select
from back_end.services.infra.criptografia.criptografia_de_senhas import verificar_senha
from fastapi import HTTPException
from back_end.auth.auth_token_itsdangerous import gerar_token_confirmacao_email
from back_end.services.infra.email.email_service import EmailService


class DeletePersonalAcountService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.persona_cadastro_service = PersonalCadastroService(db)
        self.email_service = EmailService(db)

    async def deletar_conta_personal(self, body: DeletarContaPersonal, access_token: Usuario):
        self.persona_cadastro_service.validar_senha(body.senha, body.confirmar_senha)

        query = select(Usuario).filter(Usuario.id == access_token.id)
        resultado = await self.db.execute(query)
        usuario = resultado.scalar_one_or_none()

        if not verificar_senha(body.senha, usuario.senha):
            raise HTTPException(status_code=401,detail='Senha incorreta!')

        email_token = gerar_token_confirmacao_email(usuario.email)
        
        self.email_service.enviar_email_confirmacao(token=email_token, email=usuario.email)

        # SALVAR NO REDIS A QUANTIDADE DE TENTATIVAS DE ERROS NA SENHA
        # SALVAR NO REDIS A QUANTIDADE DE TENTATIVAS DE ERROS NA SENHA
        # SALVAR NO REDIS A QUANTIDADE DE TENTATIVAS DE ERROS NA SENHA

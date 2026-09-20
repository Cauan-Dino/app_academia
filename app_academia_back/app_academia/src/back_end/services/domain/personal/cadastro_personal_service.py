from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from back_end.services.infra.sms.telefone_utils import limpar_numero_telefone
from back_end.services.infra.database.models import Personal
from back_end.schemas.personal_schema import CadastroPersonal
from sqlalchemy import select
from back_end.core.logging.logs_settings import logger
from sqlalchemy.exc import IntegrityError
from back_end.services.infra.criptografia.criptografia_de_senhas import criptografar_senha
from back_end.services.infra.email.email_service import EmailService
from back_end.auth.auth_token_itsdangerous import gerar_token_confirmacao_email, validar_token_confirmacao_email



class PersonalCadastroService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.email_service = EmailService(self.db)


    def validar_senha(self, senha: str, confirmar_senha: str):
        """Valida se as senhas enviadas são iguais e possuem mais de 6 digitos e menos de 30"""
        if confirmar_senha != senha:
            raise HTTPException(
                status_code=400,
                detail='As senhas precisam ser iguais!'
            )
        
        if len(senha) < 6:
            raise HTTPException(
                status_code=400,
                detail='A senha precisa possuir mais de 6 caracteres!'
            )

        if len(senha) > 30:
            raise HTTPException(
                status_code=400,
                detail='A senha precisa ter menos de 30 caracteres!'
            )



    async def cadastro_personal(self, body: CadastroPersonal) -> dict:
        body.telefone = limpar_numero_telefone(numero=body.telefone)

        query_usuario_telefone = select(Personal).where(Personal.telefone == body.telefone) # Verifica se o TELEFONE já está cadastrado
        query_usuario_email = select(Personal).where(Personal.email == body.email) # Verifica se o EMAIL já está cadastrado

        resultado_telefone = await self.db.execute(query_usuario_telefone)
        resultado_email = await self.db.execute(query_usuario_email)

        telefone_do_usuario = resultado_telefone.scalar_one_or_none()
        email_do_usuario = resultado_email.scalar_one_or_none()

        # Impede o cadastro se o telefone ou e-mail já pertencem a qualquer conta,
        # ativa ou inativa — contas excluídas não são reaproveitadas silenciosamente.
        if telefone_do_usuario is not None or email_do_usuario is not None:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Não foi possível cadastrar com esses dados. "
                    "Se você já possui uma conta, utilize a recuperação de acesso."
                ),
            )

        self.validar_senha(body.senha, body.confirmar_senha)
        senha_criptografada = criptografar_senha(body.senha)

        usuario = Personal(
            nome=body.nome,
            telefone=body.telefone,
            email=body.email,
            senha=senha_criptografada,
            usuario_ativo=False, # Usuário precisa confirmar a conta no Email
            email_verificado=False
        )
        self.db.add(usuario)

        try:
            await self.db.commit()
        except IntegrityError:
            await self.db.rollback()
            raise HTTPException(status_code=400, detail='Ocorreu um erro ao se cadastrar!')
        
        await self.db.refresh(usuario)
        # --- Envia Email de Confirmação ------------------
        token = gerar_token_confirmacao_email(body.email)
        try:
            await self.email_service.enviar_email_confirmacao(token=token, email=body.email, usuario_id=usuario.id) 
        # Trata o erro de Cooldown de envio
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=503, detail="Não foi possível enviar o e-mail de confirmação. Tente novamente mais tarde.")

        logger.info(
            "Cadastro de personal concluído; e-mail de confirmação enviado",
            extra={"usuario_id": usuario.id},
        )
        return {"message": "Enviamos um link de confirmação para o seu e-mail."}



    async def confirmar_email(
            self, 
            token: str
        ) -> dict:
        """Confirma o email clicando no link enviado no email"""
        email = validar_token_confirmacao_email(token=token)

        # Verifica se o email existe    
        query = select(Personal).where(Personal.email == email)
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
        try:
            await self.db.commit()
        except Exception:
            self.db.rollback()
            raise HTTPException(
                status_code=500,
                detail="Ocorreu um erro ao validar o e-mail. Tente novamente mais tarde."
            )

        logger.info('E-mail confirmado', extra={'usuario_id': usuario.id})
        return {'message':"E-mail confirmado com sucesso!"}

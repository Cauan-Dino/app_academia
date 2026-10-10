from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from back_end.services.infra.database.models import Personal
from back_end.schemas.personal_schema import CadastroPersonal
from sqlalchemy import select
from back_end.core.logging.logs_settings import logger
from sqlalchemy.exc import IntegrityError
from back_end.services.infra.criptografia.criptografia_de_senhas import criptografar_senha
from back_end.services.infra.email.email_service import EmailService
from back_end.services.infra.config.settings import settings
from back_end.auth.auth_token_itsdangerous import (
    LINK_INVALIDO,
    gerar_token_confirmacao_email,
    token_e_da_senha_atual,
    validar_token_confirmacao_email,
)



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
        # O schema já deixou o e-mail em minúsculas e sem espaços.
        permitidos = settings.emails_permitidos
        if permitidos and body.email not in permitidos:
            logger.info("Cadastro recusado: e-mail fora da lista de permitidos")
            raise HTTPException(
                status_code=403,
                detail="O cadastro está disponível só para convidados.",
            )

        query_usuario_email = select(Personal).where(Personal.email == body.email) # Verifica se o EMAIL já está cadastrado
        email_do_usuario = (await self.db.execute(query_usuario_email)).scalar_one_or_none()

        # Conta confirmada não é sobrescrita. Contas excluídas não entram aqui:
        # a exclusão apaga o e-mail da linha.
        if email_do_usuario is not None and email_do_usuario.email_verificado is True:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Não foi possível cadastrar com esses dados. "
                    "Se você já possui uma conta, utilize a recuperação de acesso."
                ),
            )

        self.validar_senha(body.senha, body.confirmar_senha)
        senha_criptografada = criptografar_senha(body.senha)

        if email_do_usuario is None:
            usuario = Personal(
                nome=body.nome,
                email=body.email,
                senha=senha_criptografada,
                usuario_ativo=False, # Usuário precisa confirmar a conta no Email
                email_verificado=False
            )
            self.db.add(usuario)
        else:
            # Cadastro pendente (e-mail não confirmado): refazer o cadastro troca
            # os dados e envia um novo link. Os links antigos deixam de valer,
            # porque o token de confirmação carrega a senha do cadastro.
            usuario = email_do_usuario
            usuario.nome = body.nome
            usuario.senha = senha_criptografada

        try:
            await self.db.commit()
        except IntegrityError:
            await self.db.rollback()
            raise HTTPException(status_code=400, detail='Ocorreu um erro ao se cadastrar!')
        
        await self.db.refresh(usuario)
        # --- Envia Email de Confirmação ------------------
        token = gerar_token_confirmacao_email(body.email, usuario.senha)
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
        email, impressao_senha = validar_token_confirmacao_email(token=token)

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
            return {"message": "E-mail já confirmado anteriormente.", "status": "ja_confirmado"}

        # Link de um cadastro anterior, refeito depois com outra senha
        if not token_e_da_senha_atual(impressao_senha, usuario.senha):
            raise HTTPException(status_code=400, detail=LINK_INVALIDO)

        usuario.email_verificado = True # Confirma o email
        usuario.usuario_ativo = True # Ativa a conta do usuario
        try:
            await self.db.commit()
        except Exception:
            await self.db.rollback()
            raise HTTPException(
                status_code=500,
                detail="Ocorreu um erro ao validar o e-mail. Tente novamente mais tarde."
            )

        logger.info('E-mail confirmado', extra={'usuario_id': usuario.id})
        return {'message':"E-mail confirmado com sucesso!", "status": "confirmado"}

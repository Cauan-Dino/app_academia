from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from back_end.services.infra.sms.telefone_utils import limpar_numero_telefone
from back_end.services.infra.database.models import Usuario
from back_end.schemas.personal_schema import CadastroPersonal
from sqlalchemy import select
from back_end.core.logging.logs_settings import logger
from sqlalchemy.exc import IntegrityError
from back_end.services.infra.criptografia.criptografia_de_senhas import criptografar_senha
from back_end.services.infra.email.email_service import EmailService
from back_end.auth.auth_token_itsdangerous import gerar_token_confirmacao_email

class PersonalCadastroService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.email_service = EmailService(db)


    def validar_senha(self, senha: str, confirmar_senha: str):
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

        query_usuario_telefone = select(Usuario).where(Usuario.telefone == body.telefone) # Verifica se o TELEFONE já está cadastrado
        query_usuario_email = select(Usuario).where(Usuario.email == body.email) # Verifica se o EMAIL já está cadastrado

        resultado_telefone = await self.db.execute(query_usuario_telefone)
        resultado_email = await self.db.execute(query_usuario_email)

        telefone_do_usuario = resultado_telefone.scalar_one_or_none()
        email_do_usuario = resultado_email.scalar_one_or_none()

        # Verifica se o telefone ou o email já existem
        if (telefone_do_usuario and telefone_do_usuario.usuario_ativo) or \
        (email_do_usuario and email_do_usuario.usuario_ativo):
            raise HTTPException(
                status_code=400,
                detail='Ocorreu um erro ao se cadastrar!'
            )

        usuario = telefone_do_usuario or email_do_usuario

        # Verifica se o usuario EXISTE e esta ATIVO
        if usuario and usuario.usuario_ativo:
            raise HTTPException(
                status_code=401,
                detail='Ocorreu um erro ao se cadastrar!'
            )

        self.validar_senha(body.senha, body.confirmar_senha)
        senha_criptografada = criptografar_senha(body.senha)

        # Se o usuario EXISTIR e não estiver ATIVO as informações dele são Reinscritas 
        if usuario and not usuario.usuario_ativo:
            # Converte o body para dict (com a senha já tratada)
            dados_atualizacao = body.model_dump(exclude={"confirmar_senha"})
            dados_atualizacao["senha"] = senha_criptografada

            # Atualiza todos os atributos dinamicamente no modelo do banco
            for campo, valor in dados_atualizacao.items():
                setattr(usuario, campo, valor)

            usuario.usuario_ativo = False 
            usuario.email_verificado = False # Usuário precisa confirmar a conta no Email
 
        # Se o personal não possuir nenhum cadastro, Ele será CADASTRADO
        else:
            usuario = Usuario(
                nome=body.nome,
                tipo='personal',
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
        return {"detail": "Enviamos um link de confirmação para o seu e-mail."}




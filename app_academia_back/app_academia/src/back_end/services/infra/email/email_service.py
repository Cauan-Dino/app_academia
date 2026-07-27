from back_end.services.infra.database.models import Usuario
from datetime import datetime, timezone
from fastapi import HTTPException, APIRouter
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from auth.auth_token_itsdangerous import validar_token_confirmacao_email,gerar_token_confirmacao_email
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import os

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
    async def verificar_cooldown_de_envio_email(self, model, usuario_id: int, cooldown_segundos: int = 60):
        # Pega o último email enviado
        query = (
            select(model)
            .filter(model.usuario_id == usuario_id)
            .order_by(model.data_criacao.desc())
        )
        resultado = await self.db.execute(query)
        ultimo_registro = resultado.scalar_one_or_none()

        if ultimo_registro is None:
            return # Nunca pediu antes, libera
        
        agora = datetime.now(timezone.utc).replace(tzinfo=None)
        segundos_desde_ultimo = (agora - ultimo_registro.data_criacao).total_seconds()
            
        if segundos_desde_ultimo < cooldown_segundos:
            tempo_restante = int(cooldown_segundos - segundos_desde_ultimo)
            raise HTTPException(
                status_code=429,
                detail=f"Aguarde {tempo_restante}s para solicitar um novo e-mail de confirmação."
            )


    # Envia de fato o email
    async def enviar_email_confirmacao(token: str, email: str):
        link_confirmacao = f"https://seuapp.com/confirmar-email?token={token}"

        mensagem = MessageSchema(
            subject='Confirme seu e-mail',
            recipients=[email],
            body=f"Clique no link para confirmar seu e-mail: {link_confirmacao}",
            subtype=MessageType.html
        )

        fm = FastMail(conf)

        await fm.send_message(mensagem) # Dispara o email



    async def confirmar_email(self, token: str):
        email = validar_token_confirmacao_email(token=token, tempo_expiracao_segundos=3600)

        # Verifica se o email existe    
        query = select(Usuario).filter(Usuario.email == email, Usuario.usuario_ativo == True)
        resultado = await self.db.execute(query)
        usuario = resultado.scalar_one_or_none()

        if usuario is None:
            raise HTTPException(
                status_code=400,
                detail='Usuário não encontrado.'
            )

        # Verifica se o email já tá verificado
        if usuario.email_verificado is True:
            return {"detail": "E-mail já confirmado anteriormente."}

        usuario.email_verificado = True # Confirma o email

        await self.db.commit()
        await self.db.refresh(usuario)

        return {'message':"E-mail confirmado com sucesso!"}



    async def reenviar_email(self):
        pass
    
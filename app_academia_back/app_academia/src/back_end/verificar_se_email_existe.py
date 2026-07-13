from models import ConfirmacaoEmail,Usuario
from database import Session, sessao_db
from datetime import datetime, timezone
from fastapi import HTTPException, Depends, APIRouter
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from auth_token.auth_token_itsdangerous import validar_token_confirmacao_email,gerar_token_confirmacao_email
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



# Verifica se o usuário pode enviar outro email
async def verificar_cooldown(db: Session, model, usuario_id: int, cooldown_segundos: int = 60):
    # Pega o último email enviado
    ultimo_registro = (
        db.query(model)
        .filter(model.usuario_id == usuario_id)
        .order_by(model.data_criacao.desc())
        .first()
    )

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



# Endpoint que o usuário confirma o email
@router.get('/confirmar-email')
async def confirmar_email(token: str, db: Session = Depends(sessao_db)):
    email = validar_token_confirmacao_email(token=token, tempo_expiracao_segundos=3600)

    # Verifica se o email existe    
    usuario = db.query(Usuario).filter(Usuario.email == email, Usuario.usuario_ativo == True).first()
    if usuario is None:
        raise HTTPException(
            status_code=400,
            detail='Usuário não encontrado.'
        )

    # Verifica se o email já tá verificado
    if usuario.email_verificado is True:
        return {"detail": "E-mail já confirmado anteriormente."}

    usuario.email_verificado = True # Confirma o email
    db.commit()
    db.refresh(usuario)

    return {'message':"E-mail confirmado com sucesso!"}



# Reenvia o email de confirmação de conta
@router.post('/reenviar-email')
async def reenvia_email_de_confirmacao():
    pass

# EXPLICAR PQ EU FIZ CADA COISA, por ex pq eu decidir itsdangerous e nao o jwt token
# EXPLICAR PQ EU FIZ CADA COISA, por ex pq eu decidir itsdangerous e nao o jwt token
# EXPLICAR PQ EU FIZ CADA COISA, por ex pq eu decidir itsdangerous e nao o jwt token
# EXPLICAR PQ EU FIZ CADA COISA, por ex pq eu decidir itsdangerous e nao o jwt token
# EXPLICAR PQ EU FIZ CADA COISA, por ex pq eu decidir itsdangerous e nao o jwt token
# EXPLICAR PQ EU FIZ CADA COISA, por ex pq eu decidir itsdangerous e nao o jwt token
# EXPLICAR PQ EU FIZ CADA COISA, por ex pq eu decidir itsdangerous e nao o jwt token
# EXPLICAR PQ EU FIZ CADA COISA, por ex pq eu decidir itsdangerous e nao o jwt token
# EXPLICAR PQ EU FIZ CADA COISA, por ex pq eu decidir itsdangerous e nao o jwt token
# EXPLICAR PQ EU FIZ CADA COISA, por ex pq eu decidir itsdangerous e nao o jwt token
# EXPLICAR PQ EU FIZ CADA COISA, por ex pq eu decidir itsdangerous e nao o jwt token
# EXPLICAR PQ EU FIZ CADA COISA, por ex pq eu decidir itsdangerous e nao o jwt token
# EXPLICAR PQ EU FIZ CADA COISA, por ex pq eu decidir itsdangerous e nao o jwt token

# Opcção de corrigir o email


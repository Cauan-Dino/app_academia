from itsdangerous import URLSafeTimedSerializer
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
import asyncio

conf = ConnectionConfig(
    MAIL_USERNAME='cauanppenha2@gmail.com',
    MAIL_PASSWORD='tityxtsjajirmojo',
    MAIL_FROM='cauanppenha2@gmail.com',
    MAIL_PORT=465,
    MAIL_SERVER='smtp.gmail.com', 
    MAIL_STARTTLS=False,
    MAIL_SSL_TLS=True,
)

EMAIL_TOKEN_SECRET_KEY = '4a5b6e7f8a9b0c1d2e3f4a5b6e7f8a9b0c1d2e3f4a5b6e7f8a9b0c1d2e3f4a5b'
serializer = URLSafeTimedSerializer(EMAIL_TOKEN_SECRET_KEY)

token = serializer.dumps('cauanppenha@gmail.com', salt='confirmacao-email') # Cria o token com base no email

link_confirmacao = f"https://seuapp.com/confirmar-email?token={token}"

mensagem = MessageSchema(
    subject='Confirme seu e-mail',
    recipients=['cauanppenha@gmail.com'], # Email pra quem vai enviar
    body=f"Clique no link para confirmar seu e-mail: {link_confirmacao}",
    subtype=MessageType.html
)

fm = FastMail(conf)

async def enviar_email():
    await fm.send_message(mensagem) # Dispara o email

if __name__ == '__main__':
    asyncio.run(enviar_email())




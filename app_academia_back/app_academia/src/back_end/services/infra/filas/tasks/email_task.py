from ..taskiq.taskiq_app import broker
from back_end.services.infra.email.envio_email_conf import conf
from fastapi_mail import FastMail, MessageSchema, MessageType
from back_end.services.infra.redis_service.redis_config import redis_client
from back_end.core.logging.logs_settings import logger
import asyncio

@broker.task(retry_on_error=True, max_retries=5)
async def fila_enviar_email(
        token: str, 
        mensagem_email: str, 
        subject: str, 
        destinatario: str, 
        body: str, 
        redis_key: str
    ) -> None:
    try:
        link_confirmacao = f"https://seuapp.com/{mensagem_email}?token={token}"
        mensagem = MessageSchema(
            subject=subject,
            recipients=[destinatario],
            body=f'{body}: {link_confirmacao}',
            subtype=MessageType.html
        )
        fm = FastMail(conf)
        await asyncio.wait_for(fm.send_message(mensagem), timeout=10) # Dispara o email

    except Exception:
        await redis_client.delete(redis_key) # Deleta a chave salva no redis no inicio
        logger.error('Falha ao enviar e-mail', extra={'redis_key': redis_key})
        raise # <- necessário pro middleware de retry saber que precisa tentar de novo
from html import escape

from ..taskiq.taskiq_app import broker
from back_end.services.infra.config.settings import settings
from back_end.services.infra.http.cliente_http import cliente_http
from back_end.services.infra.redis_service.redis_config import redis_client
from back_end.core.logging.logs_settings import logger

URL_RESEND = "https://api.resend.com/emails"


def montar_html(texto: str, link: str, texto_botao: str) -> str:
    """Corpo HTML do e-mail: o texto, um botão com o link e o link escrito por extenso."""
    texto, link, texto_botao = escape(texto), escape(link), escape(texto_botao)
    return (
        '<div style="font-family: Arial, sans-serif; color: #121815; max-width: 480px;">'
        f'<p style="font-size: 16px; line-height: 24px;">{texto}</p>'
        f'<p><a href="{link}" style="display: inline-block; background: #B9F227; color: #121815; '
        'padding: 12px 20px; border-radius: 10px; font-weight: bold; text-decoration: none;">'
        f'{texto_botao}</a></p>'
        '<p style="font-size: 13px; color: #68726D;">Se o botão não funcionar, copie este endereço:<br>'
        f'<a href="{link}" style="color: #68726D;">{link}</a></p>'
        '</div>'
    )


@broker.task(retry_on_error=True, max_retries=5)
async def fila_enviar_email(
        destinatario: str,
        assunto: str,
        texto: str,
        link: str,
        texto_botao: str,
        redis_key: str,
        chave_idempotencia: str,
    ) -> None:
    chave_api = settings.RESEND_API_KEY
    if chave_api is None:
        # Sem a chave, tentar de novo não adianta: libera o cooldown e só registra.
        await redis_client.delete(redis_key)
        logger.error('RESEND_API_KEY não configurada: e-mail não enviado', extra={'redis_key': redis_key})
        return

    try:
        resposta = await cliente_http.post(
            URL_RESEND,
            headers={
                "Authorization": f"Bearer {chave_api.get_secret_value()}",
                # As retentativas desta tarefa repetem a chave, então o Resend
                # não envia o mesmo e-mail duas vezes (a chave vale por 24 h).
                "Idempotency-Key": chave_idempotencia,
            },
            json={
                "from": settings.RESEND_FROM,
                "to": [destinatario],
                "subject": assunto,
                "html": montar_html(texto, link, texto_botao),
                "text": f"{texto}\n\n{link}",
            },
        )

        if resposta.is_error:
            try:
                motivo = resposta.json().get("message")
            except ValueError:
                motivo = None
            # O motivo do Resend explica a recusa, ex.: domínio não verificado.
            logger.error(
                'Resend recusou o e-mail',
                extra={'redis_key': redis_key, 'status_code': resposta.status_code, 'motivo': motivo},
            )
        resposta.raise_for_status()

    except Exception:
        await redis_client.delete(redis_key) # Deleta a chave salva no redis no inicio
        logger.error('Falha ao enviar e-mail', extra={'redis_key': redis_key})
        raise # <- necessário pro middleware de retry saber que precisa tentar de novo

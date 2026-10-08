from html import escape

from ..taskiq.taskiq_app import broker
from back_end.services.infra.config.settings import settings
from back_end.services.infra.http.cliente_http import cliente_http
from back_end.services.infra.redis_service.redis_config import redis_client
from back_end.core.logging.logs_settings import logger

URL_BREVO = "https://api.brevo.com/v3/smtp/email"
# Marca o e-mail como enviado: o Brevo não aceita Idempotency-Key, então é o
# Redis que impede uma retentativa de mandar a mesma mensagem de novo.
PREFIXO_ENVIADO = "email_enviado"
VALIDADE_MARCA_ENVIADO = 24 * 60 * 60  # segundos


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
    chave_api = settings.BREVO_API_KEY
    if chave_api is None or not settings.BREVO_FROM_EMAIL:
        # Sem a configuração, tentar de novo não adianta: libera o cooldown e só registra.
        await redis_client.delete(redis_key)
        logger.error(
            'BREVO_API_KEY ou BREVO_FROM_EMAIL não configurado: e-mail não enviado',
            extra={'redis_key': redis_key},
        )
        return

    marca_enviado = f'{PREFIXO_ENVIADO}:{chave_idempotencia}'
    try:
        if await redis_client.exists(marca_enviado):
            # Uma tentativa anterior já entregou ao Brevo; não manda a cópia.
            return

        resposta = await cliente_http.post(
            URL_BREVO,
            headers={"api-key": chave_api.get_secret_value()},
            json={
                "sender": {"name": settings.BREVO_FROM_NAME, "email": settings.BREVO_FROM_EMAIL},
                "to": [{"email": destinatario}],
                "subject": assunto,
                "htmlContent": montar_html(texto, link, texto_botao),
                "textContent": f"{texto}\n\n{link}",
            },
        )

        if resposta.is_error:
            try:
                motivo = resposta.json().get("message")
            except ValueError:
                motivo = None
            # O motivo do Brevo explica a recusa, ex.: remetente não verificado.
            logger.error(
                'Brevo recusou o e-mail',
                extra={'redis_key': redis_key, 'status_code': resposta.status_code, 'motivo': motivo},
            )
        resposta.raise_for_status()

        await redis_client.set(marca_enviado, 'enviado', ex=VALIDADE_MARCA_ENVIADO)

    except Exception:
        await redis_client.delete(redis_key) # Deleta a chave salva no redis no inicio
        logger.error('Falha ao enviar e-mail', extra={'redis_key': redis_key})
        raise # <- necessário pro middleware de retry saber que precisa tentar de novo

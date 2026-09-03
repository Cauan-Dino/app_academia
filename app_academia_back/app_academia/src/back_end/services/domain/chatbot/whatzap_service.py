import httpx2

from back_end.services.domain.chatbot.setting import settings
from back_end.core.logging.logs_settings import logger

class WhatzapService:
    async def enviar_mensagem_texto(
        self,
        texto: str,
        telefone: str
        ):
        url = (
            f"https://graph.facebook.com/"
            f"{settings.WHATSAPP_API_VERSION}/"
            f"{settings.PHONE_NUMBER_ID}/messages"
        )

        headers = {
            "Authorization": (
                "Bearer "
                + settings.WHATSAPP_ACCESS_TOKEN.get_secret_value()
            ),
            "Content-Type": "application/json",
        }

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": telefone,
            "type": "text",
            "text": {
                "preview_url": False,
                "body": texto,
            },
        }

        async with httpx2.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                url=url,
                headers=headers,
                json=payload,
            )

            if response.is_error:
                try:
                    erro_meta = response.json().get("error", {})

                    logger.error(
                        "Meta recusou o envio da mensagem",
                        extra={
                            "status_code": response.status_code,
                            "meta_code": erro_meta.get("code"),
                            "meta_subcode": erro_meta.get("error_subcode"),
                            "meta_type": erro_meta.get("type"),
                            "meta_message": erro_meta.get("message"),
                        },
                        exc_info=False,
                    )
                except ValueError:
                    logger.error(
                        "Meta retornou uma resposta não JSON",
                        extra={"status_code": response.status_code},
                        exc_info=False,
                    )

            response.raise_for_status()

            return response.json()
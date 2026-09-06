from fastapi import (
    HTTPException,
)
from fastapi.responses import PlainTextResponse
import secrets
import hmac
import hashlib
from fastapi import Request
from .setting import settings
import httpx2 
from back_end.core.logging.logs_settings import logger
import json

class WhatsappService:
        
    def validar_url(
        self,
        mode: str, 
        verify_token: str, 
        challenge: str, 
        ) -> PlainTextResponse:
        """
        A meta verifica se a url colocada no callback é valida via esse metodo
        """
        WHATSAPP_VERIFY_TOKEN = settings.WHATSAPP_VERIFY_TOKEN.get_secret_value()

        if not WHATSAPP_VERIFY_TOKEN:
            raise RuntimeError(
                "WHATSAPP_VERIFY_TOKEN não configurado."
            )

        if (
            mode == 'subscribe' 
            and secrets.compare_digest(
                WHATSAPP_VERIFY_TOKEN, 
                verify_token
            )
        ):
            return PlainTextResponse(challenge)

        raise HTTPException(
            status_code=403,
            detail='Token inválido.'
        )


    def validar_assinatura(
        self,
        corpo: bytes,
        assinatura_recebida: str | None,
    ) -> None:
        """
        Verifica se a entidade que chamou o endpoint colocado no callback da meta pertence a meta de fato
        """
        app_secret = settings.WHATSAPP_APP_SECRET.get_secret_value()

        if not app_secret:
            raise RuntimeError(
                "WHATSAPP_APP_SECRET não configurado."
            )

        if assinatura_recebida is None:
            raise HTTPException(
                status_code=403,
                detail='Assinatura não enviada.'
            )

        hash_calculado = hmac.new(
            app_secret.encode('utf-8'),
            corpo,
            hashlib.sha256
        ).hexdigest()

        assinatura_esperada = f"sha256={hash_calculado}"
        
        if not secrets.compare_digest(
            assinatura_recebida,
            assinatura_esperada
            ):
            raise HTTPException(
                status_code=403,
                detail="Assinatura inválida.",
            )



        #     if telefone and texto == "oi":
        #         await self.whatsapp_service.enviar_mensagem_texto(
        #             telefone=settings.WHATSAPP_TEST_RECIPIENT,
        #             texto=(
        #                 "Olá! Sou o assistente da academia."
        #             ),
        #         )

        # return Response(status_code=200)

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

    async def processar_mensagem(
        self,
        request: Request,
        assinatura: str | None 
    ) -> dict[str, str]:
        # Precisa pegar os bytes originais antes de ler o JSON
        corpo = await request.body()
        self.validar_assinatura(
            corpo=corpo,
            assinatura_recebida=assinatura,
        )
        
        try:
            payload = json.loads(corpo)
        except json.JSONDecodeError as erro:
            raise HTTPException(
                status_code=400,
                detail="Corpo JSON inválido.",
            ) from erro
        
        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                if change.get("field") != "messages":
                    continue

                value = change.get("value", {})

                for mensagem in value.get("messages", []):
                    if mensagem.get("type") != "text":
                        continue

                    # Pega o telefone e o texto da pessoa que ta mandando mensagem pro bot
                    telefone = mensagem.get("from")
                    texto = (
                        mensagem
                        .get("text", {})
                        .get("body", "")
                        .strip()
                        .casefold()
                    )

                    if telefone:
                        return {
                            "texto": texto,
                            "telefone": telefone,
                        }

        # É um evento de status ou outro evento não processado.
        return None
from fastapi import (
    HTTPException,
)
from fastapi.responses import PlainTextResponse
import os
import secrets
import hmac
import hashlib
from back_end.core.logging.logs_settings import logger
from fastapi import Request, Response
import json
from .setting import settings
from .whatzap_service import WhatzapService

class WebHook:
    def __init__(self, whatsapp_service: WhatzapService):
        self.whatsapp_service = whatsapp_service
        
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


    @staticmethod
    def _validar_assinatura(
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


    async def receber_webhook(
        self,
        request: Request,
        assinatura: str | None 
    ):
        # Precisa pegar os bytes originais antes de ler o JSON
        corpo = await request.body()
        self._validar_assinatura(
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

                    telefone = mensagem.get("from")
                    texto = (
                        mensagem
                        .get("text", {})
                        .get("body", "")
                        .strip()
                        .casefold()
                    )

                    if telefone and texto == "oi":
                        await self.whatsapp_service.enviar_mensagem_texto(
                            telefone=settings.WHATSAPP_TEST_RECIPIENT,
                            texto=(
                                "Olá! Sou o assistente da academia."
                            ),
                        )

        return Response(status_code=200)
            

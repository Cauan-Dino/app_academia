"""Utilitários de normalização e persistência das sessões do chatbot."""

import json
import re

from fastapi import HTTPException
from redis.asyncio import Redis
from redis.exceptions import RedisError

from back_end.core.logging.logs_settings import logger

from .setting import settings
from .whatsapp_service import WhatsappService

from datetime import datetime, timedelta, timezone

from back_end.schemas.chatbot_schemas import SessaoReagendamento

FUSO_HORARIO_ACADEMIA = timezone(timedelta(hours=-3))

class UtilsChatbotService:
    """Centraliza a formatação de datas e as operações de sessão no Redis."""

    def __init__(
        self,
        redis_client: Redis,
        whatsapp_service: WhatsappService,
    ) -> None:
        """Recebe o Redis e o serviço usado para comunicar falhas ao usuário."""
        self.redis_client = redis_client
        self.whatsapp_service = whatsapp_service



    async def _salvar_redis(self, telefone: str) -> None:
        """Cria ou renova a sessão do menu por 30 segundos.

        A chave ``chatbot:sessao:{telefone}`` recebe o valor ``menu`` na
        primeira gravação. Falhas geram uma HTTPException com status 500.
        """
        try:
            chave_redis = f"chatbot:sessao:{telefone}"
            redis_cache = await self.redis_client.get(chave_redis)

            if not redis_cache:
                await self.redis_client.set(chave_redis, "menu", ex=30)
            else:
                await self.redis_client.expire(chave_redis, 30)

            try:
                logger.info("Sessão com o chatbot salva no redis")
            except Exception:
                pass
        except Exception:
            logger.error(
                "Erro ao salvar chave de telefone no redis no chatbot.",
                exc_info=False,
            )
            raise HTTPException(
                status_code=500,
                detail="Serviço indisponível no momento, tente mais tarde",
            )



    def _limpar_data_e_hora(self, data_e_hora: str) -> str:
        """Troca o separador ' às ' ou ' as ' por ':' e remove espaços externos.

        Aceita maiúsculas e espaços extras. A validação da data resultante
        permanece com o chamador, por meio de ``datetime.strptime``.
        """
        return re.sub(
            r"\s+[aà]s\s+",
            ":",
            data_e_hora.strip(),
            flags=re.IGNORECASE,
        )



    async def _renovar_tempo_expiracao_conversa_redis(
        self,
        telefone_aluno: str,
    ) -> None:
        """Renova uma sessão de reagendamento existente por 40 segundos.

        Não cria uma sessão ausente. Em caso de RedisError, registra a falha
        e tenta avisar o destinatário de teste configurado.
        """
        try:
            await self.redis_client.expire(
                f"chatbot:reagendamento:{telefone_aluno}:aula_original",
                40,
            )
        except RedisError:
            logger.warning(
                "Não foi possivel salvar no redis data_hora_aula_original para mudança de aula",
                exc_info=False,
            )
            await self.whatsapp_service.enviar_mensagem_texto(
                "Nosso serviço está temporariamente indisponível. Por favor, tente mais tarde",
                telefone=settings.WHATSAPP_TEST_RECIPIENT,
            )



    async def pega_cache_e_verificar_se_redis_esta_online(
        self,
        telefone_aluno: str,
    ) -> SessaoReagendamento | None:
        """Lê e desserializa a sessão de reagendamento do telefone informado.

        Retorna None se a chave estiver ausente ou houver RedisError. Nesse
        último caso, registra a falha e tenta enviar um aviso pelo WhatsApp.
        JSON inválido e falhas no envio do aviso são propagados ao chamador.
        """
        try:
            cache = await self.redis_client.get(
                f"chatbot:reagendamento:{telefone_aluno}:aula_original",
            )
            return json.loads(cache) if cache else None
        except RedisError:
            logger.warning(
                "Não foi possivel salvar no redis data_hora_aula_original para mudança de aula",
                exc_info=False,
            )
            raise



    async def salvar_situacao_de_agendamento_de_aula_no_redis(
        self,
        telefone_aluno: str,
        sessao: dict,
    ) -> None:
        """Grava o estado completo do reagendamento em JSON por 40 segundos.

        Substitui o estado anterior e renova sua expiração. Os valores da
        sessão devem ser serializáveis em JSON. Em caso de RedisError,
        registra a falha e tenta enviar um aviso pelo WhatsApp.
        """
        try:
            await self.redis_client.set(
                f"chatbot:reagendamento:{telefone_aluno}:aula_original",
                json.dumps(sessao),
                ex=40,
            )
        except RedisError:
            logger.warning(
                "Não foi possivel salvar no redis data_hora_aula_original para mudança de aula",
                exc_info=False,
            )
            await self.whatsapp_service.enviar_mensagem_texto(
                "Nosso serviço está temporariamente indisponível. Por favor, tente mais tarde",
                telefone=settings.WHATSAPP_TEST_RECIPIENT,
            )
            raise

    async def validar_e_converter_data_hora(
        self,
        data_hora_aula_original: str,
        *,
        exigir_data_futura: bool = True,
    ) -> datetime | None:
        """Normaliza e converte a data e o horário informados pelo aluno.

        Interpreta a entrada no horário da academia (UTC−3, Fortaleza).
        Retorna um datetime sem fuso para manter o contrato com a agenda.
        Entradas inválidas ou que não sejam futuras recebem uma orientação
        e retornam None. A renovação da sessão cabe ao chamador.
        """
        try:
            data_hora_formatada = self._limpar_data_e_hora(
                data_e_hora=data_hora_aula_original,
            )

            aula_agendada = datetime.strptime(
                data_hora_formatada,
                "%d/%m/%Y:%H:%M",
            )
        except ValueError:
            await self.whatsapp_service.enviar_mensagem_texto(
                texto=(
                    "Não entendi a data e o horário.\n"
                    "Envie neste formato: 14/09/2026 às 08:00."
                ),
                telefone=settings.WHATSAPP_TEST_RECIPIENT,
            )

            return None

        if exigir_data_futura:
            if aula_agendada.replace(tzinfo=FUSO_HORARIO_ACADEMIA) <= datetime.now(
                FUSO_HORARIO_ACADEMIA
            ):
                await self.whatsapp_service.enviar_mensagem_texto(
                    texto=(
                        "A data e o horário informados já passaram ou a aula já começou.\n"
                        "Para continuar o reagendamento, informe uma data e um horário "
                        "futuros, no formato DD/MM/AAAA às HH:MM."
                    ),
                    telefone=settings.WHATSAPP_TEST_RECIPIENT,
                )
                return None

        return aula_agendada


    async def obter_sessao_ativa_ou_avisar(
        self,
        telefone_aluno: str,
        ) -> dict | None:
        """Obtém a sessão de reagendamento ou informa por que não pode continuar.

        Retorna o dicionário da sessão quando ela existe. Se o Redis estiver
        indisponível ou a sessão estiver ausente, envia o aviso correspondente
        ao aluno e retorna None.
        """
        try:
            cache = await self.pega_cache_e_verificar_se_redis_esta_online(
                telefone_aluno=telefone_aluno,
            )
        except RedisError:
            await self.whatsapp_service.enviar_mensagem_texto(
                texto="Serviço temporariamente indisponível. Tente mais tarde.",
                telefone=settings.WHATSAPP_TEST_RECIPIENT,
            )
            return None

        if cache is None:
            await self.whatsapp_service.enviar_mensagem_texto(
                texto=(
                    "Não encontrei uma sessão de reagendamento ativa. "
                    "Digite 'menu' e escolha a opção 2 para começar novamente."
                ),
                telefone=settings.WHATSAPP_TEST_RECIPIENT,
            )
            return None

        return cache

from sqlalchemy.ext.asyncio import AsyncSession
from back_end.services.infra.database.models import DiaDaSemana
from datetime import datetime
from sqlalchemy import select
from back_end.services.infra.database.models import AulaFixa, Alunos, ParticipanteAula
from back_end.core.logging.logs_settings import logger
from redis.asyncio import RedisError, Redis
from .whatsapp_service import WhatsappService
from .setting import settings
import json
import re

DIAS_DA_SEMANA = (
    DiaDaSemana.SEGUNDA,
    DiaDaSemana.TERCA,
    DiaDaSemana.QUARTA,
    DiaDaSemana.QUINTA,
    DiaDaSemana.SEXTA,
    DiaDaSemana.SABADO,
    DiaDaSemana.DOMINGO,
)

class SolicitacaoReagendamentoAulaService:
    def __init__(
        self,
        db: AsyncSession,
        whatsapp_service: WhatsappService,
        redis_client: Redis,
        ):  
        self.db = db
        self.redis_client = redis_client
        self.whatsapp_service = whatsapp_service


    def _limpar_data_e_hora(
        self,
        data_e_hora: str
    ) -> str:
        return re.sub(
            r"\s+[aà]s\s+",
            ":",
            data_e_hora.strip(),
            flags=re.IGNORECASE,
        )


    async def _renovar_tempo_expiracao_conversa_redis(
        self,
        telefone_aluno: str
    ) -> None:
        try:
            # Renova o tempo de expiração do token na conversa 
            await self.redis_client.expire(
                f"chatbot:reagendamento:{telefone_aluno}:aula_original",
                40
            )        
        except RedisError:
            logger.warning(
                'Não foi possivel salvar no redis data_hora_aula_original para mudança de aula',
                exc_info=False
            )
            await self.whatsapp_service.enviar_mensagem_texto(
                'Nosso serviço está temporariamente indisponível. Por favor, tente mais tarde',
                telefone=settings.WHATSAPP_TEST_RECIPIENT
            )

            return
        

    async def pega_cache_e_verificar_se_redis_esta_online(
        self,
        telefone_aluno: str,
    ) -> dict | None:
        try:
            # Pega o dicionario salvo no redis que mostra indica em qual estagio o aluno esta pra mudar o horario da aula
            cache = await self.redis_client.get(
                        f"chatbot:reagendamento:{telefone_aluno}:aula_original",
                    )
            return json.loads(cache) if cache else None
        
        except RedisError:
            logger.warning(
                'Não foi possivel salvar no redis data_hora_aula_original para mudança de aula',
                exc_info=False
            )
            await self.whatsapp_service.enviar_mensagem_texto(
                'Nosso serviço está temporariamente indisponível. Por favor, tente mais tarde',
                telefone=settings.WHATSAPP_TEST_RECIPIENT
            )

            return


    async def salvar_situacao_de_agendamento_de_aula_no_redis(
        self,
        telefone_aluno: str,
        sessao: dict,
        ) -> None: 
        try:
            # Salva no redis que a sessao de agendamento foi iniciada
            await self.redis_client.set(
                f"chatbot:reagendamento:{telefone_aluno}:aula_original",
                json.dumps(sessao),
                40
            )
        except RedisError:
            logger.warning(
                'Não foi possivel salvar no redis data_hora_aula_original para mudança de aula',
                exc_info=False
            )
            await self.whatsapp_service.enviar_mensagem_texto(
                'Nosso serviço está temporariamente indisponível. Por favor, tente mais tarde',
                telefone=settings.WHATSAPP_TEST_RECIPIENT
            )

            return

        
    async def solicitar_mudanca(
        self,
        texto_aluno: str,
        telefone_aluno: str,
    ) -> None:
        cache = await self.pega_cache_e_verificar_se_redis_esta_online(telefone_aluno=telefone_aluno)
        # Sai da conversa de reagendar aula
        if texto_aluno == '0' and cache:
            await self._sair_da_conversa_de_mudar_aula(
                telefone_aluno=telefone_aluno
            )
            return
        # Verifica em qual parte o aluno esta pra mudar a aula
        if cache.get('data_hora_aula_original') == 'aguardando':
            await self._verificar_dia_da_aula(telefone_aluno=telefone_aluno, data_hora_aula_original=texto_aluno)
        elif cache.get('nova_data_hora_fim') == 'aguardando':
            pass



    async def _verificar_dia_da_aula(
        self,
        data_hora_aula_original: str,
        telefone_aluno: str,
     ) -> None:
        try:
            data_hora_formatada = self._limpar_data_e_hora(data_e_hora=data_hora_aula_original)
            # Trasnforma em dia/mes/ano e hora:minutos
            data_hora = datetime.strptime(
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
            await self._renovar_tempo_expiracao_conversa_redis(
                telefone_aluno=telefone_aluno
            )
            return
        
        # Pega o dia da semana, ex: quarta = 2
        dia_da_semana = DIAS_DA_SEMANA[data_hora.weekday()]
        horario_inicio = data_hora.time()
        query = (
            select(
                AulaFixa,
                Alunos.id.label('aluno_id')
            )
            .join(
                ParticipanteAula,
                ParticipanteAula.aula_fixa_id == AulaFixa.id,
            )
            .join(
                Alunos,
                Alunos.id == ParticipanteAula.aluno_id,
            )
            .where(
                Alunos.telefone == telefone_aluno,
                AulaFixa.dia_da_semana == dia_da_semana,
                AulaFixa.horario_inicio == horario_inicio,
            )
        )
        resultado = await self.db.execute(query)
        aula = resultado.all()

        if not aula:
            await self.whatsapp_service.enviar_mensagem_texto(
                'Não existe nenhuma aula nesse horário.',
                telefone=settings.WHATSAPP_TEST_RECIPIENT
            )
            await self._renovar_tempo_expiracao_conversa_redis(
                telefone_aluno=telefone_aluno
            )
            return

        # Desempacota os dois valores do único registro encontrado.
        aula, aluno_id = aula[0]
        
        sessao = {
            "aluno_id": aluno_id,
            "aula_fixa_id": aula.id,
            "data_hora_aula_original": data_hora.isoformat(),
            "motivo": "aguardando",
            "nova_data_hora_fim": "aguardando",
            "nova_data_hora_inicio": "aguardando",
        }

        await self.salvar_situacao_de_agendamento_de_aula_no_redis(
            telefone_aluno=telefone_aluno,
            sessao=sessao
        )
        
        await self.whatsapp_service.enviar_mensagem_texto(
            texto="Para qual data e horário? Exemplo: 15/09/2026 às 10:00.",
            telefone=settings.WHATSAPP_TEST_RECIPIENT,
        )


    async def _sair_da_conversa_de_mudar_aula(
        self,
        telefone_aluno: str
    ) -> None:        
        try:
            # Salva no redis que a sessao de agendamento foi iniciada
            await self.redis_client.delete(
                f"chatbot:reagendamento:{telefone_aluno}:aula_original",
            )
            await self.whatsapp_service.enviar_mensagem_texto(
                texto=(
                    "Tudo bem! O pedido de reagendamento foi cancelado. "
                    "Sua aula continua na data e no horário originais.\n\n"
                    "Digite 'menu' para voltar às opções."
                ),
                telefone=telefone_aluno,
            )
        except RedisError:
            logger.warning(
                'Não foi possivel deletar no redis o estado de mudança de agendamento de aula',
                exc_info=False
            )
            await self.whatsapp_service.enviar_mensagem_texto(
                'Nosso serviço está temporariamente indisponível. Por favor, tente mais tarde',
                telefone=settings.WHATSAPP_TEST_RECIPIENT
            )

            return

    async def _mudar_horario(
        self
    ):
        pass
        
        
        
        

# aluno seleciona a opcao de mudar de aula
# salva no redis que o aluno iniciou a opcao 2
# verifica em qual estado esta
# escolha qual aula informando dia quer mudar
# escolha o novo horario de inicio e de fim
# escreve o motivo pra querer mudar a aula
# personal confirmar ou rejeita no aplicativo e envia a notificacao pro whatsapp do aluno
"""Etapas da conversa para solicitar e cancelar o reagendamento de uma aula."""

from sqlalchemy.ext.asyncio import AsyncSession
from back_end.services.infra.database.models import DiaDaSemana
from datetime import datetime
from sqlalchemy import select, and_
from back_end.services.infra.database.models import AulaFixa, Alunos, ParticipanteAula, SolicitacaoMudanca, StatusSolicitacao
from back_end.core.logging.logs_settings import logger
from redis.asyncio import RedisError, Redis
from .whatsapp_service import WhatsappService
from .utils_chatbot_service import UtilsChatbotService
from .setting import settings

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
    """Valida a aula original e conduz as respostas do fluxo de reagendamento."""

    def __init__(
        self,
        db: AsyncSession,
        whatsapp_service: WhatsappService,
        redis_client: Redis,
        utils_chatbot_service: UtilsChatbotService,
        ):  
        """Recebe o banco, o envio de mensagens e as dependências de sessão."""
        self.db = db
        self.redis_client = redis_client
        self.whatsapp_service = whatsapp_service
        self.utils_chatbot_service = utils_chatbot_service

        
    async def solicitar_mudanca(
        self,
        texto_aluno: str,
        telefone_aluno: str,
    ) -> None:
        """Interpreta a resposta conforme o estado de reagendamento no Redis.

        O comando '0' cancela o fluxo ativo. A etapa de aula original é
        validada neste serviço; a etapa seguinte ainda não foi implementada.
        """
        # Trata erro caso o redis esteja indisponivel
        cache = await self.utils_chatbot_service.obter_sessao_ativa_ou_avisar(
            telefone_aluno=telefone_aluno,
        )

        if cache is None:
            return

        # Sai da conversa de reagendar aula
        if texto_aluno == "0":
            await self._sair_da_conversa_de_mudar_aula(
                telefone_aluno=telefone_aluno
            )
            return
        # Verifica em qual parte o aluno esta pra mudar a aula
        if cache.get('data_hora_aula_original') == 'aguardando':
            await self._verificar_dia_da_aula(telefone_aluno=telefone_aluno, data_hora_aula_original=texto_aluno)
        elif cache.get('nova_data_hora_inicio') == 'aguardando':
            await self._mudar_horario_inicio(telefone_aluno=telefone_aluno, data_hora_aula_original=texto_aluno)

        # Renova a sessao de agendamento
        await self.utils_chatbot_service._renovar_tempo_expiracao_conversa_redis(
                telefone_aluno=telefone_aluno
            )


    async def _verificar_dia_da_aula(
        self,
        data_hora_aula_original: str,
        telefone_aluno: str,
     ) -> None:
        """Converte a data recebida e busca uma aula vinculada ao aluno.

        Respostas inválidas ou sem aula correspondente recebem orientação
        e renovam a sessão. Quando há resultados, usa o primeiro para salvar
        a ocorrência original e perguntar a nova data e o horário.
        """
        data_hora = await self.utils_chatbot_service.validar_e_converter_data_hora(
            data_hora_aula_original=data_hora_aula_original,
            telefone_aluno=telefone_aluno
        )
        if data_hora is None:
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

        await self.utils_chatbot_service.salvar_situacao_de_agendamento_de_aula_no_redis(
            telefone_aluno=telefone_aluno,
            sessao=sessao
        )
        
        await self.whatsapp_service.enviar_mensagem_texto(
            texto="Para qual data e horário? Exemplo: 15/09/2026 às 10:00.",
            telefone=settings.WHATSAPP_TEST_RECIPIENT,
        )

        try:
            logger.info(
                f'Aula {aula.id} foi marcada pra ser reagendada do aluno {aluno_id}.'
            )
        except Exception:
            pass


    async def _sair_da_conversa_de_mudar_aula(
        self,
        telefone_aluno: str
    ) -> None:        
        """Remove o estado de reagendamento e envia a confirmação de cancelamento.

        Mantém a sessão do menu e não altera a aula no banco. Se a remoção
        falhar com RedisError, tenta enviar uma mensagem de indisponibilidade.
        """
        try:
            # Remove a sessão de reagendamento do aluno.
            await self.redis_client.delete(
                f"chatbot:reagendamento:{telefone_aluno}:aula_original",
            )
            await self.whatsapp_service.enviar_mensagem_texto(
                texto=(
                    "Tudo bem! O pedido de reagendamento foi cancelado. "
                    "Sua aula continua na data e no horário originais.\n\n"
                    "Digite 'menu' para voltar às opções."
                ),
                telefone=settings.WHATSAPP_TEST_RECIPIENT,
            )
            logger.info(
                'Conversa de reagendamento de aula finalizada.'
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


    async def _mudar_horario_inicio(
        self,
        data_hora_aula_original: str,
        telefone_aluno: str,
    ) -> None:
        data_hora = await self.utils_chatbot_service.validar_e_converter_data_hora(
            data_hora_aula_original=data_hora_aula_original,
            telefone_aluno=telefone_aluno
        )
        if data_hora is None:
            return

        # Verifica ja existe uma aula cadastrada nessa data
        query = (
            select(Alunos)
            .join(
                ParticipanteAula,
                ParticipanteAula.aluno_id == Alunos.id
            )
            .join(
                AulaFixa,
                and_(
                    AulaFixa.id == ParticipanteAula.aula_fixa_id,
                    AulaFixa.dia_da_semana == DIAS_DA_SEMANA[data_hora.weekday()],
                    AulaFixa.horario_inicio == data_hora.time()
                )
            )
            .where(
                Alunos.telefone == telefone_aluno
            )
        )

        resultado = (await self.db.scalars(query)).all()
        if resultado:
            await self.whatsapp_service.enviar_mensagem_texto(
                texto='Você já possui uma aula nesse horario.',
                telefone=settings.WHATSAPP_TEST_RECIPIENT
            )
            return 

        # Verifica se existe uma aula remarcada pra essa data
        query_aula_remarcada_pro_msm_horario = (
            select(Alunos)
            .join(
                SolicitacaoMudanca,
                SolicitacaoMudanca.aluno_id == Alunos.id
            )
            .join(
                AulaFixa,
                and_(
                    AulaFixa.id == SolicitacaoMudanca.aula_fixa_id,
                    AulaFixa.personal_id == Alunos.personal_id
                )
            )
            .where(
                Alunos.telefone == telefone_aluno,
                SolicitacaoMudanca.nova_data_hora_inicio == data_hora,
                SolicitacaoMudanca.status.in_(
                    [
                        StatusSolicitacao.ACEITA,
                        StatusSolicitacao.PENDENTE
                    ]
                )
            )
        )
        # Impedi o usuario de reagendar a aula pro msm horario_inicio duas vezes
        resultado = await self.db.scalar(query_aula_remarcada_pro_msm_horario.limit(1))
        if resultado:
            await self.whatsapp_service.enviar_mensagem_texto(
                texto='Você já possui uma aula reagendada nesse horario.',
                telefone=settings.WHATSAPP_TEST_RECIPIENT
            )
            return

        # Pega a sessao que mostra o estado atual do reagendamento de aula
        sessao = await self.utils_chatbot_service.obter_sessao_ativa_ou_avisar(
            telefone_aluno=telefone_aluno,
        )

        # Verifica se a sessao de agendamento no redis ainda esta valida
        if sessao is None:
            logger.info(
                "Não foi possível recuperar a sessão de reagendamento "
                "ao processar o novo horário de início."
            )
            return
        
        sessao["nova_data_hora_inicio"] = data_hora.isoformat()

        await self.utils_chatbot_service.salvar_situacao_de_agendamento_de_aula_no_redis(
            telefone_aluno=telefone_aluno,
            sessao=sessao
        )
        
        await self.whatsapp_service.enviar_mensagem_texto(
            texto="Para qual horário deseja que aula termine? Exemplo: 10:00.",
            telefone=settings.WHATSAPP_TEST_RECIPIENT,
        )

        try:
            logger.info(
                'Aluno solicitou reagendamento de aula no bot de um novo horario_inicio'
            )
        except Exception:
            pass
        
        

# aluno seleciona a opcao de mudar de aula
# salva no redis que o aluno iniciou a opcao 2
# verifica em qual estado esta
# escolha qual aula informando dia quer mudar
# escolha o novo horario de inicio e de fim
# escreve o motivo pra querer mudar a aula
# personal confirmar ou rejeita no aplicativo e envia a notificacao pro whatsapp do aluno

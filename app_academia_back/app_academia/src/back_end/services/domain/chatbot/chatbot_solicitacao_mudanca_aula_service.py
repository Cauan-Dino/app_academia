"""Etapas da conversa para solicitar e cancelar o reagendamento de uma aula."""

from sqlalchemy.ext.asyncio import AsyncSession
from back_end.services.infra.database.models import DiaDaSemana
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, and_
from back_end.services.infra.database.models import AulaFixa, Alunos, ParticipanteAula, SolicitacaoMudanca, StatusSolicitacao
from back_end.core.logging.logs_settings import logger
from redis.asyncio import RedisError, Redis
from .whatsapp_service import WhatsappService
from .utils_chatbot_service import UtilsChatbotService
from .setting import settings
from back_end.schemas.chatbot_schemas import SessaoReagendamento
from back_end.services.domain.notificacao.enviar_notificaco_service import NotificacaoService

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
        notificacao_service: NotificacaoService
        ):  
        """Recebe o banco, o envio de mensagens e as dependências de sessão."""
        self.db = db
        self.redis_client = redis_client
        self.whatsapp_service = whatsapp_service
        self.utils_chatbot_service = utils_chatbot_service
        self.notificacao_service = notificacao_service
        
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
        elif cache.get('nova_data_hora_fim') == 'aguardando':
            await self._mudar_horario_fim(hora_fim=texto_aluno, telefone_aluno=telefone_aluno)
        elif cache.get("motivo") == "aguardando":
            await self._adicionar_motivo_de_reagendamento_aula(texto_aluno=texto_aluno, telefone_aluno=telefone_aluno,)

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
            exigir_data_futura=False
        )
        if data_hora is None:
            return
        
        # Pega o dia da semana, ex: quarta = 2
        dia_da_semana = DIAS_DA_SEMANA[data_hora.weekday()]
        horario_inicio = data_hora.time()
        query = (
            select(
                AulaFixa,
                Alunos.id.label('aluno_id'),
                Alunos.nome.label('aluno_nome'),
                AulaFixa.personal_id.label("personal_id"),
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

        # Desempacota os tres valores do único registro encontrado.
        aula, aluno_id, aluno_nome, personal_id = aula[0]
        
        sessao: SessaoReagendamento = {
            "personal_id": personal_id,
            "aluno_nome": aluno_nome,
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

        
        logger.info(
            f'Aula {aula.id} foi marcada pra ser reagendada do aluno {aluno_id}.'
        )


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
            exigir_data_futura=True
        )
        if data_hora is None:
            return

        # Verifica ja existe uma aula cadastrada nessa data
        query_aula_fixa_existente = (
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

        resultado_aula_fixa_existente = (await self.db.scalars(query_aula_fixa_existente)).all()
        if resultado_aula_fixa_existente:
            await self.whatsapp_service.enviar_mensagem_texto(
                texto='Você já possui uma aula nesse horario.',
                telefone=settings.WHATSAPP_TEST_RECIPIENT
            )
            return 

        # Verifica se existe uma aula remarcada pra essa data, verificando apenas o nova_data_hora_inicio
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
        resultado_aula_remarcada_pro_msm_horario = await self.db.scalar(query_aula_remarcada_pro_msm_horario.limit(1))
        if resultado_aula_remarcada_pro_msm_horario:
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
        
        
        logger.info(
            'Aluno solicitou reagendamento de aula no bot de um novo horario_inicio',
            extra={
                'aluno_id': sessao.get("aluno_id"),
                'aula_fixa': sessao.get('aula_fixa_id')
            }
        )


    async def _mudar_horario_fim(
            self,
            hora_fim: str,
            telefone_aluno: str,
        ) -> None:

            sessao = await self.utils_chatbot_service.obter_sessao_ativa_ou_avisar(
                telefone_aluno=telefone_aluno
            )
            if sessao is None:
                logger.info(
                    "Não foi possível recuperar a sessão de reagendamento "
                    "ao processar o novo horário fim."
                )
                return
            
            # Converte hora_fim de str no formato HH:MM para um objeto time
            try:
                hora_fim_time = datetime.strptime(
                    hora_fim.strip(),
                    "%H:%M",
                ).time()
            except ValueError:
                await self.whatsapp_service.enviar_mensagem_texto(
                    texto="Horário inválido. Informe no formato HH:MM. Exemplo: 10:30.",
                    telefone=settings.WHATSAPP_TEST_RECIPIENT,
                )
                return

            nova_data_hora_inicio = datetime.fromisoformat(sessao['nova_data_hora_inicio'])
            hora_inicio_time  = nova_data_hora_inicio.time() 

            if hora_inicio_time >= hora_fim_time: 
                await self.whatsapp_service.enviar_mensagem_texto(
                    texto=(
                        "O horário de término deve ser posterior "
                        "ao horário de início da aula."
                    ),
                    telefone=settings.WHATSAPP_TEST_RECIPIENT,
                )
                return

            nova_data_hora_fim = datetime.combine(
                nova_data_hora_inicio.date(),
                hora_fim_time,
            )

            # Verifica se ha sobreposicao em alguma aula marcada em AulaFixa
            query_aula_fixa = (
                select(AulaFixa.id)
                .join(
                    ParticipanteAula,
                    ParticipanteAula.aula_fixa_id == AulaFixa.id,
                )
                .where(
                    ParticipanteAula.aluno_id == sessao["aluno_id"],
                    AulaFixa.id != sessao["aula_fixa_id"],
                    AulaFixa.dia_da_semana == DIAS_DA_SEMANA[nova_data_hora_inicio.weekday()],
                    AulaFixa.horario_inicio < hora_fim_time,
                    AulaFixa.horario_fim > hora_inicio_time,
                )
                .limit(1)
            )

            aula_fixa_id  = await self.db.scalar(query_aula_fixa)
            if aula_fixa_id :
                await self.whatsapp_service.enviar_mensagem_texto(
                    texto=(
                        "Você já possui uma aula nesse período.\n"
                        "Por favor, escolha outra data ou outro horário."
                    ),
                    telefone=settings.WHATSAPP_TEST_RECIPIENT,
                )
                logger.info(
                    "Reagendamento não continuado: aluno já possui uma aula no período informado.",
                    extra={
                        "aluno_id": sessao.get('aluno_id') ,
                        "nova_data_hora_inicio": nova_data_hora_inicio.isoformat(),
                        "nova_hora_fim": hora_fim_time.isoformat()
                    },
                )
                return

            # Verifica se ha sobreposicao em uma aula ja reagendada
            query_aula_reagendada = (
                select(SolicitacaoMudanca.id)
                .where(
                    SolicitacaoMudanca.aluno_id == sessao["aluno_id"],
                    SolicitacaoMudanca.nova_data_hora_inicio
                    < nova_data_hora_fim,
                    SolicitacaoMudanca.nova_data_hora_fim
                    > nova_data_hora_inicio,
                    SolicitacaoMudanca.status.in_(
                        [
                            StatusSolicitacao.PENDENTE,
                            StatusSolicitacao.ACEITA,
                        ]
                    ),
                )
                .limit(1)
            )

            aula_reagendada_id = await self.db.scalar(query_aula_reagendada)
            if aula_reagendada_id:
                await self.whatsapp_service.enviar_mensagem_texto(
                    texto=(
                        "Você já possui uma aula reagendada nesse período.\n"
                        "Por favor, escolha outra data ou outro horário."
                    ),
                    telefone=settings.WHATSAPP_TEST_RECIPIENT,
                )
                logger.info(
                    "Reagendamento não continuado: aluno já possui uma aula reagendada no período informado.",
                    extra={
                        "solicitacao_id": aula_reagendada_id,
                        "nova_data_hora_inicio": nova_data_hora_inicio.isoformat(),
                        "nova_data_hora_fim": nova_data_hora_fim.isoformat(),
                    }
                )
                return
            
            # Atualiza a sesssao de reagendamento de aula no redis
            sessao["nova_data_hora_fim"] = nova_data_hora_fim.isoformat()
            
            await self.utils_chatbot_service.salvar_situacao_de_agendamento_de_aula_no_redis(
                telefone_aluno=telefone_aluno,
                sessao=sessao
            )
            await self.whatsapp_service.enviar_mensagem_texto(
                texto=(
                    'Qual o motivo do reagendamento?\n\n'
                    'Escreva em até 250 caracteres.'
                ),
                telefone=settings.WHATSAPP_TEST_RECIPIENT,
            )
            logger.info(
                "Aula original selecionada para reagendamento.",
                extra={
                    "aula_fixa_id": aula_fixa_id,
                    "aluno_id": sessao["aluno_id"],
                },
            )


    async def _adicionar_motivo_de_reagendamento_aula(
        self,
        texto_aluno: str,
        telefone_aluno: str,
    ) -> None:
        sessao: SessaoReagendamento | None = await self.utils_chatbot_service.obter_sessao_ativa_ou_avisar(
                telefone_aluno=telefone_aluno
            )
        if sessao is None:
            logger.info(
                "Não foi possível recuperar a sessão de reagendamento "
                "ao processar o novo horário fim."
            )
            return

        motivo = texto_aluno.strip()

        if not motivo or len(motivo) > 250:
            await self.whatsapp_service.enviar_mensagem_texto(
                texto=(
                    "Informe o motivo do reagendamento em até 250 caracteres."
                    if not motivo
                    else (
                        "O motivo do reagendamento deve ter no máximo 250 caracteres. "
                        "Por favor, resuma o motivo e envie novamente."
                    )
                ),
                telefone=settings.WHATSAPP_TEST_RECIPIENT
            )
            return

        # Expiracao pra solicitação de mudanca de hora expirar
        expiracao = datetime.now(timezone.utc) + timedelta(days=1)
        
        # Salva no banco que a solicitacao foi enviada
        reagendamento_aula = SolicitacaoMudanca(
            personal_id=sessao["personal_id"],
            aluno_id=sessao["aluno_id"],
            aula_fixa_id=sessao["aula_fixa_id"],
            data_hora_aula_original=datetime.fromisoformat(
                sessao["data_hora_aula_original"]
            ),
            nova_data_hora_inicio=datetime.fromisoformat(
                sessao["nova_data_hora_inicio"]
            ),
            nova_data_hora_fim=datetime.fromisoformat(
                sessao["nova_data_hora_fim"]
            ),
            motivo=motivo,
            status=StatusSolicitacao.PENDENTE,
            expira_em=expiracao
        )

        try:
            self.db.add(reagendamento_aula)
            await self.db.commit()
        except Exception:
            await self.db.rollback()

            logger.exception(
                "Erro ao registrar solicitação de reagendamento.",
                extra={
                    "aula_fixa_id": sessao["aula_fixa_id"],
                    "aluno_id": sessao["aluno_id"],
                },
            )

            await self.whatsapp_service.enviar_mensagem_texto(
                texto="Ocorreu um erro. Por favor, tente novamente mais tarde.",
                telefone=settings.WHATSAPP_TEST_RECIPIENT,
            )
            return


        # Exclui a sessao salva no redis
        try:
            await self.redis_client.delete(
                f"chatbot:reagendamento:{telefone_aluno}:aula_original"
            )
        except RedisError:
            logger.warning(
                "Solicitação salva, mas não foi possível remover "
                "a sessão de reagendamento.",
                exc_info=True,
            )

        await self.whatsapp_service.enviar_mensagem_texto(
            texto=(
                "Sua solicitação de reagendamento foi registrada! ✅\n\n"
                "Agora ela aguarda a aprovação ou recusa do seu personal. "
                "Até a aprovação, sua aula continua na data e no horário originais."
            ),
            telefone=settings.WHATSAPP_TEST_RECIPIENT,
        )
        
        # Envia notificação pro personal informando que o aluno deseja reagendar a aula
        data_original = datetime.fromisoformat(sessao['data_hora_aula_original'])
        novo_inicio = datetime.fromisoformat(sessao['nova_data_hora_inicio'])
        novo_fim = datetime.fromisoformat(sessao['nova_data_hora_fim'])

        await self.notificacao_service.enviar_notificacao(
            personal_id=sessao['personal_id'],
            title=f"Pedido de reagendamento: {sessao['aluno_nome']}",
            body=(
                f"Aula de {data_original.strftime('%d/%m às %H:%M')} "
                f"para {novo_inicio.strftime('%d/%m %H:%M')} "
                f"– {novo_fim.strftime('%H:%M')}.\n"
                f"Motivo: {motivo}"
            ),
        )
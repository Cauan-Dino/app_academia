"""Textos do menu, consulta de aulas e encerramento da sessão principal."""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from back_end.services.infra.database.models import Alunos, AulaFixa, ParticipanteAula, SolicitacaoMudanca, StatusSolicitacao
from redis.asyncio import Redis
from back_end.core.logging.logs_settings import logger
from datetime import datetime, timezone
from .utils_chatbot_service import FUSO_HORARIO_ACADEMIA

class ChatBotOptionsService:
    """Prepara as respostas das opções disponíveis no menu do chatbot."""

    def __init__(self, db: AsyncSession, redis_client: Redis):
        """Recebe o banco para consultar aulas e o Redis para encerrar sessões."""
        self.db = db
        self.redis_client = redis_client

    @staticmethod
    def menu():
        """Retorna o texto de boas-vindas com as opções de consulta, mudança e saída."""
        menu = [
            "Olá! Seja bem-vindo ao atendimento da academia.",
            "",
            "Escolha uma opção:",
            "[1] Consultar minhas aulas",
            "[2] Reagendar uma aula",
            "[0] Fechar a sessão"
        ]
        return "\n".join(menu)


    async def resposta_opcao_1_consultar_aulas(
        self,
        telefone_aluno
        ) -> str:
        """Lista em texto as aulas dos personais vinculados ao telefone informado.

        A consulta atual associa aluno e aula pelo personal, sem filtrar
        inscrições em ParticipanteAula. Retorna um aviso se não houver aulas.
        """
        agora_local = datetime.now(FUSO_HORARIO_ACADEMIA).replace(tzinfo=None)
        agr_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        query = (
            select(
                AulaFixa,
                SolicitacaoMudanca,
                )
            .join(
                ParticipanteAula,
                ParticipanteAula.aula_fixa_id == AulaFixa.id,
            )
            .join(
                Alunos,
                Alunos.id == ParticipanteAula.aluno_id,
            )
            .outerjoin(
                SolicitacaoMudanca,
                and_(
                    SolicitacaoMudanca.aluno_id == Alunos.id,
                    SolicitacaoMudanca.personal_id == AulaFixa.personal_id,
                    SolicitacaoMudanca.aula_fixa_id == ParticipanteAula.aula_fixa_id,
                    SolicitacaoMudanca.nova_data_hora_fim  > agora_local,
                    or_(
                        SolicitacaoMudanca.status == StatusSolicitacao.ACEITA,
                        and_(
                            SolicitacaoMudanca.status == StatusSolicitacao.PENDENTE,
                            SolicitacaoMudanca.expira_em > agr_utc,
                        ),
                    ),
                    SolicitacaoMudanca.status.in_(
                        [
                            StatusSolicitacao.PENDENTE,
                            StatusSolicitacao.ACEITA,
                        ]
                    )
                )
            )
            .where(
                Alunos.telefone == telefone_aluno,
            )
        )
        resultado = await self.db.execute(query)
        linhas = resultado.all()

        if not linhas:
            return "Nenhuma aula encontrada."


        aulas_fixas_por_id: dict[int, str] = {}
        solicitacoes_por_id: dict[int, str] = {}

        for aula_fixa, solicitacao in linhas:
            horario_inicio = aula_fixa.horario_inicio.strftime("%H:%M")
            horario_fim = aula_fixa.horario_fim.strftime("%H:%M")
            dia = aula_fixa.dia_da_semana.value.capitalize()

            aulas_fixas_por_id[aula_fixa.id] = (
                f"• {dia}: {horario_inicio} às {horario_fim}"
            )

            if solicitacao is not None:
                horario_original = (
                    solicitacao.data_hora_aula_original
                    .strftime("%d/%m/%Y às %H:%M")
                )

                nova_data = (
                    solicitacao.nova_data_hora_inicio
                    .strftime("%d/%m/%Y")
                )
                novo_inicio = (
                    solicitacao.nova_data_hora_inicio
                    .strftime("%H:%M")
                )
                novo_fim = (
                    solicitacao.nova_data_hora_fim
                    .strftime("%H:%M")
                )

                status = solicitacao.status.value.capitalize()

                solicitacoes_por_id[solicitacao.id] = (
                    f"• {horario_original} → "
                    f"{nova_data}, das {novo_inicio} às {novo_fim} "
                    f"({status})"
                )

        texto_aulas_fixas = "\n".join(
            aulas_fixas_por_id.values()
        )

        texto_reagendamentos = "\n".join(
            solicitacoes_por_id.values()
        )
        partes = [
            "📅 *Suas aulas fixas:*",
            texto_aulas_fixas,
        ]

        if solicitacoes_por_id:
            partes.extend(
                [
                    "🔄 *Solicitações de reagendamento:*",
                    texto_reagendamentos,
                ]
            )

        return "\n\n".join(partes)

        

    async def resposta_opcao_2_(
        self,
        telefone_aluno: str
    ) -> str:
        """Retorna a primeira pergunta do reagendamento e a instrução para sair."""
        aulas_cadastradas = await self.resposta_opcao_1_consultar_aulas(telefone_aluno=telefone_aluno)
        return (
            "Vamos solicitar o reagendamento da sua aula! 😊\n"
            "Vou pedir uma informação por vez.\n\n"
            "Primeiro, qual é a data e o horário de início "
            "da aula que você deseja mudar?\n\n"
            "Responda neste formato: 14/09/2026 às 08:00\n\n"
            f"Essas são suas aulas cadastradas:\n\n"
            f'{aulas_cadastradas}\n\n'
            "Digite 0 pra sair da conversa"
        )


    async def resposta_opcao_0_(
        self,
        telefone: str
    ) -> str:
        """Exclui a sessão do menu e retorna a mensagem de conversa encerrada.

        Uma chave ausente é apenas registrada no log. Falhas de acesso ao
        Redis são propagadas para o chamador.
        """
        # Revoga a chave da conversa
        chave = await self.redis_client.delete(f'chatbot:sessao:{telefone}')
        if chave == 0:
            logger.info(f'Nenhuma sessão ativa encontrada para {telefone}')

        return (
            'Conversa encerrada.'
        )


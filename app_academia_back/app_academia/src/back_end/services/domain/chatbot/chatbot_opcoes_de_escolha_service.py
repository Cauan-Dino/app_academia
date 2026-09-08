"""Textos do menu, consulta de aulas e encerramento da sessão principal."""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from back_end.services.infra.database.models import Alunos, AulaFixa, ParticipanteAula
from redis.asyncio import Redis
from back_end.core.logging.logs_settings import logger

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
        query = (
            select(AulaFixa)
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
            )
        )
        resultado = await self.db.execute(query)
        aulas = resultado.scalars().all()

        if not aulas:
            return "Nenhuma aula encontrada."

        linhas = ["Suas aulas:"]

        for aula in aulas:
            inicio = aula.horario_inicio.strftime("%H:%M")
            fim = aula.horario_fim.strftime("%H:%M")

            dia = aula.dia_da_semana.value.capitalize()

            linhas.append(
                f"• {dia}: {inicio} às {fim}"
            )

        return "\n".join(linhas)

        

    def resposta_opcao_2_(
        self
    ) -> str:
        """Retorna a primeira pergunta do reagendamento e a instrução para sair."""
        return (
            "Vamos solicitar o reagendamento da sua aula! 😊\n"
            "Vou pedir uma informação por vez.\n\n"
            "Primeiro, qual é a data e o horário de início "
            "da aula que você deseja mudar?\n\n"
            "Responda neste formato: 14/09/2026 às 08:00\n\n"
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


from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from back_end.services.infra.database.models import Alunos, AulaFixa
from redis.asyncio import Redis
from back_end.core.logging.logs_settings import logger

class ChatBotOptionsService:
    def __init__(self, db: AsyncSession, redis_client: Redis):
        self.db = db
        self.redis_client = redis_client

    @staticmethod
    def menu():
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

        query = (
            select(AulaFixa)
            .join(
                Alunos,
                Alunos.personal_id == AulaFixa.personal_id 
            )
            .where(
                Alunos.telefone == telefone_aluno
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
        # Revoga a chave da conversa
        chave = await self.redis_client.delete(f'chatbot:sessao:{telefone}')
        if chave == 0:
            logger.info(f'Nenhuma sessão ativa encontrada para {telefone}')

        return (
            'Conversa encerrada.'
        )


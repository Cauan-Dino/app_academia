from back_end.services.infra.database.models import AulaFixa, Personal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException
from back_end.services.infra.database.models import DiaDaSemana
from datetime import time

from datetime import datetime
from back_end.services.infra.database.models import (
    SolicitacaoMudanca,
    StatusSolicitacao,
)
from back_end.services.domain.chatbot.utils_chatbot_service import (
    FUSO_HORARIO_ACADEMIA,
)

class ClassQueryService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def verifica_sobreposicao_de_horario(
        self,
        dia_da_semana: DiaDaSemana,
        horario_inicio: time,
        horario_fim: time,
        personal_id: int,
        id_ignorado: int | None = None,
    ) -> None:
        # Busca se o Personal ja possui uma aula cadastrada com os horarios enviados no paramentro
        query = select(AulaFixa.id).where(
            AulaFixa.personal_id == personal_id,
            AulaFixa.dia_da_semana == dia_da_semana,

            # Verifica a sobreposição
            AulaFixa.horario_inicio < horario_fim,
            AulaFixa.horario_fim > horario_inicio,
        ).limit(1) # So pega uma linha no banco de dados msm se existir mais de uma
    
        if id_ignorado is not None:
            query = query.where(
                AulaFixa.id != id_ignorado,
            )

        aula_existente = await self.db.scalar(query)

        if aula_existente is not None:
            raise HTTPException(
                status_code=409,
                detail="Já existe outra aula nesse período.",
            )

        # Os horários das aulas estão salvos no horário local da academia.
        agora_local = datetime.now(
            FUSO_HORARIO_ACADEMIA
        ).replace(tzinfo=None)

        query_reagendamentos = (
            select(SolicitacaoMudanca)
            .where(
                SolicitacaoMudanca.personal_id == personal_id,
                SolicitacaoMudanca.status == StatusSolicitacao.ACEITA,
                SolicitacaoMudanca.nova_data_hora_fim > agora_local,
            )
            .with_for_update()
        )

        reagendamentos = (
            await self.db.scalars(query_reagendamentos)
        ).all()

        dias_da_semana = (
            DiaDaSemana.SEGUNDA,
            DiaDaSemana.TERCA,
            DiaDaSemana.QUARTA,
            DiaDaSemana.QUINTA,
            DiaDaSemana.SEXTA,
            DiaDaSemana.SABADO,
            DiaDaSemana.DOMINGO,
        )

        for solicitacao in reagendamentos:
            inicio = solicitacao.nova_data_hora_inicio
            fim = solicitacao.nova_data_hora_fim

            mesmo_dia = (
                dias_da_semana[inicio.weekday()] == dia_da_semana
            )

            horarios_sobrepostos = (
                inicio.time() < horario_fim
                and fim.time() > horario_inicio
            )

            if mesmo_dia and horarios_sobrepostos:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "Já existe um reagendamento aceito em "
                        f"{inicio.strftime('%d/%m/%Y, das %H:%M')} "
                        f"às {fim.strftime('%H:%M')}."
                    ),
                )


    async def bloquear_agenda_do_personal(
        self,
        personal_id: int
        ):
        """
        Se duas requisições chegarem ao mesmo tempo vinda do msm personal
        A primeira requisição bloqueia a linha da Tabela Personal onde tem o mesmo Personal.id enviado
        Se chegar a segunda requisição ela só será executada após a primeira ser liberada
        """
        query = ( 
            select(Personal)
            .where(
                Personal.id == personal_id
            )
            .with_for_update()
        )
        personal_encontrado = await self.db.scalar(query)

        if personal_encontrado is None:
            raise HTTPException(
                status_code=404,
                detail='Esse id não encontrado'
            )
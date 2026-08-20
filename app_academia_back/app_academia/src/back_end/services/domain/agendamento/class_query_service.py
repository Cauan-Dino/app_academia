from back_end.services.infra.database.models import AulaFixa, Personal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException
from back_end.services.infra.database.models import DiaDaSemana
from datetime import time

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
from back_end.services.infra.database.models import AulaFixa, Alunos, ParticipanteAula
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from fastapi import HTTPException
from back_end.schemas.agendamento_schema import CadastrarAlunoNaAula
from back_end.services.domain.aluno.aluno_utils import PersonalClientUtils


class StudentAddClassService:

    def __init__(self, db: AsyncSession, personal_client_utils: PersonalClientUtils):
        self.db = db
        self.personal_client_utils = personal_client_utils


    async def buscar_aulas_do_aluno(
        self,
        aluno_id: int,
        access_token: dict
        ) -> list[dict]:
        personal_id = access_token["id"]
        query_aluno = (
            select(Alunos)
            .where(
                Alunos.personal_id == personal_id,
                Alunos.id == aluno_id
            )
        )

        aluno = await self.db.scalar(query_aluno)
        if not aluno:
            raise HTTPException(
                status_code=404,
                detail='Esse aluno não existe.'
            )

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
                ParticipanteAula.aluno_id == aluno_id,
                Alunos.personal_id == personal_id,
                AulaFixa.personal_id == personal_id,
            )
            .order_by(
                AulaFixa.dia_da_semana,
                AulaFixa.horario_inicio,
            )
        )

        resultado = await self.db.execute(query)
        aulas = resultado.scalars().all()

        if not aulas:
            raise HTTPException(
                status_code=404,
                detail='Esse aluno não está cadastrado em nenhuma aula.'
            )

        return [
            {
                "aula_id": aula.id,
                "dia_da_semana": aula.dia_da_semana,
                "horario_inicio": aula.horario_inicio,
                "horario_fim": aula.horario_fim,
            }
            for aula in aulas
        ]


    async def cadastrar_aluno_na_aula(
        self,
        body: CadastrarAlunoNaAula,
        access_token: dict
        ) -> dict:
        """
        Cadastra um aluno em uma aula fixa do personal autenticado.

        Verifica se a aula e o aluno pertencem ao personal, se o aluno ainda
        não participa da aula e se há capacidade disponível. A aula é bloqueada
        durante a operação para reduzir conflitos entre cadastros simultâneos.

        Args:
            body: Dados contendo os identificadores da aula fixa e do aluno.
            access_token: Dados do token de acesso contendo o ID do personal
                autenticado na chave ``id``.

        Returns:
            Dicionário contendo a mensagem de confirmação do cadastro.

        Raises:
            HTTPException: Com status 404 quando a aula ou o aluno não existir
                para o personal autenticado.
            HTTPException: Com status 409 quando o aluno já estiver cadastrado
                ou a aula tiver atingido sua capacidade máxima.
            HTTPException: Com status 500 quando ocorrer um erro do banco de
                dados ao salvar o participante.
        """
        personal_id = access_token['id']

        # Verifica se o personal e a aula existem
        query_personal_e_aula = (
            select(AulaFixa)
            .where(
                AulaFixa.personal_id == personal_id,
                AulaFixa.id == body.aula_fixa_id
            )
            .with_for_update() # Bloqueia a aula durante a operação.
        )
        resultado_personal_e_aula = await self.db.execute(query_personal_e_aula)
        personal_e_aula = resultado_personal_e_aula.scalar_one_or_none()

        if personal_e_aula is None:
            raise HTTPException(
                status_code=404,
                detail="Essa aula não existe."
            )
        
        # Verifica se o aluno existe
        query_aluno = (
            select(Alunos)
            .where(
                Alunos.id == body.aluno_id,
                Alunos.personal_id == personal_id
            )
        )
        resultado_aluno = await self.db.execute(query_aluno)
        aluno = resultado_aluno.scalar_one_or_none()

        if aluno is None:
            raise HTTPException(
                status_code=404,
                detail='Esse aluno não existe!'
            )

        # Verifica se o aluno já está cadastrado na aula
        query_participantes_da_aula = (
            select(ParticipanteAula)
            .where(
                ParticipanteAula.aluno_id == body.aluno_id,
                ParticipanteAula.aula_fixa_id == body.aula_fixa_id
            )
        )
        resultado_participantes_da_aula = await self.db.execute(query_participantes_da_aula)
        participantes_da_aula = resultado_participantes_da_aula.scalar_one_or_none()
        if participantes_da_aula:
            raise HTTPException(
                status_code=409,
                detail='Esse aluno já está cadastrado nessa aula.'
            )

        # Conta os participantes da aula
        query_quant_alunos_na_aula = (
            select(
                func.count(ParticipanteAula.id)
                )
                .where(
                    ParticipanteAula.aula_fixa_id == body.aula_fixa_id
                )
            )
        resultado_quant_alunos_na_aula = await self.db.execute(query_quant_alunos_na_aula)
        quant_alunos_na_aula = resultado_quant_alunos_na_aula.scalar_one()
        if quant_alunos_na_aula >= personal_e_aula.capacidade_max:
            raise HTTPException(
                status_code=409,
                detail="A aula atingiu a capacidade máxima."
            )
        
        participante = ParticipanteAula(
            aula_fixa_id=body.aula_fixa_id,
            aluno_id=body.aluno_id,
        )

        self.db.add(participante)
        try:
            await self.db.commit()

        except IntegrityError as erro:
            await self.db.rollback()
            raise HTTPException(
                status_code=409,
                detail="Esse aluno já está cadastrado nessa aula.",
            ) from erro

        except SQLAlchemyError as erro:
            await self.db.rollback()
            raise HTTPException(
                status_code=500,
                detail="Erro ao salvar o aluno na aula.",
            ) from erro 
        
        return {
            "message": "Aluno adicionado à aula com sucesso.",
        }


    async def buscar_alunos_cadastrados_na_aula(
        self,
        access_token: dict,
        aula_id: int
        ):
        personal_id = access_token['id']

        # Verifica se a aula existe
        query_aula = select(AulaFixa).where(
            AulaFixa.personal_id == personal_id,
            AulaFixa.id == aula_id
            )
        resultado_aula = await self.db.execute(query_aula)
        aula = resultado_aula.scalar_one_or_none()

        if aula is None:
            raise HTTPException(
                status_code=404,
                detail='Essa aula não existe.'
            )

        # Verifica se há alunos cadastrado na aula
        query = (
            select(
                ParticipanteAula.aula_fixa_id,
                Alunos.id,
                Alunos.nome,
                Alunos.personal_id,
                Alunos.telefone
            )
            .join(
                Alunos,
                Alunos.id == ParticipanteAula.aluno_id
            )
            .where(
                ParticipanteAula.aula_fixa_id == aula_id,
                Alunos.personal_id == personal_id
            )
            .order_by(Alunos.nome)
        )
        resultado = await self.db.execute(query)
        alunos_na_aula = resultado.all()

        if not alunos_na_aula:
            raise HTTPException(
                status_code=404,
                detail='Nenhum aluno está cadastrado na aula.'
            )

        return [
            {
                "aula_id": aula_fixa_id,
                "aluno_id": aluno_id,
                "nome_aluno": nome,
                "personal_id": personal_id,
                "telefone": telefone
            }
            for aula_fixa_id, aluno_id, nome, personal_id, telefone in alunos_na_aula

        ]



    async def deletar_aluno_cadastrado_na_aula(
        self,
        aluno_id: int,
        aula_fixa_id: int,
        access_token: dict,
        ):
        personal_id = access_token['id']

        # Verifica se o aluno existe
        query_aluno = select(Alunos).where(
            Alunos.id == aluno_id,
            Alunos.personal_id == personal_id
        )
        resultado_aluno = await self.db.execute(query_aluno)
        aluno = resultado_aluno.scalar_one_or_none()

        if aluno is None:
            raise HTTPException(
                status_code=404,
                detail='Esse aluno não existe.'
            )

        # Verifica se a aula existe
        query_aula = select(AulaFixa).where(
            AulaFixa.id == aula_fixa_id,
            AulaFixa.personal_id == personal_id
        )
        resultado_aula = await self.db.execute(query_aula)
        aula = resultado_aula.scalar_one_or_none()

        if aula is None:
            raise HTTPException(
                status_code=404,
                detail='Essa aula não existe.'
            )

        # Verifica se o aluno ta cadastrado na aula
        query_deletar_aluno_na_aula = select(ParticipanteAula).where(
            ParticipanteAula.aula_fixa_id == aula_fixa_id,
            ParticipanteAula.aluno_id == aluno_id
        )
        resultado = await self.db.execute(query_deletar_aluno_na_aula)
        deletar_aluno_na_aula = resultado.scalar_one_or_none()

        if deletar_aluno_na_aula is None:
            raise HTTPException(
                status_code=404,
                detail='Esse aluno não está cadastrado na aula.'
            )

        try:
            await self.db.delete(deletar_aluno_na_aula)
            await self.db.commit()

        except IntegrityError as erro:
            await self.db.rollback()

            raise HTTPException(
                status_code=409,
                detail="Não foi possível remover o aluno dessa aula.",
            ) from erro

        except SQLAlchemyError as erro:
            await self.db.rollback()

            raise HTTPException(
                status_code=500,
                detail="Erro ao remover o aluno da aula.",
            ) from erro

        return {'message':f'Aluno {aluno.nome} deletado com sucesso!'} 
        

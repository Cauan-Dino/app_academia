from back_end.services.infra.database.models import AulaFixa, ParticipanteAula
from back_end.schemas.agendamento_schema import AgendarAula, AlterarAula
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from fastapi import HTTPException
from back_end.services.domain.agendamento.class_query_service import ClassQueryService
from back_end.services.infra.database.models import DiaDaSemana
from datetime import time
from back_end.services.domain.aluno.aluno_utils import PersonalClientUtils

class ClassRegisterService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.class_query_service = ClassQueryService(self.db) 
        self.personal_client_utils = PersonalClientUtils()


    async def cadastrar_aula(
        self,
        body: AgendarAula,
        access_token: dict
        ) -> dict:
        """
        Cadastra uma nova aula fixa para o personal.

        Valida o horário e a capacidade máxima da aula,
        verifica se já existe uma aula no mesmo dia e horário
        e salva a nova aula no banco de dados.

        Args:
            body: Dados da aula a ser cadastrada.
            access_token: Dados do usuário autenticado.

        Returns:
            Uma mensagem informando que a aula foi cadastrada
            com sucesso.

        Raises:
            HTTPException: Se os dados da aula forem inválidos,
            se já existir uma aula no horário ou se ocorrer
            um erro ao salvar no banco.
        """
        if body.horario_fim <= body.horario_inicio:
            raise HTTPException(
                status_code=400,
                detail="O horário final deve ser posterior ao horário inicial.",
            )
            
        if body.capacidade_max <= 0:
            raise HTTPException(
                status_code=400,
                detail='Você precisa ter ao menos um aluno cadastrado nessa aula.'
            )

        try:
            personal_id = access_token['id']
            # Bloqueia a linha do personal até commit ou rollback
            await self.class_query_service.bloquear_agenda_do_personal(
                personal_id=personal_id,
            )
            
            # Verifica se o Personal ja possui uma aula nesse horario
            await self.class_query_service.verifica_sobreposicao_de_horario(
                dia_da_semana=body.dia_da_semana,
                horario_inicio=body.horario_inicio,
                horario_fim=body.horario_fim,
                personal_id=personal_id,
            )
            
            cadastro_aula = AulaFixa(
                **body.model_dump(),
                personal_id=personal_id
            )

            self.db.add(cadastro_aula)
            await self.db.flush()
            aula_id = cadastro_aula.id
            await self.db.commit()

        except HTTPException:
            await self.db.rollback()
            raise 
        
        except IntegrityError as erro:
            await self.db.rollback()
            raise HTTPException(
                status_code=409,
                detail="Já existe outra aula nesse horário.",
            ) from erro

        except SQLAlchemyError as erro:
            await self.db.rollback()
            raise HTTPException(
                status_code=500,
                detail="Erro ao salvar no banco de dados.",
            ) from erro
        
        return {
            "message": "Aula cadastrada com sucesso.",
            "aula_id": aula_id,
        }  



    async def alterar_informacoes_aula(
        self,
        aula_id: int,
        body: AlterarAula,
        access_token: dict
        ) -> dict:
        personal_id = access_token['id']
        try:
            # Bloqueio comum para todas as aulas desse personal
            await self.class_query_service.bloquear_agenda_do_personal(
                personal_id=personal_id,
            )

            # Bloqueio específico da aula alterada
            query = select(AulaFixa).where(
                AulaFixa.id == aula_id,
                AulaFixa.personal_id == personal_id
                ).with_for_update()
            resultado = await self.db.execute(query)
            aula = resultado.scalar_one_or_none()

            if not aula:
                raise HTTPException(
                    status_code=404,
                    detail='Essa aula não existe.'
                ) 

            # Pega apenas os valores enviados no payload
            valores = body.model_dump(exclude_unset=True)
            if not valores:
                raise HTTPException(
                    status_code=400,
                    detail="Nenhuma informação foi enviada para alteração."
                )

            # Impede o usuario de enviar um payload com valores None ou null
            campos_nulos  = [
                campo
                for campo, valor in valores.items()
                if valor is None 
            ]
            if campos_nulos:
                raise HTTPException(
                    status_code=400,
                    detail="Os campos enviados não podem ser nulos.",
                )

            # Tenta pegar o valor enviado pelo body, se não conseguir usar o atributo do objeto aula
            dia_da_semana = valores.get(
                "dia_da_semana",
                aula.dia_da_semana,
            )
            horario_inicio = valores.get(
                "horario_inicio",
                aula.horario_inicio,
            )
            horario_fim = valores.get(
                "horario_fim",
                aula.horario_fim,
            )



            if horario_fim <= horario_inicio:
                raise HTTPException(
                    status_code=400,
                    detail="O horário final deve ser posterior ao horário inicial.",
                )

            if "capacidade_max" in valores:
                nova_capacidade = valores["capacidade_max"]
                if nova_capacidade <= 0:
                    raise HTTPException(
                        status_code=400,
                        detail="A capacidade máxima deve ser maior que zero.",
                    )
                
                # Query que pega quantos alunos estão cadastrados na aula
                query_quantidade_alunos = (
                    select(func.count(ParticipanteAula.id))
                    .where(
                        ParticipanteAula.aula_fixa_id == aula_id,
                    )
                )
                alunos_cadastrados_na_aula = await self.db.scalar(query_quantidade_alunos)

                # Impede colocar uma capacidade menor do que a quantidade alunos cadastrados
                if nova_capacidade < alunos_cadastrados_na_aula: 
                    raise HTTPException(
                        status_code=409,
                        detail=(
                            "A capacidade deve ser maior ou igual à "
                            "quantidade de alunos cadastrados na aula."
                        ),
                    )

            await self.class_query_service.verifica_sobreposicao_de_horario(
                dia_da_semana=dia_da_semana,
                horario_fim=horario_fim,
                horario_inicio=horario_inicio,
                personal_id=personal_id,
                id_ignorado=aula_id
            )

            # Aplica as alterações no objeto
            for chave,valor in valores.items():
                setattr(aula, chave, valor)

            aula_id_alterada = aula.id

            await self.db.commit()

        except HTTPException:
            await self.db.rollback()
            raise 

        except IntegrityError as erro: 
            await self.db.rollback()
            raise HTTPException(
                status_code=409,
                detail="Já existe outra aula nesse dia e horário.",
            ) from erro

        except SQLAlchemyError as erro:
            await self.db.rollback()
            raise HTTPException(
                status_code=500,
                detail="Erro ao salvar no banco de dados.",
            ) from erro

        except Exception:
            await self.db.rollback()
            raise

        return {
            "detail": "Aula alterada com sucesso.",
            "aula_id": aula_id_alterada
        }


    async def buscar_aulas(
        self,
        access_token: dict,
        dia_da_semana: DiaDaSemana | None = None,
        horario_inicio: time | None = None,
        horario_fim: time | None = None
        ) -> list[dict]:
        personal_id = access_token['id']

        # Filtro de busca utilizado na query
        filtro = [
            AulaFixa.personal_id == personal_id
        ]

        if dia_da_semana:
            filtro.append(AulaFixa.dia_da_semana == dia_da_semana)

        if horario_fim and horario_inicio:
            filtro.extend(
                [
                    AulaFixa.horario_inicio >= horario_inicio,
                    AulaFixa.horario_fim <= horario_fim
                ]
            )

        else:
            if horario_inicio:
                filtro.append(AulaFixa.horario_inicio == horario_inicio)

            if horario_fim:
                filtro.append(AulaFixa.horario_fim <= horario_fim)

        query = select(AulaFixa) \
            .where(*filtro) \
                .order_by(
                AulaFixa.dia_da_semana,
                AulaFixa.horario_inicio
            )
        resultado = await self.db.execute(query)
        aulas = resultado.scalars().all()

        if not aulas:
            raise HTTPException(
                status_code=404,
                detail='Nenhuma aula foi encontrada.'
            )

        return [
            {
                'dia_da_semana': valor.dia_da_semana,
                "id": valor.id,
                'horario_inicio': valor.horario_inicio,
                'horario_fim': valor.horario_fim,
                'quantidade_max_de_alunos': valor.capacidade_max
            }
            for valor in aulas
        ]


    async def deletar_aula(
        self,
        aula_id: int,
        access_token: dict
        ):
        personal_id = access_token['id']

        query = select(AulaFixa).where(
            AulaFixa.personal_id == personal_id,
            AulaFixa.id == aula_id
            )
        resultado = await self.db.execute(query)
        aula = resultado.scalar_one_or_none()

        if aula is None:
            raise HTTPException(
                status_code=404,
                detail='Esse aula não existe.'
            )

        try:
            await self.db.delete(aula)
            await self.db.commit()

        except IntegrityError:
            await self.db.rollback()
            raise HTTPException(
                status_code=409,
                detail="Já existe outra aula nesse dia e horário.",
            )

        except SQLAlchemyError:
            await self.db.rollback()
            raise HTTPException(
                status_code=500,
                detail="Erro ao salvar no banco de dados.",
            )

        return {'message':'Aula deletada com sucesso.'}
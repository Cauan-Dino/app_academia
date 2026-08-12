from back_end.services.infra.database.models import Alunos
from sqlalchemy.ext.asyncio import AsyncSession
from back_end.schemas.cadastrar_aluno import CadastrarAluno, AlterarInformacoesAluno
from sqlalchemy import select
from fastapi import HTTPException
from back_end.core.logging.logs_settings import logger
from redis.asyncio import Redis
from back_end.services.domain.aluno.aluno_query_service import AlunoQueryService 
from back_end.services.domain.aluno.aluno_utils import PersonalClientUtils

class AlunoCommandService:
    def __init__(self, db: AsyncSession, redis_client: Redis):
        self.db = db
        self.redis_client = redis_client
        self.query_service = AlunoQueryService(db, redis_client)
        self.client_utils = PersonalClientUtils()


    async def cadastrar_aluno(
        self,
        body: CadastrarAluno,
        access_token: dict
        ) -> dict:
        """Função que permite o Personal Cadastrar um aluno"""
        personal_id = self.client_utils.obter_personal_id(access_token)

        body.telefone = await self.query_service.verificar_se_telefone_do_aluno_ja_ta_cadastrado(telefone_aluno=body.telefone, personal_id=personal_id)
        body.nome = await self.query_service.verifica_se_nome_do_aluno_ja_ta_cadastrado(nome_aluno=body.nome, personal_id=personal_id)

        informacoes_aluno = Alunos(**body.model_dump(), personal_id=personal_id)
        self.db.add(informacoes_aluno)

        try:
            await self.db.commit()
        except Exception:
            await self.db.rollback()
            raise HTTPException(
                status_code=500,
                detail="Já existe um aluno com esse número de telefone"
            )

        try:
            await self.redis_client.delete(
                f"alunos:personal:{personal_id}:todos"
                )
        except Exception:
            logger.exception("Não foi possível invalidar o cache dos alunos")
            
        return {'message':'Aluno cadastrado com sucesso!'}



    async def alterar_informacoes_aluno(
        self,
        aluno_id: int,
        body: AlterarInformacoesAluno, 
        access_token: dict
        ) -> dict:
        """Altera as informações do aluno que foi cadastrado"""
        personal_id = self.client_utils.obter_personal_id(access_token)

        query = select(Alunos).where(
            Alunos.id == aluno_id,
            Alunos.personal_id == personal_id
            )
        resultado = await self.db.execute(query)
        alunos = resultado.scalar_one_or_none()

        if not alunos:
            raise HTTPException(
                status_code=404,
                detail="Aluno não encontrado"
            )


        # Pega apenas os campos que foram enviados no payload
        dados_atualizacao = body.model_dump(exclude_unset=True)

        if "telefone" in dados_atualizacao:
            if dados_atualizacao["telefone"] is None:
                raise HTTPException(
                    status_code=400,
                    detail="O telefone não pode ser nulo"
                )
            
            dados_atualizacao['telefone'] = await self.query_service.verificar_se_telefone_do_aluno_ja_ta_cadastrado(
                telefone_aluno=dados_atualizacao['telefone'], 
                personal_id=personal_id,
                aluno_id_ignorado=aluno_id
                )


        if "nome" in dados_atualizacao:
            if dados_atualizacao['nome'] is None:
                raise HTTPException(
                    status_code=400,
                    detail="O nome não pode ser nulo"
                )
            
            dados_atualizacao['nome'] = await self.query_service.verifica_se_nome_do_aluno_ja_ta_cadastrado(
                nome_aluno=dados_atualizacao['nome'], 
                personal_id=personal_id, 
                aluno_id_ignorado=aluno_id
            )

        # Aplica as alterações no objeto
        for campo, valor in dados_atualizacao.items():
            setattr(alunos, campo, valor)

        try:
            await self.db.commit()
        except Exception:
            await self.db.rollback() 
            raise HTTPException(
                status_code=500,
                detail="Erro ao salvar os dados"
            )

        try:
            await self.redis_client.delete(
                f"alunos:personal:{personal_id}:todos",
                f"alunos:personal:{personal_id}:aluno:{alunos.id}"
                )
        except Exception:
            logger.exception("Não foi possível invalidar o cache dos alunos")

        return {"message": "Informações do aluno alteradas com sucesso!"}



    async def deletar_aluno(
        self,
        aluno_id: int,
        access_token: dict
        ) -> dict:
        """Deleta um aluno que o personal cadastrou"""
        personal_id = self.client_utils.obter_personal_id(access_token)

        query = select(Alunos).where(
            Alunos.id == aluno_id,
            Alunos.personal_id == personal_id
        )
        resultado = await self.db.execute(query)
        aluno = resultado.scalar_one_or_none()

        if not aluno:
            raise HTTPException(
                status_code=404,
                detail="Aluno não encontrado"
            )

        try:
            await self.db.delete(aluno)
            await self.db.commit()
        except Exception:
            await self.db.rollback() 
            raise HTTPException(
                status_code=500,
                detail="Erro ao salvar os dados"
            )

        try:
            await self.redis_client.delete(
                f"alunos:personal:{personal_id}:todos",
                f"alunos:personal:{personal_id}:aluno:{aluno_id}"
                )
        except Exception:
            logger.exception("Não foi possível invalidar o cache dos alunos")

        return {'message':f'Aluno deletado: {aluno.nome}'}
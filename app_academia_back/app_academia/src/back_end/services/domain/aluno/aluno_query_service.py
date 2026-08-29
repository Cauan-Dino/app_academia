from back_end.services.infra.sms.telefone_utils import limpar_numero_telefone
from sqlalchemy import select
from fastapi import HTTPException
from back_end.services.infra.database.models import Alunos
from sqlalchemy.ext.asyncio import AsyncSession
from back_end.services.domain.aluno.aluno_utils import PersonalClientUtils
from back_end.services.infra.utils.texto import remover_acentos
import json
from back_end.core.logging.logs_settings import logger
from redis.asyncio import Redis

class AlunoQueryService:
    def __init__(self, db: AsyncSession, redis_client: Redis):
        self.db = db
        self.client_utils = PersonalClientUtils()
        self.redis_client = redis_client


    async def verificar_se_telefone_do_aluno_ja_ta_cadastrado(
        self,
        telefone_aluno: str,
        personal_id: int,
        aluno_id_ignorado: int | None = None
        ) -> str:     
        """
        Verifica se o Personal já tem um Aluno com esse telefone cadastrado.
        Se sim, Retorna um erro.
        Se não, Passa normalmente
        """
        telefone_aluno_formatado = limpar_numero_telefone(telefone_aluno)

        query = select(Alunos).where(
            Alunos.telefone == telefone_aluno_formatado, 
            Alunos.personal_id == personal_id
        )

        if aluno_id_ignorado is not None:
            query = query.where(Alunos.id != aluno_id_ignorado)

        resultado = await self.db.execute(query)

        if resultado.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=409,
                detail='Você já possui um aluno cadastrado com esse telefone.'
            )

        return telefone_aluno_formatado
    


    async def verifica_se_nome_do_aluno_ja_ta_cadastrado(
        self,
        nome_aluno: str,
        personal_id: int,
        aluno_id_ignorado: int | None = None
        ) -> str:
        """
        Verifica se o Personal já tem um Aluno com esse Nome.
        Se sim, Retorna um erro.
        Se não, Passa normalmente
        """

        nome_aluno_validado = self.client_utils.validacao_nome_aluno(nome_aluno)

        query = select(Alunos).where(
            Alunos.nome == nome_aluno_validado, 
            Alunos.personal_id == personal_id
        )

        if aluno_id_ignorado is not None:
            query = query.where(Alunos.id != aluno_id_ignorado)

        resultado = await self.db.execute(query)

        if resultado.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=409,
                detail='Você já possui um aluno cadastrado com esse nome.'
            )

        return nome_aluno_validado

    

    async def buscar_alunos(
        self,
        access_token: dict,
        nome_aluno: str | None = None
        ) -> list[dict]:
        """Busca todos os alunos que o personal tem cadastrado"""
        personal_id = self.client_utils.obter_personal_id(access_token)
        chave_cache = f"alunos:personal:{personal_id}:todos"

        alunos_formatados = None

        try:
            cache = await self.redis_client.get(chave_cache)

            if cache is not None:
                alunos_formatados = json.loads(cache)

        except Exception as erro:
            logger.warning(
                "Não foi possível consultar o cache dos alunos", 
                extra={
                    'tipo_erro': type(erro).__name__
                },
                exc_info=False
            )

        if alunos_formatados is None:
            query = (
                select(Alunos)
                .where(Alunos.personal_id == personal_id)
                .order_by(Alunos.nome)
            )

            resultado = await self.db.execute(query)
            alunos = resultado.scalars().all()
            alunos_formatados = self.client_utils.serializar_alunos(alunos)

            try:
                await self.redis_client.set(
                    chave_cache,
                    json.dumps(alunos_formatados, ensure_ascii=False),
                    ex=900,
                )
            except Exception as erro:
                logger.warning(
                    "Não foi possível salvar os alunos no cache", 
                    extra={
                    'tipo_erro': type(erro).__name__
                    },
                    exc_info=False
                )

        if nome_aluno:
            nome_validado = self.client_utils.validacao_nome_aluno(nome_aluno)
            
            return [
                aluno
                for aluno in alunos_formatados
                if remover_acentos(nome_validado.casefold()) in remover_acentos(aluno["nome"].casefold())
            ]

        return alunos_formatados



    async def buscar_aluno_por_id(
        self,
        aluno_id: int,
        access_token: dict
        ) -> dict:
        """Busca o aluno pelo id"""
        personal_id = self.client_utils.obter_personal_id(access_token)

        chave_redis = f'alunos:personal:{personal_id}:aluno:{aluno_id}'
        resultado_redis = None

        try:
            resultado_redis = await self.redis_client.get(chave_redis)
            if resultado_redis:
                return json.loads(resultado_redis)

        except Exception as erro:
            logger.warning(
                "Não foi possível consultar o cache dos alunos",
                extra={
                    'tipo_erro': type(erro).__name__
                },
                exc_info=False
                )

        query = select(Alunos).where(Alunos.id == aluno_id, Alunos.personal_id == personal_id)
        resultado = await self.db.execute(query)
        aluno = resultado.scalar_one_or_none()

        if not aluno:
            raise HTTPException(
                status_code=404,
                detail='Esse aluno não existe!'
            )

        aluno_formatado = self.client_utils.serializar_aluno(aluno)

        try:
            await self.redis_client.set(
                chave_redis,
                json.dumps(
                    aluno_formatado,
                    ensure_ascii=False
                    ),
                ex=900
            )
        except Exception as erro:
            logger.warning(
                "Não foi possível salvar o aluno no cache",
                extra={
                    'tipo_erro': type(erro).__name__
                }, 
                exc_info=False
                )

        return aluno_formatado
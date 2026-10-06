from back_end.services.infra.database.models import Alunos
from sqlalchemy.ext.asyncio import AsyncSession
from back_end.schemas.cadastrar_aluno import CadastrarAluno, AlterarInformacoesAluno
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from back_end.core.logging.logs_settings import logger
from redis.asyncio import Redis
from back_end.services.domain.aluno.aluno_query_service import AlunoQueryService 
from back_end.services.domain.aluno.aluno_utils import PersonalClientUtils
from back_end.services.infra.redis_service.notificacao_cache import invalidar_cache_notificacoes
from back_end.services.domain.chatbot.whatsapp_service import WhatsappService
from back_end.services.infra.config.settings import settings

class AlunoCommandService:
    def __init__(
        self,
        db: AsyncSession,
        redis_client: Redis,
        whatsapp_service: WhatsappService,
    ):
        self.db = db
        self.redis_client = redis_client
        self.whatsapp_service = whatsapp_service
        self.query_service = AlunoQueryService(db, redis_client)
        self.client_utils = PersonalClientUtils()


    async def _enviar_notificacao_no_telefone_no_whatsapp_do_aluno(
        self,
        telefone: str,
        nome_aluno: str,
        nome_personal: str,
    ) -> bool | None:
        """Diz se o número recebe WhatsApp, enviando o template de boas-vindas.

        Roda antes de gravar o aluno: True = número aceito, False = não recebe
        WhatsApp, None = não foi possível confirmar agora.
        """
        resultado = await self.whatsapp_service.enviar_template(
            telefone=telefone,
            nome_template=settings.WHATSAPP_TEMPLATE_BOAS_VINDAS,
            idioma=settings.WHATSAPP_TEMPLATE_IDIOMA,
            parametros={
                "nome_do_aluno": nome_aluno,
                "nome_do_personal": nome_personal,
            },
        )

        return resultado


    async def cadastrar_aluno(
        self,
        body: CadastrarAluno,
        access_token: dict
        ) -> dict:
        """Função que permite o Personal Cadastrar um aluno"""
        personal_id = self.client_utils.obter_personal_id(access_token)

        body.telefone = await self.query_service.verificar_se_telefone_do_aluno_ja_ta_cadastrado(telefone_aluno=body.telefone, personal_id=personal_id)
        body.nome = await self.query_service.verifica_se_nome_do_aluno_ja_ta_cadastrado(nome_aluno=body.nome, personal_id=personal_id)

        # Tenta enviar uma notificação pro telefone do aluno enviado no payload
        # Se Falhar exibe uma mensagem de erro, se não cadastra
        telefone_verificado = await self._enviar_notificacao_no_telefone_no_whatsapp_do_aluno(
            telefone=body.telefone,
            nome_aluno=body.nome,
            nome_personal=access_token.get("nome", ""),
        )

        if telefone_verificado is False:
            raise HTTPException(
                status_code=400,
                detail="Esse número não recebe WhatsApp. Confira se foi digitado corretamente."
            )

        if telefone_verificado is None:
            mensagem = "Aluno cadastrado. Não foi possível confirmar o número no WhatsApp agora."
        else:
            mensagem = "Aluno cadastrado com sucesso! Enviamos uma mensagem de boas-vindas."

        informacoes_aluno = Alunos(**body.model_dump(), telefone_verificado=telefone_verificado, personal_id=personal_id)
        self.db.add(informacoes_aluno)

        try:
            await self.db.commit()
            
        except IntegrityError:
            await self.db.rollback()
            raise HTTPException(
                status_code=409,
                detail="Já existe um aluno com esse número de telefone."
            )

        except Exception:
            await self.db.rollback()
            raise HTTPException(
                status_code=500,
                detail="Ocorreu um erro ao cadastrar o aluno."
            )

        try:
            await self.redis_client.delete(
                f"alunos:personal:{personal_id}:todos"
                )
        except Exception:
            logger.exception("Não foi possível invalidar o cache dos alunos", exc_info=False)

        return {
            "message": mensagem,
            "telefone_verificado": telefone_verificado,
        }



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


        # Pega apenas os campos que foram enviados no payload, excluindo os que não foram enviados
        dados_atualizacao = body.model_dump(exclude_unset=True)
        if not dados_atualizacao:
            raise HTTPException(
                status_code=400,
                detail="Nenhuma informação foi enviada para alteração.",
            )

        if "telefone" in dados_atualizacao:
            if dados_atualizacao["telefone"] is None:
                raise HTTPException(
                    status_code=400,
                    detail="O telefone não pode ser nulo"
                )

            # O schema já normalizou o número: se é o mesmo que está salvo, não houve troca
            # e não há o que verificar nem reenviar (o app sempre manda o telefone ao editar).
            if dados_atualizacao["telefone"] == alunos.telefone:
                del dados_atualizacao["telefone"]

        if "telefone" in dados_atualizacao:
            dados_atualizacao['telefone'] =await self.query_service.verificar_se_telefone_do_aluno_ja_ta_cadastrado(
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

        if 'telefone' in dados_atualizacao:
            verificado  = await self._enviar_notificacao_no_telefone_no_whatsapp_do_aluno(
                telefone=dados_atualizacao['telefone'],
                nome_aluno=dados_atualizacao.get('nome', alunos.nome),
                nome_personal=access_token.get("nome", ""),
            )
            if verificado is False:
                raise HTTPException(
                    status_code=400,
                    detail="Esse número não recebe WhatsApp. Confira se foi digitado corretamente.",
            )
            alunos.telefone_verificado = verificado

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
        except Exception as erro:
            logger.exception(
                "Não foi possível invalidar o cache dos alunos",
                extra={
                    'tipo_erro': type(erro).__name__
                },
                exc_info=False
                )

        await invalidar_cache_notificacoes(self.redis_client, personal_id)
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
            logger.exception("Não foi possível invalidar o cache dos alunos", exc_info=False)

        await invalidar_cache_notificacoes(self.redis_client, personal_id)
        return {'message':f'Aluno deletado: {aluno.nome}'}

from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Request, HTTPException
import json
from .whatsapp_service import WhatsappService
from .chatbot_opcoes_de_escolha_service import ChatBotOptionsService
from .chatbot_solicitacao_mudanca_aula_service import SolicitacaoReagendamentoAulaService
from .setting import settings
from redis.asyncio import Redis
from back_end.core.logging.logs_settings import logger
from fastapi import Response

class ChatbotConversationService:
    def __init__(
            self, 
            whatzap_service: WhatsappService,
            db: AsyncSession,
            redis_client: Redis,
            chatbot_options_service: ChatBotOptionsService,
            chatbot_solicitacao_mudanca_service: SolicitacaoReagendamentoAulaService,
        ):
        self.whatzap_service = whatzap_service
        self.db = db
        self.redis_client = redis_client
        self.chatbot_options_service = chatbot_options_service
        self.chatbot_solicitacao_mudanca_service = chatbot_solicitacao_mudanca_service


    async def _salvar_redis(
        self,
        telefone: str
    ):
        try:
            # Verifica se ja existe salvo a chave no redis
            chave_redis = f'chatbot:sessao:{telefone}'
            redis_cache = await self.redis_client.get(chave_redis)
            # Salva no redis a chave, indicando q a conversa foi iniciada
            if not redis_cache:
                await self.redis_client.set(
                    chave_redis,
                    'menu',
                    ex=30
                )
            # Renova o expire na conversa, indicando ja foi iniciada
            else:
                await self.redis_client.expire(
                    chave_redis,
                    30
                )
            try:
                logger.info(
                    'Sessão com o chatbot salva no redis'
                )
            except Exception:
                pass
        except Exception:
            logger.error(
                'Erro ao salvar chave de telefone no redis no chatbot.',
                exc_info=False
            )
            raise HTTPException(
                status_code=500,
                detail='Serviço indisponível no momento, tente mais tarde'
            )


    async def main(
        self,
        request: Request,
        assinatura: str | None
    ):  
        """
        Metodo principal que recebe a mensagem do aluno via processar_mensagem
        Responsavel por receber a mensagem e tratar a reposta
        """
        # Pega a mensagem do aluno
        resposta_usuario = await self.whatzap_service.processar_mensagem(
            request=request,
            assinatura=assinatura
        )

        if resposta_usuario is None:
            return Response(status_code=200)

        telefone_aluno = resposta_usuario.get('telefone')
        texto_aluno = resposta_usuario.get('texto')

        # --- Envio de mensagens do bot -----------------------------

        # Verifica se o usuario ja escolheu a opcao 2 (inicia uma lista de perguntas pra reagendar a aula)
        if await self.chatbot_solicitacao_mudanca_service.pega_cache_e_verificar_se_redis_esta_online(telefone_aluno=telefone_aluno):
            await self.chatbot_solicitacao_mudanca_service.solicitar_mudanca(texto_aluno=texto_aluno, telefone_aluno=telefone_aluno)

        # Verifica se o telefone esta salvo no redis (verifica se a conversa ja foi iniciada)
        # Se estiver não manda o menu com escolhas pro usuario escolher se tiver manda 
        elif not await self.redis_client.get(f'chatbot:sessao:{telefone_aluno}'):
            await self._salvar_redis(
                telefone=telefone_aluno
            )
            texto = self.chatbot_options_service.menu()
            await self.whatzap_service.enviar_mensagem_texto(
                    texto=texto,
                    telefone=settings.WHATSAPP_TEST_RECIPIENT
                )


        else:
            if texto_aluno == '1':
                texto = await self.chatbot_options_service.resposta_opcao_1_consultar_aulas(telefone_aluno=telefone_aluno)
                await self.whatzap_service.enviar_mensagem_texto(
                    texto=texto,
                    telefone=settings.WHATSAPP_TEST_RECIPIENT
                )
                
            elif texto_aluno == '2':
                texto = self.chatbot_options_service.resposta_opcao_2_()
                await self.whatzap_service.enviar_mensagem_texto(
                    texto=texto,
                    telefone=settings.WHATSAPP_TEST_RECIPIENT
                )
                # Salva no redis pra indicar que o aluno começou a responder as perguntas pra mudar o horario da aula
                await self.chatbot_solicitacao_mudanca_service.salvar_situacao_de_agendamento_de_aula_no_redis(
                    telefone_aluno=telefone_aluno,
                    sessao= {
                        "aluno_id": "aguardando",
                        "aula_fixa_id": "aguardando",
                        "data_hora_aula_original": "aguardando",
                        "motivo": "aguardando",
                        "nova_data_hora_fim": "aguardando",
                        "nova_data_hora_inicio": "aguardando",
                    }
                )

            elif texto_aluno == '0':
                texto = await self.chatbot_options_service.resposta_opcao_0_(telefone=telefone_aluno)
                await self.whatzap_service.enviar_mensagem_texto(
                    texto=texto,
                    telefone=settings.WHATSAPP_TEST_RECIPIENT
                )
                return 

            elif texto_aluno == 'menu':
                texto = self.chatbot_options_service.menu()
                await self.whatzap_service.enviar_mensagem_texto(
                        texto=texto,
                        telefone=settings.WHATSAPP_TEST_RECIPIENT
                    )

            else:
                await self.whatzap_service.enviar_mensagem_texto(
                texto='Por favor, digite alguma opção válida.',
                telefone=settings.WHATSAPP_TEST_RECIPIENT
            )
                
            await self._salvar_redis(
                telefone=telefone_aluno
            )
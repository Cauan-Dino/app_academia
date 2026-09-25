"""Coordenação do menu e encaminhamento das mensagens para o reagendamento."""

from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Request
from .whatsapp_service import WhatsappService
from .chatbot_opcoes_de_escolha_service import ChatBotOptionsService
from .chatbot_solicitacao_mudanca_aula_service import SolicitacaoReagendamentoAulaService
from .utils_chatbot_service import UtilsChatbotService
from redis.asyncio import Redis
from fastapi import Response

class ChatbotConversationService:
    """Direciona mensagens recebidas conforme a sessão e a opção escolhida."""

    def __init__(
            self, 
            whatzap_service: WhatsappService,
            db: AsyncSession,
            redis_client: Redis,
            chatbot_options_service: ChatBotOptionsService,
            chatbot_solicitacao_mudanca_service: SolicitacaoReagendamentoAulaService,
            utils_chatbot_service: UtilsChatbotService,
        ):
        """Recebe as dependências de envio, consulta, reagendamento e sessão."""
        self.whatzap_service = whatzap_service
        self.db = db
        self.redis_client = redis_client
        self.chatbot_options_service = chatbot_options_service
        self.chatbot_solicitacao_mudanca_service = chatbot_solicitacao_mudanca_service
        self.utils_chatbot_service = utils_chatbot_service


    async def main(
        self,
        request: Request,
        assinatura: str | None
    ) -> Response:  
        """Processa uma mensagem recebida pelo webhook do WhatsApp.

        Retorna HTTP 200 quando o evento não contém uma mensagem de texto.
        Encaminha conversas com reagendamento ativo ao serviço responsável.
        Para as demais conversas, apresenta o menu, processa a opção escolhida
        e renova a sessão do chatbot.

        Raises:
            RedisError: Se ocorrer uma falha ao consultar ou salvar dados no Redis.
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
        sessao_reagendamento = (
            await self.utils_chatbot_service
            .pega_cache_e_verificar_se_redis_esta_online(
                telefone_aluno=telefone_aluno,
            )
        )

        # Usa a sessão que já foi consultada (na opcao [2] )
        if sessao_reagendamento is not None:
            await self.chatbot_solicitacao_mudanca_service.solicitar_mudanca(
                texto_aluno=texto_aluno,
                telefone_aluno=telefone_aluno,
            )

        # verifica se a conversa ja foi iniciada
        # Se estiver não manda o menu com escolhas pro usuario escolher, se tiver manda 
        elif not await self.redis_client.get(f'chatbot:sessao:{telefone_aluno}'):
            await self.utils_chatbot_service._salvar_redis(
                telefone=telefone_aluno
            )
            texto = self.chatbot_options_service.menu()
            await self.whatzap_service.enviar_mensagem_texto(
                    texto=texto,
                    telefone=telefone_aluno
                )


        else:
            if texto_aluno == '1':
                texto = await self.chatbot_options_service.resposta_opcao_1_consultar_aulas(telefone_aluno=telefone_aluno)
                await self.whatzap_service.enviar_mensagem_texto(
                    texto=texto,
                    telefone=telefone_aluno
                )
                
            elif texto_aluno == '2':
                texto = await self.chatbot_options_service.resposta_opcao_2_(telefone_aluno=telefone_aluno)
                await self.whatzap_service.enviar_mensagem_texto(
                    texto=texto,
                    telefone=telefone_aluno
                )
                # Salva no redis pra indicar que o aluno começou a responder as perguntas pra mudar o horario da aula
                await self.utils_chatbot_service.salvar_situacao_de_agendamento_de_aula_no_redis(
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
                    telefone=telefone_aluno
                )
                return Response(status_code=200)

            elif texto_aluno == 'menu':
                texto = self.chatbot_options_service.menu()
                await self.whatzap_service.enviar_mensagem_texto(
                        texto=texto,
                        telefone=telefone_aluno
                    )

            else:
                await self.whatzap_service.enviar_mensagem_texto(
                texto='Por favor, digite alguma opção válida.',
                telefone=telefone_aluno
            )
                
            await self.utils_chatbot_service._salvar_redis(
                telefone=telefone_aluno
            )

        return Response(status_code=200)

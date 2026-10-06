from sqlalchemy.ext.asyncio import AsyncSession
from .enviar_notificaco_service import NotificacaoService
from sqlalchemy import select, and_, func
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from back_end.services.infra.database.models import AulaFixa, ParticipanteAula, Personal, SolicitacaoMudanca, LembreteAula, DiaDaSemana, StatusLembrete, StatusSolicitacao
from back_end.services.domain.chatbot.utils_chatbot_service import (
    FUSO_HORARIO_ACADEMIA,
)
import asyncio
from anyio import move_on_after
from back_end.core.logging.logs_settings import logger
from datetime import datetime, timedelta, timezone

class LembrenteAulaService:
    def __init__(
            self,
            db: AsyncSession,
            notificacao_service: NotificacaoService,
        ):
        self.db = db
        self.notificacao_service = notificacao_service


    async def preparar_lembretes(self) -> list[int]:
        data_local = datetime.now(FUSO_HORARIO_ACADEMIA).date()

        aulas_fixa = await self._buscar_aulas_fixas_nos_proximos_10_minutos()
        # Pega todas as aulas_fixas nos proximos 10 minutos
        dados_aula = [
            (
                aula.id,
                aula.personal_id,
                datetime.combine(
                    data_local, 
                    aula.horario_inicio, 
                    tzinfo=FUSO_HORARIO_ACADEMIA
                ),
                None, # Não veio de um reagendamento
                f'fixa:{aula.id}:{data_local.isoformat()}'
            )
            for aula in aulas_fixa
        ]

        aulas_reagendadas = await self._buscar_aulas_reagendadas_nos_proximos_10_minutos() 

        # Pega todas as aulas reagendadas nos proximos 10 minutos e junta com as aulas_fixas
        dados_aula.extend(
            [
                (
                    solicitacao.aula_fixa_id,
                    solicitacao.personal_id,
                    solicitacao.nova_data_hora_inicio.replace(
                        tzinfo=FUSO_HORARIO_ACADEMIA
                    ),
                    solicitacao.id,
                    f'reagendamento:{solicitacao.id}'
                )
            for solicitacao in aulas_reagendadas 
            ]
        )

        ids = []

        for (
            aula_fixa_id,
            personal_id,
            horario_inicio,
            solicitacao_id,
            chave_ocorrencia,
        ) in dados_aula:
            try:
                inicio_utc = horario_inicio.astimezone(timezone.utc).replace(tzinfo=None)

                lembrente = await self._criar_ou_obter_lembrete(
                    chave_ocorrencia=chave_ocorrencia,
                    personal_id=personal_id,
                    aula_fixa_id=aula_fixa_id,
                    inicio_da_aula=inicio_utc,
                    solicitacao_id=solicitacao_id,
                )

                await self.db.commit()
                ids.append(lembrente.id)
            
            except Exception as erro:
                logger.warning(
                    'Falha ao preparar lembrete',
                    extra={
                        'chave_ocorrencia': chave_ocorrencia,
                        'personal_id': personal_id,
                        'tipo_erro': type(erro).__name__,
                    }
                )
                await self.db.rollback()

        return ids

    

    async def processar_lembrete(self, lembrete_id: int,) -> None:
        try:
            # Se a chave_ocorrencia ja existir o status é colocado em PROCESSADO
            lembrete = await self._reservar_lembrete(
                lembrete_id=lembrete_id,
            )
            
            # Rollback caso o lebrete_id não exista 
            if lembrete is None:
                await self.db.rollback()
                return
                
            lembrete.tentativas += 1
            await self.db.flush()

            try:
                enviado = await asyncio.wait_for(
                        self._enviar_lembrete(
                            personal_id=lembrete.personal_id,
                            chave_ocorrencia=lembrete.chave_ocorrencia,
                    ),
                    timeout=20,
                )

            except SQLAlchemyError:
                # Um erro no banco pode invalidar a transação.
                # O except externo fará rollback.
                raise
            
            except Exception:
                # Falha de envio: registra enquanto ainda temos a trava.
                lembrete.status = StatusLembrete.FALHOU
                await self.db.commit()
                raise

            if enviado:
                await self._registrar_resultado_envio(
                    lembrete=lembrete,
                )
            else:
                lembrete.status = StatusLembrete.CANCELADO

            # Confirma o resultado e libera a trava.
            await self.db.commit()


        except Exception as erro:
            logger.warning(
                "Falha ao processar lembrete",
                extra={
                    "lembrete_id": lembrete_id,
                    "tipo_erro": type(erro).__name__,
                },
                exc_info=False
            )
            await self.db.rollback()
            raise # ← o TaskIQ precisa disto para retentar


        except BaseException:
            # Também desfaz a transação em cancelamentos do Taskiq.
            # A proteção permite concluir o rollback durante o cancelamento.
            with move_on_after(5, shield=True) as scope:
                await self.db.rollback()

            if scope.cancelled_caught:
                logger.warning("Rollback não concluiu em 5s; conexão pode estar inconsistente")

            raise
                            


    async def _buscar_aulas_fixas_nos_proximos_10_minutos(self) -> list[AulaFixa]:
        agora = datetime.now(FUSO_HORARIO_ACADEMIA)
        limite = agora + timedelta(minutes=10)
        dia_da_semana = tuple(DiaDaSemana)[agora.weekday()]

        # No MySQL, combina a data de hoje com o horário da aula.
        inicio_original = func.timestamp(
            agora.date(),
            AulaFixa.horario_inicio,
        )

        # Verifica se aquele participante mudou esta ocorrência.
        tem_reagendamento = (
            select(SolicitacaoMudanca.id)
            .where(
                SolicitacaoMudanca.aula_fixa_id == AulaFixa.id,
                SolicitacaoMudanca.personal_id == AulaFixa.personal_id,
                SolicitacaoMudanca.aluno_id == ParticipanteAula.aluno_id,
                SolicitacaoMudanca.data_hora_aula_original == inicio_original,
                SolicitacaoMudanca.status == StatusSolicitacao.ACEITA,
            )
            .correlate(AulaFixa, ParticipanteAula)
            .exists()
        )

        # Basta existir um participante que permaneça na aula original.
        tem_participante_no_horario_original = (
            select(ParticipanteAula.id)
            .where(
                ParticipanteAula.aula_fixa_id == AulaFixa.id,
                ~tem_reagendamento,
            )
            .correlate(AulaFixa)
            .exists()
        )

        query = (
            select(AulaFixa)
            .join(
                Personal,
                Personal.id == AulaFixa.personal_id,
            )
            .where(
                AulaFixa.dia_da_semana == dia_da_semana,
                AulaFixa.horario_inicio > agora.time(),
                AulaFixa.horario_inicio <= limite.time(),
                Personal.usuario_ativo.is_(True),
                tem_participante_no_horario_original,
            )
        )

        aulas = (await self.db.scalars(query)).all()
        return aulas


    async def _buscar_aulas_reagendadas_nos_proximos_10_minutos(self) -> list[SolicitacaoMudanca]:
        agora = datetime.now(FUSO_HORARIO_ACADEMIA).replace(tzinfo=None)
        limite = agora + timedelta(minutes=10)

        aulas_reagendadas = (
            await self.db.scalars(
                select(SolicitacaoMudanca)
                .join(
                    AulaFixa,
                    and_(
                        AulaFixa.id == SolicitacaoMudanca.aula_fixa_id,
                        AulaFixa.personal_id == SolicitacaoMudanca.personal_id 
                    )
                )
                .join(
                    Personal,
                    Personal.id == SolicitacaoMudanca.personal_id
                )
                .where(
                    SolicitacaoMudanca.nova_data_hora_inicio > agora,
                    SolicitacaoMudanca.nova_data_hora_inicio <= limite,
                    SolicitacaoMudanca.status == StatusSolicitacao.ACEITA,
                    Personal.usuario_ativo.is_(True)
                ) 
            )
        ).all()

        return aulas_reagendadas


    async def _criar_ou_obter_lembrete(
            self,
            chave_ocorrencia: str,
            personal_id: int,
            aula_fixa_id: int,
            inicio_da_aula: datetime,
            solicitacao_id: int | None = None,
        ) -> LembreteAula:
        query = (
            select(LembreteAula)
            .where(
                LembreteAula.personal_id == personal_id,
                LembreteAula.chave_ocorrencia == chave_ocorrencia,
            )
        )
        lembrete = (await self.db.execute(query)).scalar_one_or_none()

        if lembrete is not None:
            return lembrete

        try:
            # Permite desfazer esta inserção sem desfazer
            # toda a transação do chamador.
            async with self.db.begin_nested():
                lembrete = LembreteAula(
                    personal_id=personal_id,
                    aula_fixa_id=aula_fixa_id,
                    solicitacao_id=solicitacao_id,
                    chave_ocorrencia=chave_ocorrencia,
                    inicio_da_aula=inicio_da_aula,
                    programado_para=(
                        inicio_da_aula - timedelta(minutes=10)
                    ),
                    status=StatusLembrete.PENDENTE,
                    tentativas=0,
                )

                self.db.add(lembrete)
                await self.db.flush()

        except IntegrityError as erro:
            # No MySQL, 1062 significa violação de unicidade.
            # Outros erros devem continuar sendo propagados.
            if not erro.orig.args or erro.orig.args[0] != 1062:
                raise

            # Outro worker pode ter criado o mesmo lembrete.
            # A leitura com trava consulta o registro atual no MySQL.
            lembrete = (
                await self.db.execute(
                    query
                    .with_for_update()
                    .execution_options(populate_existing=True) # Atualiza os atributos do objeto já existente na sessão.
                                                               # Útil quando outro worker/processo alterou o mesmo registro no banco.
                )
            ).scalar_one_or_none()

            if lembrete is None:
                raise

        return lembrete


    async def _reservar_lembrete(
        self,
        lembrete_id: int
    ) -> LembreteAula | None:
        query = (
            select(LembreteAula)
            .where(
                LembreteAula.id == lembrete_id
            )
            .with_for_update()
            .execution_options(populate_existing=True) # Atualiza os atributos do objeto já existente na sessão.
                                                        # Útil quando outro worker/processo alterou o mesmo registro no banco.
        )

        lembrete = (
            await self.db.execute(query)
        ).scalar_one_or_none()

        # Impede com que um lembrente que ja estiver sendo PROCESSANDO, ENVIADO ou CANCELADO seja mudado pro status PROCESSANDO
        if (
            lembrete is None
            or lembrete.status not in (
                StatusLembrete.PENDENTE,
                StatusLembrete.FALHOU,
                # Recupera registros presos pela implementação anterior.
                StatusLembrete.PROCESSANDO,
            )
        ):
            return None

        lembrete.status = StatusLembrete.PROCESSANDO

        return lembrete



    async def _enviar_lembrete(
        self,
        personal_id: int,
        chave_ocorrencia: str,
    ) -> bool:
        query = (
            select(
                LembreteAula,
                Personal.push_token,
            )
            .join(
                Personal,
                Personal.id == LembreteAula.personal_id,
            )
            .where(
                LembreteAula.personal_id == personal_id,
                LembreteAula.chave_ocorrencia == chave_ocorrencia,
                Personal.usuario_ativo.is_(True),
            )
            .execution_options(populate_existing=True) # Atualiza os atributos do objeto já existente na sessão.
                                                       # Útil quando outro worker/processo alterou o mesmo registro no banco.
        ) 

        registro = (
            await self.db.execute(query)
        ).one_or_none()

        if registro is None:
            return False

        lembrete, push_token = registro

        if lembrete.status != StatusLembrete.PROCESSANDO:
            return False

        if not push_token:
            logger.info(
                "Lembrete cancelado: personal sem push token",
                extra={"personal_id": personal_id, "chave_ocorrencia": chave_ocorrencia},
            )
            return False

        # O horário está salvo em UTC sem fuso.
        inicio_utc = lembrete.inicio_da_aula.replace(
            tzinfo=timezone.utc,
        )

        # Não enviar um lembrete atrasado de uma aula que já começou.
        if inicio_utc <= datetime.now(timezone.utc):
            return False

        inicio_local = inicio_utc.astimezone(
            FUSO_HORARIO_ACADEMIA,
        )

        await self.notificacao_service.disparar_a_notificaca_pro_celular_do_personal(
            push_token=push_token,
            title="Sua aula começa em breve!",
            body=(
                "Você tem uma aula marcada para "
                f"{inicio_local.strftime('%d/%m às %H:%M')}."
            ),
            data={
                "lembrete_id": lembrete.id,
                "aula_fixa_id": lembrete.aula_fixa_id,
            },
            propagar_erro=True,
        )

        return True


    async def _registrar_resultado_envio(
            self,
            lembrete: LembreteAula
        ) -> None:
        lembrete.status = StatusLembrete.ENVIADO
        lembrete.enviado_em = datetime.now(timezone.utc).replace(tzinfo=None)
        await self.db.flush()


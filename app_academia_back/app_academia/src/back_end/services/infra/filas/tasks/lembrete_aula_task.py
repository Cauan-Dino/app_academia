"""Varredura recuperável e envio individual dos lembretes de aula."""

from back_end.services.domain.notificacao.enviar_notificaco_service import NotificacaoService
from back_end.services.domain.notificacao.lembrete_aula_service import LembrenteAulaService
from back_end.services.infra.database.database import SessionLocal
from back_end.services.infra.filas.taskiq.taskiq_app import broker


@broker.task(
        retry_on_error=True, 
        max_retries=5,
        timeout=45,
)
async def fila_enviar_lembrete(lembrete_id: int):
    async with SessionLocal() as db:
        service = LembrenteAulaService(
                db=db, 
                notificacao_service=NotificacaoService(db=db)
            )

        await service.processar_lembrete(lembrete_id=lembrete_id)

@broker.task(
        schedule=[{'interval': 60}], 
        timeout=50
)
async def fila_processar_lembrete():
    async with SessionLocal() as db:
        service = LembrenteAulaService(
            db=db, 
            notificacao_service=NotificacaoService(db=db)
        )
        ids = await service.preparar_lembretes()
    
    for id in ids:
        await fila_enviar_lembrete.kiq(lembrete_id=id)
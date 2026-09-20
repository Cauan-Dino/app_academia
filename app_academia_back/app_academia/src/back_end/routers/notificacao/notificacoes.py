from datetime import date

from fastapi import APIRouter, Depends, Path, Query, Response, status

from back_end.auth.jwt_token import verificar_access_token
from back_end.schemas.notificacao_schema import NotificacaoResposta, ResponderReagendamento, RespostaReagendamento
from back_end.services.domain.notificacao.dependencies import (
    get_gerenciar_notificacao_service, get_visualizar_notificacao_service,
)
from back_end.services.domain.notificacao.gerenciar_notificacao_service import GerenciarNotificacaoService
from back_end.services.domain.notificacao.visualizar_notificacao_service import VisualizarNotificacaoService

router = APIRouter(prefix="/notificacoes", tags=["Notificações"])


@router.get("", response_model=list[NotificacaoResposta])
async def buscar_notificacoes(
    nome_aluno: str | None = Query(default=None, min_length=1, max_length=100),
    data: date | None = Query(default=None, description="Dia de criação da notificação, no formato YYYY-MM-DD."),
    access_token: dict = Depends(verificar_access_token),
    service: VisualizarNotificacaoService = Depends(get_visualizar_notificacao_service),
):
    return await service.buscar_notificacoes(personal_id=access_token["id"], nome_aluno=nome_aluno, data=data)


@router.delete("/{notificacao_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deletar_notificacao(
    notificacao_id: int = Path(gt=0),
    access_token: dict = Depends(verificar_access_token),
    service: GerenciarNotificacaoService = Depends(get_gerenciar_notificacao_service),
) -> Response:
    await service.deletar_notificacao(personal_id=access_token["id"], notificacao_id=notificacao_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/{notificacao_id}/reagendamento", response_model=RespostaReagendamento)
async def responder_reagendamento(
    body: ResponderReagendamento,
    notificacao_id: int = Path(gt=0),
    access_token: dict = Depends(verificar_access_token),
    service: GerenciarNotificacaoService = Depends(get_gerenciar_notificacao_service),
):
    return await service.responder_reagendamento(
        personal_id=access_token["id"], notificacao_id=notificacao_id, body=body,
    )

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from back_end.services.infra.database.models import StatusSolicitacao

class AtualizarPushToken(BaseModel):
    push_token: str = Field(..., pattern=r'^ExponentPushToken\[.+\]$')


class ReagendamentoNotificacao(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    aluno_id: int
    aula_fixa_id: int
    data_hora_aula_original: datetime
    nova_data_hora_inicio: datetime
    nova_data_hora_fim: datetime
    motivo: str | None
    status: StatusSolicitacao
    expira_em: datetime
    respondida_em: datetime | None


class NotificacaoResposta(BaseModel):
    id: int
    solicitacao_id: int | None
    titulo: str
    mensagem: str
    lida: bool
    criada_em: datetime
    aluno_nome: str | None
    reagendamento: ReagendamentoNotificacao | None
    pode_responder: bool = False


class ResponderReagendamento(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal[StatusSolicitacao.ACEITA, StatusSolicitacao.RECUSADA]


class RespostaReagendamento(BaseModel):
    solicitacao_id: int
    status: Literal[StatusSolicitacao.ACEITA, StatusSolicitacao.RECUSADA]
    respondida_em: datetime
    whatsapp_enviado: bool
    message: str

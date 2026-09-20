from pydantic import BaseModel
from back_end.services.infra.database.models import DiaDaSemana
from datetime import datetime

class SolicitacaoReagendamentoAula(BaseModel):
    dia_da_semana: DiaDaSemana
    nova_data_hora_inicio: datetime
    nova_data_hora_fim: datetime
    motivo: str | None = None
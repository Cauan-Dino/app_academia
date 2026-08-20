from pydantic import BaseModel, Field
from datetime import time
from back_end.services.infra.database.models import DiaDaSemana

class AgendarAula(BaseModel):
    dia_da_semana: DiaDaSemana
    horario_inicio: time
    horario_fim: time
    capacidade_max: int = Field(..., ge=1)


class AlterarAula(BaseModel):
    dia_da_semana: DiaDaSemana | None = None
    horario_inicio: time | None = None
    horario_fim: time | None = None
    capacidade_max: int | None = Field(default=None, ge=1)


class CadastrarAlunoNaAula(BaseModel):
    aluno_id: int = Field(..., gt=0)
    aula_fixa_id: int = Field(..., gt=0)
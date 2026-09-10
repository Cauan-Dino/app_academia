
from typing import TypedDict

class SessaoReagendamento(TypedDict):
    personal_id: int
    aluno_id: int
    aula_fixa_id: int
    data_hora_aula_original: str
    motivo: str
    nova_data_hora_fim: str
    nova_data_hora_inicio: str

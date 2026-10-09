from back_end.services.infra.utils.normalizar_telefone import normalizar_telefone
from pydantic import BaseModel, ConfigDict, Field, field_validator




class CadastrarAluno(BaseModel):
    model_config = ConfigDict(extra='forbid')

    nome: str
    telefone: str = Field(..., min_length=12, max_length=15)
    # O personal viu o aviso de que o número não recebe WhatsApp e quer cadastrar assim mesmo.
    confirmar_telefone_sem_whatsapp: bool = False

    @field_validator('telefone', mode='before')
    @classmethod
    def _normalizar_telefone(
        cls,
        value: str,
    ) -> str:
        return normalizar_telefone(value)


class AlterarInformacoesAluno(BaseModel):
    model_config = ConfigDict(extra='forbid')

    nome: str | None = None
    telefone: str | None = Field(default=None, min_length=12, max_length=15)
    # O personal viu o aviso de que o número não recebe WhatsApp e quer salvar assim mesmo.
    confirmar_telefone_sem_whatsapp: bool = False

    @field_validator('telefone', mode='before')
    @classmethod
    def _normalizar_telefone(
        cls,
        value: str | None
    ) -> str | None:
        if value is None:
            return None
        return normalizar_telefone(value)

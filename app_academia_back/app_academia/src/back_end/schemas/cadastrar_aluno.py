from pydantic import BaseModel, Field, ConfigDict
from pydantic import field_validator
import re

class CadastrarAluno(BaseModel):
    model_config = ConfigDict(extra='forbid')

    nome: str
    telefone: str = Field(..., min_length=10, max_length=15)

    @field_validator('telefone', mode='before')
    @classmethod
    def normalizar_telefone(
        cls,
        value: str,
    ) -> str:
        telefone = re.sub(r'\D', "", value)
        if len(telefone) > 15 or len(telefone) < 10:
            raise ValueError(
                "O telefone deve conter entre 10 e 15 dígitos, "
                "incluindo o código do país e o DDD."
            )
        return telefone

class AlterarInformacoesAluno(BaseModel):
    model_config = ConfigDict(extra='forbid')
    
    nome: str | None = None
    telefone: str | None = Field(default=None, min_length=10, max_length=15)

    @field_validator('telefone', mode='before')
    @classmethod
    def normalizar_telefone(
        cls,
        value: str | None
    ) -> str:
        if value is None:
            return None
        telefone = re.sub(r'\D', "", value)
        if len(telefone) > 15 or len(telefone) < 10:
            raise ValueError(
                "O telefone deve conter entre 10 e 15 dígitos, "
                "incluindo o código do país e o DDD."
            )
        return telefone
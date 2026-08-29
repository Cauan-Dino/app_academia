from pydantic import BaseModel, Field

class CadastrarAluno(BaseModel):
    nome: str
    telefone: str = Field(..., min_length=10, max_length=15)

class AlterarInformacoesAluno(BaseModel):
    nome: str | None = None
    telefone: str | None = Field(default=None, min_length=10, max_length=15)
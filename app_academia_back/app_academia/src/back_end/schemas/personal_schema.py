from pydantic import BaseModel,EmailStr,Field, field_validator
# Schema que cadastra o personal
class CadastroPersonal(BaseModel):
    nome: str
    email: EmailStr
    senha: str = Field(...,min_length=6,max_length=30)
    confirmar_senha: str = Field(...,min_length=6,max_length=30)

    @field_validator('email', mode='before')
    @classmethod
    def normalizar_email(cls, valor):
        if isinstance(valor, str):
            return valor.strip().lower()
        return valor


# Schema logar personal
class LoginPersonal(BaseModel):
    email: EmailStr
    senha: str

    @field_validator('email', mode='before')
    @classmethod
    def normalizar_email(cls, valor):
        if isinstance(valor, str):
            return valor.strip().lower()
        return valor
    
# Schema pra Deletar a conta do Personal
class DeletarContaPersonal(BaseModel):
    senha: str
    confirmar_senha: str


class ReenviarEmailConfirmacao(BaseModel):
    email: EmailStr


class AlterarPersonalNome(BaseModel):
    nome: str

class EnviarEmailRedefinirSenha(BaseModel):
    email: str


class AlterarSenhaPersonal(BaseModel):
    senha: str
    confirmar_senha: str
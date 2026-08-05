from pydantic import BaseModel,EmailStr,Field

# Schema que cadastra o personal
class CadastroPersonal(BaseModel):
    nome: str
    telefone: str = Field(..., min_length=10, max_length=15)
    email: EmailStr
    senha: str = Field(...,min_length=6,max_length=30)
    confirmar_senha: str = Field(...,min_length=6,max_length=30)


# Schema logar personal
class LoginPersonal(BaseModel):
    email: EmailStr
    senha: str

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
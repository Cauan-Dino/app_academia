from pydantic import BaseModel,EmailStr,Field

# Scheme que cadastra o personal
class CadastroPersonal(BaseModel):
    nome: str
    telefone: str = Field(..., min_length=10, max_length=15)
    email: EmailStr
    senha: str = Field(...,min_length=6,max_length=30)
    confirmar_senha: str = Field(...,min_length=6,max_length=30)



# Scheme logar personal
class LoginPersonal(BaseModel):
    email: EmailStr
    senha: str
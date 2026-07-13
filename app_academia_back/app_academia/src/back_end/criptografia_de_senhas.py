from passlib.context import CryptContext

bcrypt_context = CryptContext(
    schemes=['bcrypt'],
    deprecated='auto'
)

# Criptografa
def criptografar_senha(senha: str):
    return bcrypt_context.hash(senha)
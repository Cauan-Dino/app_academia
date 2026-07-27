from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

ph = PasswordHasher()

def criptografar_senha(senha: str):
    return ph.hash(senha)


def verificar_senha(senha: str, hash_banco: str) -> bool:
    try:
        return ph.verify(hash_banco, senha)
    except VerifyMismatchError:
        return False
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
import os

PEPPER = os.getenv('PEPPER')

ph = PasswordHasher(
    time_cost=3,
    memory_cost=19456,
    parallelism=2
    )

def criptografar_senha(senha: str):
    return ph.hash(senha + PEPPER)


def verificar_senha(senha: str, hash_banco: str) -> bool:
    try:
        return ph.verify(hash_banco, senha + PEPPER)
    except VerifyMismatchError:
        return False
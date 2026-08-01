from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
import os
from fastapi import HTTPException

EMAIL_TOKEN_SECRET_KEY = os.getenv("EMAIL_TOKEN_SECRET_KEY")
serializer = URLSafeTimedSerializer(EMAIL_TOKEN_SECRET_KEY)

def _gerar_token(email: str, salt: str) -> str:
    return serializer.dumps(email, salt=salt)


def _validar_token(token: str, salt: str, tempo_expiracao_segundos: int = 1800) -> str:
    try:
        email = serializer.loads(token, salt=salt,max_age=tempo_expiracao_segundos)
        return email
    except (SignatureExpired, BadSignature):
        raise HTTPException(
            status_code=400,
            detail="Link de confirmação inválido ou expirado.",
        )

# ---- Confirmar email ---------------------

def gerar_token_confirmacao_email(email: str) -> str:
    return _gerar_token(email, salt="confirmacao-email")


def validar_token_confirmacao_email(token: str) -> str:
    return _validar_token(token, salt="confirmacao-email", tempo_expiracao_segundos=1800)


# ---- Excluir conta -------------------

def gerar_token_exclusao_conta(email: str) -> str:
    return _gerar_token(email, salt="confirmar-exclusao-conta-email")

def validar_token_exclusao_conta(token: str) -> str:
    return _validar_token(token, salt='confirmar-exclusao-conta-email', tempo_expiracao_segundos=1800)
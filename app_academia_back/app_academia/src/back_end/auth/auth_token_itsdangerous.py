from itsdangerous import URLSafeTimedSerializer
import os
from fastapi import HTTPException

EMAIL_TOKEN_SECRET_KEY = os.getenv("EMAIL_TOKEN_SECRET_KEY")
serializer = URLSafeTimedSerializer(EMAIL_TOKEN_SECRET_KEY)

def gerar_token_confirmacao_email(email: str) -> str:
    return serializer.dumps(email, salt='confirmacao-email')



def validar_token_confirmacao_email(token: str, tempo_expiracao_segundos: int = 3600) -> str:
    try:
        email = serializer.loads(token, salt='confirmacao-email',max_age=tempo_expiracao_segundos)
        return email
    except:
        raise HTTPException(
            status_code=400,
            detail="Link de confirmação inválido ou expirado."
        )
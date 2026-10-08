from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
import hashlib
import hmac
import os
from fastapi import HTTPException

EMAIL_TOKEN_SECRET_KEY = os.getenv("EMAIL_TOKEN_SECRET_KEY")
serializer = URLSafeTimedSerializer(EMAIL_TOKEN_SECRET_KEY)

LINK_INVALIDO = "Link de confirmação inválido ou expirado."

def _gerar_token(email: str, salt: str) -> str:
    return serializer.dumps(email, salt=salt)


def _validar_token(token: str, salt: str, tempo_expiracao_segundos: int = 1800) -> str:
    try:
        email = serializer.loads(token, salt=salt,max_age=tempo_expiracao_segundos)
        return email
    except (SignatureExpired, BadSignature):
        raise HTTPException(
            status_code=400,
            detail=LINK_INVALIDO,
        )

# ---- Confirmar email ---------------------

def impressao_da_senha(senha_hash: str) -> str:
    """Resumo do hash da senha que vai no token: o token é assinado, mas legível."""
    return hashlib.sha256(senha_hash.encode()).hexdigest()[:16]


def gerar_token_confirmacao_email(email: str, senha_hash: str) -> str:
    # A senha entra no token para que refazer o cadastro invalide os links
    # anteriores: cada link só ativa a conta com a senha do cadastro que o gerou.
    return serializer.dumps(
        {"email": email, "senha": impressao_da_senha(senha_hash)},
        salt="confirmacao-email",
    )


def validar_token_confirmacao_email(token: str) -> tuple[str, str]:
    """Devolve o e-mail e a impressão da senha do cadastro que gerou o link."""
    dados = _validar_token(token, salt="confirmacao-email", tempo_expiracao_segundos=1800)
    if not isinstance(dados, dict):
        raise HTTPException(status_code=400, detail=LINK_INVALIDO)
    return dados["email"], dados["senha"]


def token_e_da_senha_atual(impressao: str, senha_hash_atual: str) -> bool:
    """Falso quando o cadastro foi refeito com outra senha depois de gerar o link."""
    return hmac.compare_digest(impressao, impressao_da_senha(senha_hash_atual))


# ---- Excluir conta -------------------

def gerar_token_exclusao_conta(email: str) -> str:
    return _gerar_token(email, salt="confirmar-exclusao-conta-email")

def validar_token_exclusao_conta(token: str) -> str:
    return _validar_token(token, salt='confirmar-exclusao-conta-email', tempo_expiracao_segundos=1800)


# ---- Atualizar Informações Personal -------------------

def gerar_token_alterar_senha(email: str) -> str:
    return _gerar_token(email=email, salt='alterar-senha')

def validar_token_alterar_senha(token: str):
    return _validar_token(token=token, salt='alterar-senha', tempo_expiracao_segundos=1800)
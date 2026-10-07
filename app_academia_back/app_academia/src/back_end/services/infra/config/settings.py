"""Configurações do WhatsApp compartilhadas pelo chatbot e pelas notificações."""

from pydantic import SecretStr, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal

class Settings(BaseSettings):
    """Carrega variáveis de ambiente e do .env, protegendo a exibição dos segredos."""

    model_config = SettingsConfigDict(
        env_file=".env", 
        extra="ignore",
        env_file_encoding='utf-8',
        case_sensitive=True
    )

    WHATSAPP_VERIFY_TOKEN: SecretStr
    WHATSAPP_APP_SECRET: SecretStr
    WHATSAPP_ACCESS_TOKEN: SecretStr

    PHONE_NUMBER_ID: str
    WHATSAPP_API_VERSION: str = "v26.0"

    # Template aprovado na Meta, enviado ao aluno no cadastro.
    WHATSAPP_TEMPLATE_BOAS_VINDAS: str = "boas_vindas_app_academia"
    WHATSAPP_TEMPLATE_IDIOMA: str = "pt_BR"

    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: SecretStr

    # JWT TOKEN
    SECRET_KEY: SecretStr = Field(min_length=32)
    TEMPO_REFRESH_TOKEN: int
    TEMPO_ACCESS_TOKEN: int
    ALGORITHM: Literal["HS256"] = "HS256"

    # CRIPTOGRAFIA DE SENHA
    PEPPER: SecretStr = Field(min_length=16)

    # E-MAIL (Resend): o Railway bloqueia SMTP nos planos Trial e Hobby, então o
    # envio é pela API HTTPS. Sem a chave, a tarefa só registra um erro no log.
    RESEND_API_KEY: SecretStr | None = None
    # Sem domínio verificado no Resend, onboarding@resend.dev só entrega
    # para o e-mail da própria conta do Resend.
    RESEND_FROM: str = "TreinoPro <onboarding@resend.dev>"

    # Endereço público da API, usado para montar os links dos e-mails.
    API_PUBLIC_URL: str = "http://localhost:8000"

settings = Settings()


"""Configurações do WhatsApp compartilhadas pelo chatbot e pelas notificações."""

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

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

    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: SecretStr

settings = Settings()


from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
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
    WHATSAPP_TEST_RECIPIENT: str


settings = Settings()


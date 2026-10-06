"""Testes isolados: banco SQLite em memória e nenhuma chamada a serviços reais."""

import os
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

# Sobrescreve também configurações herdadas; o engine da aplicação não é utilizado.
os.environ.update({
    "SQLALCHEMY_DATABASE_URL": "mysql+aiomysql://test:test@127.0.0.1/test_nao_utilizado",
    # Os mínimos vêm do Settings: 32 caracteres nas chaves, 16 no pepper.
    "SECRET_KEY": "chave-apenas-para-testes-sem-valor-real",
    "EMAIL_TOKEN_SECRET_KEY": "chave-de-email-apenas-para-testes-local",
    "PEPPER": "pepper-apenas-para-testes",
    "TEMPO_REFRESH_TOKEN": "1",
    "TEMPO_ACCESS_TOKEN": "5",
    "ALGORITHM": "HS256",
    "WHATSAPP_VERIFY_TOKEN": "test",
    "WHATSAPP_APP_SECRET": "test",
    "WHATSAPP_ACCESS_TOKEN": "test",
    "PHONE_NUMBER_ID": "test",
    "REDIS_PASSWORD": "test",
    "LOG_FILE_PATH": str(Path(__file__).resolve().parents[2] / "logs" / "testes_notificacoes.log"),
})


@pytest.fixture
def anyio_backend():
    return "asyncio"

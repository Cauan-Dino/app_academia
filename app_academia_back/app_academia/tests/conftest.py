"""Testes isolados: banco SQLite em memória e nenhuma chamada a serviços reais."""

import os
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

# Sobrescreve também configurações herdadas; o engine da aplicação não é utilizado.
os.environ.update({
    "SQLALCHEMY_DATABASE_URL": "mysql+aiomysql://test:test@127.0.0.1/test_nao_utilizado",
    "SECRET_KEY": "chave-apenas-para-testes",
    "TEMPO_REFRESH_TOKEN": "1",
    "TEMPO_ACCESS_TOKEN": "5",
    "ALGORITHM": "HS256",
    "WHATSAPP_VERIFY_TOKEN": "test",
    "WHATSAPP_APP_SECRET": "test",
    "WHATSAPP_ACCESS_TOKEN": "test",
    "PHONE_NUMBER_ID": "test",
    "WHATSAPP_TEST_RECIPIENT": "5500000000000",
    "REDIS_PASSWORD": "test",
    "LOG_FILE_PATH": str(Path(__file__).resolve().parents[2] / "logs" / "testes_notificacoes.log"),
})


@pytest.fixture
def anyio_backend():
    return "asyncio"

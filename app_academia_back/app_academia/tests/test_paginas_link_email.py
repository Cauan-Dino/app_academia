"""Páginas abertas pelos links dos e-mails: confirmar conta e excluir conta."""

from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from back_end.auth.auth_token_itsdangerous import LINK_INVALIDO, gerar_token_exclusao_conta
from back_end.routers.personal.cadastro_personal import router as rotas_cadastro
from back_end.routers.personal.delete_personal import router as rotas_exclusao
from back_end.services.domain.personal.cadastro_personal_service import PersonalCadastroService
from back_end.services.domain.personal.delete_personal_service import DeletePersonalAcountService
from back_end.services.infra.database.database import sessao_db


@pytest.fixture
def cliente():
    app = FastAPI()
    app.include_router(rotas_cadastro)
    app.include_router(rotas_exclusao)
    # Os serviços são substituídos nos testes; o banco nunca é usado.
    app.dependency_overrides[sessao_db] = lambda: None
    return TestClient(app)


def eh_pagina(resposta):
    assert resposta.headers["content-type"].startswith("text/html")
    assert resposta.headers["cache-control"] == "no-store"
    return resposta.text


# --------------------------------------------------------------------------
# confirmar conta
# --------------------------------------------------------------------------


@pytest.mark.parametrize("status, titulo", [
    ("confirmado", "E-mail confirmado"),
    ("ja_confirmado", "Este e-mail já foi confirmado"),
])
def test_confirmacao_mostra_a_pagina_de_sucesso(cliente, monkeypatch, status, titulo):
    monkeypatch.setattr(
        PersonalCadastroService, "confirmar_email", AsyncMock(return_value={"message": "", "status": status}),
    )

    resposta = cliente.get("/confirmar-email", params={"token": "t"})

    assert resposta.status_code == 200
    html = eh_pagina(resposta)
    assert titulo in html
    assert 'href="treinopro://"' in html


@pytest.mark.parametrize("codigo, titulo", [
    (400, "Link expirado"),
    (404, "Conta não encontrada"),
    (500, "Algo deu errado"),
])
def test_erros_da_confirmacao_viram_pagina(cliente, monkeypatch, codigo, titulo):
    monkeypatch.setattr(
        PersonalCadastroService, "confirmar_email",
        AsyncMock(side_effect=HTTPException(status_code=codigo, detail=LINK_INVALIDO)),
    )

    resposta = cliente.get("/confirmar-email", params={"token": "t"})

    assert resposta.status_code == codigo
    assert titulo in eh_pagina(resposta)


# --------------------------------------------------------------------------
# excluir conta
# --------------------------------------------------------------------------


def test_link_de_exclusao_so_pede_confirmacao(cliente, monkeypatch):
    excluir = AsyncMock()
    monkeypatch.setattr(DeletePersonalAcountService, "confirmar_exclusao_de_conta", excluir)
    token = gerar_token_exclusao_conta("ana@example.com")

    resposta = cliente.get("/confirmar-exclusao-conta", params={"token": token})

    assert resposta.status_code == 200
    html = eh_pagina(resposta)
    assert "Excluir sua conta?" in html
    assert 'method="post" action="/confirmar-exclusao-conta"' in html
    assert f'name="token" value="{token}"' in html
    # Abrir o link (como faz o leitor de segurança de alguns e-mails) não exclui nada.
    excluir.assert_not_awaited()


def test_link_de_exclusao_expirado_avisa(cliente):
    resposta = cliente.get("/confirmar-exclusao-conta", params={"token": "invalido"})

    assert resposta.status_code == 400
    html = eh_pagina(resposta)
    assert "Link expirado" in html
    assert "<form" not in html


def test_botao_de_exclusao_exclui_a_conta(cliente, monkeypatch):
    excluir = AsyncMock(return_value={"message": "", "status": "excluida"})
    monkeypatch.setattr(DeletePersonalAcountService, "confirmar_exclusao_de_conta", excluir)

    resposta = cliente.post("/confirmar-exclusao-conta", data={"token": "tok"})

    assert resposta.status_code == 200
    assert "Conta excluída" in eh_pagina(resposta)
    excluir.assert_awaited_once_with("tok")


def test_exclusao_repetida_mostra_conta_nao_encontrada(cliente, monkeypatch):
    # Depois da exclusão o e-mail sai da conta, então o mesmo link não acha mais ninguém.
    monkeypatch.setattr(
        DeletePersonalAcountService, "confirmar_exclusao_de_conta",
        AsyncMock(side_effect=HTTPException(status_code=404, detail="Usuário não encontrado.")),
    )

    resposta = cliente.post("/confirmar-exclusao-conta", data={"token": "tok"})

    assert resposta.status_code == 404
    assert "Conta não encontrada" in eh_pagina(resposta)


def test_token_com_html_nao_e_injetado_na_pagina(cliente, monkeypatch):
    monkeypatch.setattr(
        "back_end.routers.personal.delete_personal.validar_token_exclusao_conta", lambda token: "ana@example.com",
    )

    resposta = cliente.get("/confirmar-exclusao-conta", params={"token": '"><script>alert(1)</script>'})

    assert "<script>" not in resposta.text
    assert "&quot;&gt;&lt;script&gt;" in resposta.text

"""Envio dos e-mails pelo Brevo e links que eles carregam."""

from types import SimpleNamespace
from unittest.mock import AsyncMock
from urllib.parse import unquote

import httpx2
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr

from back_end.auth.auth_token_itsdangerous import validar_token_alterar_senha
from back_end.routers.personal.update_personal import router as rotas_senha
from back_end.schemas.personal_schema import EnviarEmailRedefinirSenha
from back_end.services.infra.config.settings import settings
from back_end.services.infra.email import email_service
from back_end.services.infra.email.email_service import EmailService
from back_end.services.infra.filas.tasks import email_task

pytestmark = pytest.mark.anyio


class RedisMemoria:
    def __init__(self):
        self.chaves = {}
        self.apagadas = []

    async def ttl(self, chave):
        return -2

    async def exists(self, chave):
        return int(chave in self.chaves)

    async def set(self, chave, valor, ex=None):
        self.chaves[chave] = valor

    async def delete(self, chave):
        self.chaves.pop(chave, None)
        self.apagadas.append(chave)


@pytest.fixture
def fila(monkeypatch):
    """Intercepta o que o EmailService coloca na fila, sem Redis nem worker."""
    monkeypatch.setattr(settings, "API_PUBLIC_URL", "https://api.exemplo.com/")
    monkeypatch.setattr(email_service, "redis_client", RedisMemoria())
    kiq = AsyncMock()
    monkeypatch.setattr(email_service, "fila_enviar_email", SimpleNamespace(kiq=kiq))
    return kiq


@pytest.fixture
def brevo(monkeypatch):
    """Substitui o cliente HTTP e o Redis da tarefa; devolve o post e o Redis."""
    monkeypatch.setattr(settings, "BREVO_API_KEY", SecretStr("xkeysib-chave-de-teste"))
    monkeypatch.setattr(settings, "BREVO_FROM_EMAIL", "treinopro@gmail.com")
    monkeypatch.setattr(settings, "BREVO_FROM_NAME", "TreinoPro")
    redis = RedisMemoria()
    monkeypatch.setattr(email_task, "redis_client", redis)
    post = AsyncMock()
    monkeypatch.setattr(email_task, "cliente_http", SimpleNamespace(post=post))
    return post, redis


def resposta_brevo(status, corpo):
    return httpx2.Response(status, json=corpo, request=httpx2.Request("POST", email_task.URL_BREVO))


async def enviar(**campos):
    padrao = dict(
        destinatario="ana@example.com",
        assunto="Confirme seu e-mail",
        texto="Clique no botão abaixo.",
        link="https://api.exemplo.com/confirmar-email?token=abc",
        texto_botao="Confirmar e-mail",
        redis_key="cooldown:email_confirmacao:1",
        chave_idempotencia="chave-unica",
    )
    padrao.update(campos)
    await email_task.fila_enviar_email(**padrao)


# --------------------------------------------------------------------------
# links
# --------------------------------------------------------------------------


async def test_link_de_confirmacao_usa_a_url_publica_e_protege_o_token(fila):
    await EmailService(db=None).enviar_email_confirmacao(token="abc+/=", email="ana@example.com", usuario_id=1)

    link = fila.call_args.kwargs["link"]
    # Sem barra dupla, e os caracteres especiais do token codificados.
    assert link == "https://api.exemplo.com/confirmar-email?token=abc%2B%2F%3D"


async def test_link_de_exclusao_aponta_para_o_endpoint_de_confirmacao(fila):
    await EmailService(db=None).enviar_email_confirmacao_exclusao_conta(
        email="ana@example.com", usuario_id=1, token="tok",
    )

    assert fila.call_args.kwargs["link"] == "https://api.exemplo.com/confirmar-exclusao-conta?token=tok"


async def test_link_de_senha_abre_a_pagina_do_app_com_token_valido(fila):
    await EmailService(db=None).enviar_email_pra_mudar_de_senha_deslogado(
        body=EnviarEmailRedefinirSenha(email="ana@example.com"), usuario_id=7,
    )

    argumentos = fila.call_args.kwargs
    prefixo = "https://api.exemplo.com/abrir-app/redefinir-senha?token="
    assert argumentos["link"].startswith(prefixo)
    # O token do link é aceito pela validação usada no PATCH de nova senha.
    token = unquote(argumentos["link"].removeprefix(prefixo))
    assert validar_token_alterar_senha(token) == "ana@example.com"
    assert argumentos["destinatario"] == "ana@example.com"
    assert argumentos["redis_key"] == "cooldown:email_alterar_senha_deslogado:7"


async def test_cada_email_recebe_uma_chave_de_idempotencia_propria(fila):
    servico = EmailService(db=None)
    await servico.enviar_email_confirmacao(token="a", email="ana@example.com", usuario_id=1)
    await servico.enviar_email_confirmacao(token="b", email="ana@example.com", usuario_id=1)

    primeira, segunda = (chamada.kwargs["chave_idempotencia"] for chamada in fila.call_args_list)
    assert primeira and segunda and primeira != segunda


# --------------------------------------------------------------------------
# tarefa de envio
# --------------------------------------------------------------------------


async def test_envia_pelo_brevo_com_link_no_html_e_no_texto(brevo):
    post, redis = brevo
    post.return_value = resposta_brevo(201, {"messageId": "<202610081200.123@smtp-relay.mailin.fr>"})

    await enviar()

    argumentos = post.call_args.kwargs
    assert post.call_args.args == (email_task.URL_BREVO,)
    assert argumentos["headers"]["api-key"] == "xkeysib-chave-de-teste"
    corpo = argumentos["json"]
    assert corpo["sender"] == {"name": "TreinoPro", "email": "treinopro@gmail.com"}
    assert corpo["to"] == [{"email": "ana@example.com"}]
    assert corpo["subject"] == "Confirme seu e-mail"
    assert 'href="https://api.exemplo.com/confirmar-email?token=abc"' in corpo["htmlContent"]
    assert "https://api.exemplo.com/confirmar-email?token=abc" in corpo["textContent"]
    # Envio bem-sucedido mantém o cooldown.
    assert redis.apagadas == []


async def test_retentativa_de_email_ja_enviado_nao_manda_copia(brevo):
    post, redis = brevo
    post.return_value = resposta_brevo(201, {"messageId": "<1@smtp-relay.mailin.fr>"})

    await enviar()
    await enviar()  # mesma chave de idempotência, como numa retentativa da fila

    assert post.await_count == 1


async def test_emails_com_chaves_diferentes_sao_enviados(brevo):
    post, redis = brevo
    post.return_value = resposta_brevo(201, {"messageId": "<1@smtp-relay.mailin.fr>"})

    await enviar(chave_idempotencia="primeira")
    await enviar(chave_idempotencia="segunda")

    assert post.await_count == 2


async def test_recusa_do_brevo_libera_o_cooldown_e_pede_nova_tentativa(brevo):
    post, redis = brevo
    post.return_value = resposta_brevo(
        400, {"code": "invalid_parameter", "message": "Sender is not valid"},
    )

    with pytest.raises(httpx2.HTTPStatusError):
        await enviar()

    assert redis.apagadas == ["cooldown:email_confirmacao:1"]


async def test_falha_de_rede_libera_o_cooldown_e_pede_nova_tentativa(brevo):
    post, redis = brevo
    post.side_effect = httpx2.ConnectError("sem conexão")

    with pytest.raises(httpx2.ConnectError):
        await enviar()

    assert redis.apagadas == ["cooldown:email_confirmacao:1"]
    # A falha não marca o e-mail como enviado: a retentativa ainda manda.
    assert not await redis.exists("email_enviado:chave-unica")


@pytest.mark.parametrize("campo, valor", [("BREVO_API_KEY", None), ("BREVO_FROM_EMAIL", "")])
async def test_sem_configuracao_do_brevo_nao_envia_nem_tenta_de_novo(brevo, monkeypatch, campo, valor):
    post, redis = brevo
    monkeypatch.setattr(settings, campo, valor)

    await enviar()  # não levanta: tentar de novo não adiantaria

    post.assert_not_awaited()
    assert redis.apagadas == ["cooldown:email_confirmacao:1"]


def test_html_do_email_escapa_o_conteudo():
    html = email_task.montar_html("<script>x</script>", 'https://a.com/?t="x"', "<b>Botão</b>")

    assert "<script>" not in html and "<b>Botão</b>" not in html
    assert "&lt;script&gt;" in html and "&quot;x&quot;" in html


# --------------------------------------------------------------------------
# página que abre o app
# --------------------------------------------------------------------------


@pytest.fixture
def cliente():
    app = FastAPI()
    app.include_router(rotas_senha)
    return TestClient(app)


def test_pagina_de_senha_abre_o_app_com_o_token(cliente):
    resposta = cliente.get("/abrir-app/redefinir-senha", params={"token": "abc.def-ghi"})

    assert resposta.status_code == 200
    assert resposta.headers["content-type"].startswith("text/html")
    assert "treinopro://senha/redefinir-senha?token=abc.def-ghi" in resposta.text
    # A página contém o token: não pode ficar em cache nem vazar pelo Referer.
    assert resposta.headers["cache-control"] == "no-store"
    assert resposta.headers["referrer-policy"] == "no-referrer"


def test_pagina_de_senha_nao_injeta_html_vindo_do_token(cliente):
    malicioso = '"><script>alert(1)</script>'

    resposta = cliente.get("/abrir-app/redefinir-senha", params={"token": malicioso})

    assert resposta.status_code == 200
    assert "<script>" not in resposta.text
    assert "treinopro://senha/redefinir-senha?token=%22%3E%3Cscript%3E" in resposta.text


def test_pagina_de_senha_exige_token(cliente):
    assert cliente.get("/abrir-app/redefinir-senha").status_code == 422

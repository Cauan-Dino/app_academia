"""Formato canônico do telefone: o mesmo valor entrando pela API e pelo webhook."""

import pytest

from back_end.services.infra.utils.normalizar_telefone import (
    normalizar_telefone,
    normalizar_telefone_recebido,
)


@pytest.mark.parametrize(
    "digitado, esperado",
    [
        # O WhatsApp entrega contas brasileiras antigas sem o nono dígito.
        ("559887808745", "5598987808745"),
        # O que o personal digita, em qualquer forma, chega no mesmo lugar.
        ("5598987808745", "5598987808745"),
        ("98987808745", "5598987808745"),
        ("9887808745", "5598987808745"),
        ("(98) 98780-8745", "5598987808745"),
        ("+55 98 98780-8745", "5598987808745"),
    ],
)
def test_todas_as_formas_do_mesmo_celular_convergem(digitado, esperado):
    assert normalizar_telefone(digitado) == esperado


@pytest.mark.parametrize(
    "digitado, esperado",
    [
        ("558533334444", "558533334444"),   # fixo já com DDI
        ("8533334444", "558533334444"),     # fixo sem DDI
    ],
)
def test_fixo_nao_ganha_o_nono_digito(digitado, esperado):
    """Fixo brasileiro começa com 2-5; só celular (6-9) recebe o 9."""
    assert normalizar_telefone(digitado) == esperado


def test_numero_estrangeiro_passa_intacto():
    assert normalizar_telefone("351912345678") == "351912345678"


@pytest.mark.parametrize(
    "valor",
    ["559887808745", "5598987808745", "9887808745", "558533334444", "351912345678"],
)
def test_normalizar_e_idempotente(valor):
    """Normalizar de novo não pode inserir um segundo 9."""
    uma_vez = normalizar_telefone(valor)
    assert normalizar_telefone(uma_vez) == uma_vez


@pytest.mark.parametrize("invalido", ["999990001", "abc", "", "1" * 16])
def test_versao_estrita_recusa_formato_invalido(invalido):
    """Na API o erro precisa subir: é ele que vira 422 para o personal corrigir."""
    with pytest.raises(ValueError):
        normalizar_telefone(invalido)


@pytest.mark.parametrize("invalido", ["999990001", "abc", "", "1" * 16])
def test_versao_do_webhook_nunca_levanta(invalido):
    """Um 'from' inesperado da Meta não pode derrubar o processamento da mensagem."""
    assert isinstance(normalizar_telefone_recebido(invalido), str)


def test_versao_do_webhook_normaliza_o_wa_id():
    """É esta chamada que faz o wa_id casar com o aluno gravado."""
    assert normalizar_telefone_recebido("559887808745") == "5598987808745"

import re

DDI_BRASIL = "55"

def normalizar_telefone(valor: str) -> str:
    """Formato canônico: só dígitos, com DDI e com o nono dígito.

    Levanta ValueError em número fora do formato — é o que o schema
    precisa para virar 422 na API.
    """
    digitos = re.sub(r'\D', "", valor)

    # 10 dígitos = DDD + fixo, 11 = DDD + celular: nos dois casos falta o DDI.
    if len(digitos) in (10, 11):
        digitos = DDI_BRASIL + digitos

    # O WhatsApp entrega celular brasileiro antigo sem o nono dígito:
    # 55 + DDD + 8 dígitos. Celular começa com 6-9; fixo, com 2-5.
    if len(digitos) == 12 and digitos.startswith(DDI_BRASIL) and digitos[4] in "6789":
        digitos = digitos[:4] + "9" + digitos[4:]

    if not 12 <= len(digitos) <= 15:
        raise ValueError(
            "O telefone deve ter 10 ou 11 dígitos (DDD + número) ou "
            "de 12 a 15 dígitos incluindo o código do país."
        )

    return digitos


def normalizar_telefone_recebido(valor: str) -> str:
    """Versão para dado externo: nunca levanta, devolve os dígitos se não souber."""
    try:
        return normalizar_telefone(valor)
    except ValueError:
        return re.sub(r'\D', "", valor)
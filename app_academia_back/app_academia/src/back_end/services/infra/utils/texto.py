import unicodedata

def remover_acentos(texto: str) -> str:
    # Normaliza e remove os caracteres de acento
    texto = unicodedata.normalize('NFD', texto)
    texto = ''.join(c for c in texto if unicodedata.category(c) != 'Mn')
    return texto.casefold()
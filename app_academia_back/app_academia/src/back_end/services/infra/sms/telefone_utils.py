from fastapi import HTTPException

def limpar_numero_telefone(numero: str) -> str:
    numero = numero \
        .replace('-','') \
        .replace('+','') \
        .replace(' ','') \
        .replace('(','') \
        .replace(')','')

    if not numero.isnumeric():
        raise HTTPException(status_code=400, detail='Insira apenas números no número de telefone!')
    return numero
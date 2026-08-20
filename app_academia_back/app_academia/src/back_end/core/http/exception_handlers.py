from fastapi import Request, HTTPException
from back_end.main import app
from back_end.core.logging.logs_settings import logger
from fastapi.responses import JSONResponse
import uuid
from pathlib import Path
from traceback import extract_tb

# Envia logs de qualquer erro que tenha a classe HTTPException sem precisar colocar o finally nas funções 
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    tipo_log = logger.warning if exc.status_code < 500 else logger.error # A variavel tipo_log pega onde está armazenado na memoria o error ou warning e aponta pro msm endereco de memoria
    tipo_log(
        f"Requisição encerrada com HTTPException",
        extra={
            'endpoint': request.url.path,
            'method': request.method,
            'tipo_erro': type(exc).__name__, # Retorna o Nome da Classe da Exceção, ex: "ZeroDivisionError"
            'status_code': exc.status_code
        },
        exc_info=False # Exceção já tratada, ex: (fastapi.exceptions.HTTPException: 401: Senha incorreta)
    )

    return JSONResponse( # Mensagem que retornar pro usuário no front end
        status_code=exc.status_code,
        content={'detail': exc.detail}
    )


# Trata os bugs não previstos e envia Logs (ZeroDivisionError, KeyError, etc)
@app.exception_handler(Exception)
async def global_exception_handler(
    request: Request,
    exc: Exception,
    ) -> JSONResponse:
    error_id = uuid.uuid4().hex

    # Guarda somente arquivo, função e linha.
    # Não inclui mensagem da exceção, SQL ou parâmetros.
    pilha_segura = [
        {
            "arquivo": Path(frame.filename).name,
            "funcao": frame.name,
            "linha": frame.lineno,
        }
        for frame in extract_tb(exc.__traceback__)[-10:]
    ]

    logger.error(
        "Erro interno não tratado",
        extra={
            "error_id": error_id,
            "endpoint": request.url.path,
            "metodo": request.method,
            "tipo_erro": type(exc).__name__,
            "pilha": pilha_segura,
        },
        exc_info=False,
    )

    return JSONResponse(
        status_code=500,
        content={
            "detail": "Erro interno no servidor.",
            "error_id": error_id,
        },
    )

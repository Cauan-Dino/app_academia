from fastapi import Request, HTTPException
from back_end.main import app
from back_end.core.logging.logs_settings import logger
from fastapi.responses import JSONResponse

# Envia logs de qualquer erro que tenha a classe HTTPException sem precisar colocar o finally nas funções 
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    # Erros de cliente (400 até 499) -> WARNING (sem traceback poluindo o log)
    if exc.status_code >= 400 and exc.status_code < 500:
        logger.warning(
            f"Erro de validação na requisição: {exc.detail}",
            extra={
                'endpoint': request.url.path,
                'tipo_erro': type(exc).__name__, # Retorna o Nome da Classe da Exceção, ex: "ZeroDivisionError"
                'mensagem_erro': exc.detail, # Retorna o Nome da Classe da Exceção, ex: "ZeroDivisionError"
                'status_code': exc.status_code
            },
            exc_info=False # Exceção já tratada, ex: (fastapi.exceptions.HTTPException: 401: Senha incorreta)
        )

    # Erros de servidor intencionais (500+) -> ERROR (com traceback)
    else:
        logger.error(
            f"Erro de Servidor HTTPException: {exc.detail}",
            extra={
                'endpoint': request.url.path,
                'tipo_erro': type(exc).__name__, # Retorna o Nome da Classe da Exceção, ex: "ZeroDivisionError"
                'mensagem_erro': exc.detail, # Retorna o Nome da Classe da Exceção, ex: "ZeroDivisionError"
                'status_code': exc.status_code 
            },
            exc_info=True # Grava o Traceback completo para achar a linha do bug
        )

    return JSONResponse( # Mensagem que retornar pro usuário no front end
        status_code=exc.status_code,
        content={'detail': exc.detail}
    )


# Trata os bugs não previstos e envia Logs (ZeroDivisionError, KeyError, etc)
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(
        f'Erro no Servidor',
        extra={
            'endpoint': request.url.path,
            'tipo_erro': type(exc).__name__, # Retorna o Nome da Classe da Exceção, ex: "ZeroDivisionError"
            'erro_mensagem': str(exc) # Mensagem do erro, ex: "NoneType" object has no attribute "nome"
        },
        exc_info=True # Grava o Traceback completo para você achar a linha do bug
    )

    return JSONResponse( # Mensagem que retornar pro usuário no front end
        status_code=500,
        content={"detail": "Erro interno no servidor."}
    )

    
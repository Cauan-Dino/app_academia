from back_end.main import app
from fastapi import Request
import time
from back_end.core.logging.logs_settings import logger

@app.middleware("http")
async def medir_tempo_execucao(request: Request, call_next):
    tempo_inicio = time.time()
    response = await call_next(request) # Executa a função call_next até chegar em um await da função onde ela é pausada no event loop e continua recebendo novas requisições
    tempo_decorrido = time.time() - tempo_inicio
    logger.info(
        "HTTP Request",
        extra={
            'method': request.method,
            'endpoint': request.url.path,
            'status_code': response.status_code, # Pega o response retornado pelo call_next,
            'duration_ms': round(tempo_decorrido * 1000, 2)
        }
    )

    return response # Devolve a resposta final para o cliente 
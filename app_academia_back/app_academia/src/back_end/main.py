from dotenv import load_dotenv
from pathlib import Path

# Carrega as variáveis de ambientes antes de TUDO
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
load_dotenv(dotenv_path=BASE_DIR / ".env")

from fastapi import FastAPI
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from back_end.auth.jwt_token import router as jwt_router
from back_end.services.infra.database.database import criar_tabela
from back_end.services.infra.database.database import engine
from back_end.routers.personal.cadastro_personal import router as cadastro_personal
from back_end.routers.personal.login_personal import router as login_personal
from back_end.routers.personal.delete_personal import router as deletar_conta_personal
from back_end.routers.personal.update_personal import router as update_personal

@asynccontextmanager
async def lifepan(app: FastAPI):
    # roda no STARTUP (uma vez, quando o servidor sobe)
    await criar_tabela()

    yield # a aplicação fica "pausada" aqui, atendendo requisições normalmente

    # tudo DEPOIS do yield roda no SHUTDOWN (uma vez, quando o servidor desliga)
    await engine.dispose()
    # await redis_client.close()  # fecha a conexão Redis de forma organizada
    # await kafka.close()
    # await celery.close() 
    
    # FECHAR A CONEXAO COM O SERVICO VALE PRA TODOS OS SERVICOS | FECHAR A CONEXAO COM O SERVICO VALE PRA TODOS OS SERVICOS
    # FECHAR A CONEXAO COM O SERVICO VALE PRA TODOS OS SERVICOS | FECHAR A CONEXAO COM O SERVICO VALE PRA TODOS OS SERVICOS
    # FECHAR A CONEXAO COM O SERVICO VALE PRA TODOS OS SERVICOS | FECHAR A CONEXAO COM O SERVICO VALE PRA TODOS OS SERVICOS

app = FastAPI(lifespan=lifepan)

from back_end.core.http import exception_handlers   # <-- ADICIONAR
from back_end.core.http import middleware  

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permite requisições de qualquer origem
    allow_methods=["*"],  # Permite todos os métodos (GET, POST, etc.)
    allow_headers=["*"],  # Permite todos os cabeçalhos
)

app.include_router(cadastro_personal)
app.include_router(login_personal)
app.include_router(jwt_router)
app.include_router(deletar_conta_personal)
app.include_router(update_personal)


import os

from dotenv import load_dotenv
from pathlib import Path

# Carrega as variáveis de ambientes antes de TUDO
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
load_dotenv(dotenv_path=BASE_DIR / ".env")

from fastapi import FastAPI
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from back_end.auth.jwt_token import router as jwt_router
from back_end.services.infra.database.database import engine
from back_end.services.infra.filas.taskiq.taskiq_app import broker
from back_end.routers.personal.cadastro_personal import router as cadastro_personal
from back_end.routers.personal.login_personal import router as login_personal
from back_end.routers.personal.delete_personal import router as deletar_conta_personal
from back_end.routers.personal.update_personal import router as update_personal
from back_end.routers.aluno.cadastrar_aluno import router as alunos_router
from back_end.services.infra.redis_service.redis_config import redis_client
from back_end.routers.agendamento.cadastrar_aluno_na_aula import router as cadastrar_aluno_na_sala
from back_end.routers.agendamento.cadastrar_aula import router as cadastrar_aula
from back_end.routers.chatbot.webhook import router as webhook
from back_end.routers.notificacao.salvar_push_token import router as push_token_router 
from back_end.routers.notificacao.notificacoes import router as notificacoes_router

@asynccontextmanager
async def lifepan(app: FastAPI):
    await broker.startup()
    
    yield # a aplicação fica "pausada" aqui, atendendo requisições normalmente

    # tudo DEPOIS do yield roda no SHUTDOWN (uma vez, quando o servidor desliga)
    await engine.dispose()
    await redis_client.close()  # fecha a conexão Redis de forma organizada
    await broker.shutdown()
    
    # FECHAR A CONEXAO COM O SERVICO VALE PRA TODOS OS SERVICOS | FECHAR A CONEXAO COM O SERVICO VALE PRA TODOS OS SERVICOS

app = FastAPI(lifespan=lifepan)

from back_end.core.http import exception_handlers  
from back_end.core.http import middleware  

# Origens liberadas para navegadores, separadas por vírgula no .env (CORS_ORIGINS).
# Vazio bloqueia todo navegador; o app mobile e o webhook não passam por CORS.
origens_permitidas = [
    origem.strip()
    for origem in os.getenv("CORS_ORIGINS", "").split(",")
    if origem.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origens_permitidas,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(cadastro_personal)
app.include_router(login_personal)
app.include_router(jwt_router)
app.include_router(deletar_conta_personal)
app.include_router(update_personal)
app.include_router(alunos_router)
app.include_router(cadastrar_aula)
app.include_router(cadastrar_aluno_na_sala)
app.include_router(webhook)
app.include_router(push_token_router)
app.include_router(notificacoes_router)

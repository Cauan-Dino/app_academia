from dotenv import load_dotenv
from pathlib import Path
import os

# Carrega as variáveis de ambientes antes de TUDO
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
load_dotenv(dotenv_path=BASE_DIR / "env_db_test.env")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from back_end.models import Base
from back_end.database import engine
from back_end.routers.cadastro_usuario import router as cadastro_de_usuarios
from back_end.auth_token.jwt_token import router as jwt_router

Base.metadata.create_all(bind=engine)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permite requisições de qualquer origem
    allow_methods=["*"],  # Permite todos os métodos (GET, POST, etc.)
    allow_headers=["*"],  # Permite todos os cabeçalhos
)

app.include_router(cadastro_de_usuarios)
app.include_router(jwt_router)

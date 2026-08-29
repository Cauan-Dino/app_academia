
from sqlalchemy.orm import DeclarativeBase
import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

SQLALCHEMY_DATABASE_URL = os.getenv('SQLALCHEMY_DATABASE_URL')

engine = create_async_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_size=10, # Mantém até 10 conexões assíncronas fixas no pool
    max_overflow=20, # Permite criar até +20 conexões temporárias em picos (total 30)
    pool_timeout=30, # Tempo máximo (em segundos) que uma requisição aguarda na fila por uma conexão
    pool_recycle=1800, # Recicla conexões antigas a cada 30 minutos (evita conexões caindo por timeout do SO)
    echo=False
)

SessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False) # expire_on_commit=False 

class Base(DeclarativeBase):
    pass

async def criar_tabela():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def sessao_db():
    async with SessionLocal() as db:
        yield db 


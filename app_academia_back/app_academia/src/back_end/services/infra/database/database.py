
from sqlalchemy.orm import DeclarativeBase
import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker


SQLALCHEMY_DATABASE_URL = os.getenv('SQLALCHEMY_DATABASE_URL')

engine = create_async_engine(SQLALCHEMY_DATABASE_URL, echo=True)
SessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False) # expire_on_commit=False 

class Base(DeclarativeBase):
    pass

async def criar_tabela():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def sessao_db():
    async with SessionLocal() as db:
        yield db 


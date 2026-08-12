from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException
from back_end.services.infra.database.models import Personal

async def buscar_usuario_autorizado(
    email: str, 
    db: AsyncSession
    ) -> Personal:
    """
    Busca o usuario via email retornando o objeto de Personal
    Ou Exibindo mensagem de erro caso o email não exista ou não esteja ativo ou verificado
    """
    query = select(Personal).where(Personal.email == email)
    resultado = await db.execute(query)
    usuario = resultado.scalar_one_or_none()

    if usuario is None or not usuario.usuario_ativo or not usuario.email_verificado :
        raise HTTPException(status_code=401, detail="Usuário não autorizado.")

    return usuario
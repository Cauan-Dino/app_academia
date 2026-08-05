from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException
from back_end.services.infra.database.models import Usuario

async def buscar_usuario_autorizado(
    email: str, 
    db: AsyncSession
    ) -> Usuario:
    """
    Busca o usuario via email retornando o objeto de Usuario
    Ou Exibindo mensagem de erro caso o email não exista ou não esteja ativo ou verificado
    """
    query = select(Usuario).where(Usuario.email == email)
    resultado = await db.execute(query)
    usuario = resultado.scalar_one_or_none()

    if usuario is None or not usuario.usuario_ativo or not usuario.email_verificado :
        raise HTTPException(status_code=401, detail="Usuário não autorizado.")

    return usuario
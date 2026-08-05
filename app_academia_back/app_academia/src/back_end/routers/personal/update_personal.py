from fastapi import APIRouter, Depends
from back_end.services.domain.personal.update_personal_service import UpdatePersonalDetailsService
from back_end.auth.jwt_token import verificar_access_token
from back_end.services.infra.database.database import sessao_db
from sqlalchemy.ext.asyncio import AsyncSession
from back_end.schemas.personal_schema import AlterarPersonalNome, AlterarSenhaPersonal, EnviarEmailRedefinirSenha

router = APIRouter(tags=['Atualizar Informações Personal'])


@router.patch('/alterar-nome')
async def alterar_nome_personal(
    body: AlterarPersonalNome,
    aceess_token: dict = Depends(verificar_access_token),
    db: AsyncSession = Depends(sessao_db),
    ):
    service = UpdatePersonalDetailsService(db=db)
    return await service.alterar_nome_personal(body=body, access_token=aceess_token)


@router.post('/enviar-email/redefinir-senha')
async def enviar_email_pra_alterar_senha(
    body: EnviarEmailRedefinirSenha,
    access_token: str = Depends(verificar_access_token),
    db: AsyncSession = Depends(sessao_db)
    ):
    service = UpdatePersonalDetailsService(db=db)
    return await service.verificar_email_e_enviar_mudar_senha(body=body, access_token=access_token)


@router.patch('/alterar-senha')
async def alterar_senha(
    body: AlterarSenhaPersonal,
    db: AsyncSession = Depends(sessao_db)
    ):
    service = UpdatePersonalDetailsService(db=db)
    service.al
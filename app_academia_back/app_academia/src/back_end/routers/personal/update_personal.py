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


# Envia e-mail pra alterar senha Logado
@router.post('/senha/enviar-email-alteracao')
async def enviar_email_pra_alterar_senha(
    body: EnviarEmailRedefinirSenha,
    access_token: str = Depends(verificar_access_token),
    db: AsyncSession = Depends(sessao_db)
    ):
    service = UpdatePersonalDetailsService(db=db)
    return await service.verificar_email_e_enviar_mudar_senha_logado(body=body, access_token=access_token)


# Altera a senha Logado
@router.patch('/senha/alterar-senha')
async def alterar_senha(
    token: str,
    body: AlterarSenhaPersonal,
    db: AsyncSession = Depends(sessao_db)
    ):
    service = UpdatePersonalDetailsService(db=db)
    return await service.alterar_senha_no_link_do_email(token=token, body=body)


# Envia e-mail pra alterar a senha Deslogado
@router.post('/senha/esqueci-senha')
async def enviar_email_esqueci_senha(
    body: EnviarEmailRedefinirSenha,
    db: AsyncSession = Depends(sessao_db)
    ):
    service = UpdatePersonalDetailsService(db=db)
    return await service.verificar_email_e_enviar_mudar_senha_deslogado(body=body)


# Altera a senha Deslogado
@router.patch('/senha/redefinir-senha')
async def redefinir_senha(
    token: str,
    body: AlterarSenhaPersonal,
    db: AsyncSession = Depends(sessao_db)
    ):
    service = UpdatePersonalDetailsService(db=db)
    return await service.alterar_senha_no_link_do_email(token=token, body=body)
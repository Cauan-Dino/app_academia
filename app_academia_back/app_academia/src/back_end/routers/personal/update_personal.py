from html import escape
from urllib.parse import quote
from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from back_end.services.domain.personal.update_personal_service import UpdatePersonalDetailsService
from back_end.auth.jwt_token import verificar_access_token
from back_end.services.infra.database.database import sessao_db
from sqlalchemy.ext.asyncio import AsyncSession
from back_end.schemas.personal_schema import AlterarPersonalNome, AlterarSenhaPersonal, EnviarEmailRedefinirSenha

router = APIRouter(tags=['Atualizar Informações Personal'])

# Igual ao "scheme" do front_end/app.json.
ESQUEMA_APP = "treinopro"

PAGINA_ABRIR_APP = """<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="0; url={link_app}">
<title>TreinoPro</title>
</head>
<body style="font-family: Arial, sans-serif; color: #121815; text-align: center; padding: 48px 24px;">
<h1 style="font-size: 22px;">Redefinir senha</h1>
<p>Toque no botão para abrir o TreinoPro e criar sua nova senha.</p>
<p><a href="{link_app}" style="display: inline-block; background: #B9F227; color: #121815; padding: 14px 24px; border-radius: 10px; font-weight: bold; text-decoration: none;">Abrir o app</a></p>
<p style="font-size: 13px; color: #68726D;">Abra este link no celular em que o TreinoPro está instalado.</p>
</body>
</html>"""


# Página do link do e-mail de senha. O Gmail não aceita links treinopro:// e os
# endpoints de senha são PATCH, então o e-mail aponta para cá (https) e a página
# abre o app, que mostra a tela de nova senha e chama o PATCH com o token.
@router.get('/abrir-app/redefinir-senha', response_class=HTMLResponse, include_in_schema=False)
async def abrir_app_redefinir_senha(token: str) -> HTMLResponse:
    # O token vem da URL: codificado e escapado, não consegue injetar HTML na página.
    link_app = escape(f"{ESQUEMA_APP}://senha/redefinir-senha?token={quote(token, safe='')}")
    return HTMLResponse(
        PAGINA_ABRIR_APP.format(link_app=link_app),
        headers={
            "Cache-Control": "no-store",  # a página contém o token
            "Referrer-Policy": "no-referrer",
        },
    )


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
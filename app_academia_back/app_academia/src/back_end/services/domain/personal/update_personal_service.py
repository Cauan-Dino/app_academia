from sqlalchemy.ext.asyncio import AsyncSession
from back_end.services.infra.database.models import Usuario
from back_end.schemas.personal_schema import AlterarPersonalNome
from sqlalchemy import select
from fastapi import HTTPException
from back_end.schemas.personal_schema import EnviarEmailRedefinirSenha, AlterarSenhaPersonal
from back_end.auth.usuario_auth import buscar_usuario_autorizado
from back_end.services.infra.email.email_service import EmailService
from back_end.auth.auth_token_itsdangerous import validar_token_alterar_senha
from back_end.services.domain.personal.cadastro_personal_service import PersonalCadastroService
from back_end.services.infra.criptografia.criptografia_de_senhas import verificar_senha, criptografar_senha
from back_end.services.infra.redis_service.redis_config import redis_client
from back_end.core.logging.logs_settings import logger

class UpdatePersonalDetailsService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.email_service = EmailService(self.db)
        self.cadatro_personal_service = PersonalCadastroService(self.db)


    async def alterar_nome_personal(
            self,
            body: AlterarPersonalNome,
            access_token: dict
        ) -> dict:
        """Altera o nome do personal no banco de dados"""

        query = select(Usuario).where(Usuario.id == access_token['id'])
        resultado = await self.db.execute(query)
        usuario = resultado.scalar_one_or_none()

        if usuario is None:
            raise HTTPException(
                status_code=401,
                detail="Usuário não autorizado.",
            )

        # Impede mudança de NOME se for IGUAL ao atual
        if usuario.nome == body.nome:
            raise HTTPException(
                status_code=400,
                detail="O Nome não pode ser igual ao atual."
            )

        usuario.nome = body.nome

        try:
            await self.db.commit()
        except Exception:
            await self.db.rollback()
            raise HTTPException(
                status_code=500,
                detail='Ocorreu um erro ao tentar mudar o nome!'
            )

        logger.info('Nome alterado com sucesso', extra={'usuario_id': access_token['id']})
        return {'message':'Nome alterado com sucesso.'}



    async def verificar_email_e_enviar_mudar_senha_logado(
            self,
            body: EnviarEmailRedefinirSenha,
            access_token: dict
        ):
        """
        Envia o e-mail pra mudar de Senha Apenas pro Personal Logado
        Verifica se o email é igual ao da sessao atual do Personal e envia o email via metodo da classe EmailService
        """

        email = access_token['email']

        # Verifica se o email é igual ao do usuário
        if body.email != email:
            raise HTTPException(
                status_code=400,
                detail='E-mail incorreto!'
            )

        await self.email_service.enviar_email_pra_mudar_de_senha_logado(body=body, access_token=access_token)

        return {'message':'E-mail enviado, por favor cheque o seu e-mail.'}



    async def verificar_email_e_enviar_mudar_senha_deslogado(
            self,
            body: EnviarEmailRedefinirSenha
        ) -> dict:
        """
        Envia o e-mail pra mudar de Senha Apenas pro Personal Deslogado
        """

        query = select(Usuario).where(Usuario.email == body.email)
        resultado = await self.db.execute(query)
        usuario = resultado.scalar_one_or_none()

        if not usuario: 
            return {"message": "Se o e-mail estiver cadastrado, enviaremos as instruções para redefinição de senha."}

        await self.email_service.enviar_email_pra_mudar_de_senha_deslogado(body=body, usuario_id=usuario.id)

        return {"message": "Se o e-mail estiver cadastrado, enviaremos as instruções para redefinição de senha."}



    async def alterar_senha_no_link_do_email(
            self,
            token: str,
            body: AlterarSenhaPersonal
        ) -> dict:
        """
        Altera a senha do Personal no Link do Email
        Podendo ser tanto deslogado, como Logado
        """

        email = validar_token_alterar_senha(token=token)

        usuario = await buscar_usuario_autorizado(email=email, db=self.db)

        self.cadatro_personal_service.validar_senha(body.senha, body.confirmar_senha)

        # Valida se a senha é igual a salva no banco de dados
        if verificar_senha(body.senha, usuario.senha):
            raise HTTPException(
                status_code=400,
                detail="A nova senha deve ser diferente da senha atual."    
            )

        usuario.senha = criptografar_senha(senha=body.senha)
        usuario.token_version += 1 # Invalida o access e refresh token

        try:
            await self.db.commit()

        except Exception:
            await self.db.rollback()
            raise HTTPException(
                status_code=500,
                detail='Ocorreu um erro ao tentar mudar a senha!'
            )
        # Deleta o access token no redis
        await redis_client.delete(f'usuario_status:{usuario.email}')

        return {'message':'Senha alterado com sucesso!'}
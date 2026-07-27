from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from back_end.services.infra.sms.telefone_utils import limpar_numero_telefone
from back_end.services.infra.database.models import Usuario
from back_end.schemas.personal_schema import CadastroPersonal
from sqlalchemy import select
from back_end.auth.jwt_token import criar_access_token,criar_refresh_token
from sqlalchemy.exc import IntegrityError
from back_end.services.infra.criptografia.criptografia_de_senhas import criptografar_senha

class PersonalCadastroService:
    def __init__(self, db: AsyncSession):
        self.db = db


    def validar_senha(self, senha: str, confirmar_senha: str):
        if confirmar_senha != senha:
            raise HTTPException(
                status_code=400,
                detail='As senhas precisam ser iguais!'
            )
        
        if len(senha) < 6:
            raise HTTPException(
                status_code=400,
                detail='A senha precisa possuir mais de 6 caracteres!'
            )

        if len(senha) > 30:
            raise HTTPException(
                status_code=400,
                detail='A senha precisa ter menos de 30 caracteres!'
            )



    async def cadastro_personal(self, body: CadastroPersonal) -> dict:
        query_usuario_telefone = select(Usuario).filter(Usuario.telefone == body.telefone) # Verifica se o TELEFONE já está cadastrado
        query_usuario_email = select(Usuario).filter(Usuario.email == body.email) # Verifica se o EMAIL já está cadastrado

        resultado_telefone = await self.db.execute(query_usuario_telefone)
        resultado_email = await self.db.execute(query_usuario_email)

        telefone_do_usuario = resultado_telefone.scalar_one_or_none()
        email_do_usuario = resultado_email.scalar_one_or_none()

        # Verifica se o telefone ou o email já existem
        if (telefone_do_usuario and telefone_do_usuario.usuario_ativo) or \
        (email_do_usuario and email_do_usuario.usuario_ativo):
            raise HTTPException(
                status_code=400,
                detail='Ocorreu um erro ao se cadastrar!'
            )

        usuario = telefone_do_usuario or email_do_usuario

        # Verifica se o usuario EXISTE e esta ATIVO
        if usuario and usuario.usuario_ativo:
            raise HTTPException(
                status_code=400,
                detail='Ocorreu um erro ao se cadastrar!'
            )

        body.telefone = limpar_numero_telefone(numero=body.telefone)
        self.validar_senha(body.senha, body.confirmar_senha)
        senha_criptografada = criptografar_senha(body.senha)

        # Se o usuario EXISTIR e não estiver ATIVO as informações dele são Reinscritas 
        if usuario and not usuario.usuario_ativo:
            # # Converte o body para dict (com a senha já tratada)
            # dados_atualizacao = body.model_dump()
            # dados_atualizacao["senha"] = senha_criptografada

            # # Atualiza todos os atributos dinamicamente no modelo do banco
            # for campo, valor in dados_atualizacao.items():
            #     setattr(usuario, campo, valor)
            usuario.nome = body.nome
            usuario.telefone = body.telefone
            usuario.senha = senha_criptografada
            usuario.email = body.email

        # Se o personal não possuir nenhum cadastro, Ele será CADASTRADO
        else:
            usuario = Usuario(
                nome=body.nome,
                tipo='personal',
                telefone=body.telefone,
                email=body.email,
                senha=senha_criptografada
            )
            self.db.add(usuario)

        try:
            await self.db.commit()
        except IntegrityError:
            await self.db.rollback()
            raise HTTPException(status_code=400, detail='Ocorreu um erro ao se cadastrar!')
        
        await self.db.refresh(usuario)

        refresh_token = await criar_refresh_token(email=body.email,db=self.db) 
        access_token = await criar_access_token(email=body.email,db=self.db) 
        
        return {
            'refresh_token':refresh_token,
            'access_token':access_token,
            'type':'Bearer'
            }



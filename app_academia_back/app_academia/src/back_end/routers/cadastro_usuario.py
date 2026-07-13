from fastapi import APIRouter,Depends,HTTPException,status
from back_end.database import Session,sessao_db
from back_end.models import Usuario,AgendamentoFixo,SolicitacaoMudanca
from back_end.scheme import CadastroPersonal, LoginPersonal
from sqlalchemy.exc import IntegrityError
from sqlalchemy import or_
from back_end.auth_token.jwt_token import criar_refresh_token,criar_access_token
from back_end.criptografia_de_senhas import bcrypt_context,criptografar_senha
from back_end.verifica_se_numero_existe import numero_existe_no_whatsapp,verificar_e_remover_caracteres_numero
from back_end.verificar_se_email_existe import enviar_email_confirmacao

router = APIRouter(tags=['Cadastro do usuario'])

@router.post('/cadastro')
async def cadastro_personal(
    body: CadastroPersonal,
    db: Session = Depends(sessao_db)
    ):
    
    usuario_por_telefone = db.query(Usuario).filter(Usuario.telefone == body.telefone).first() # Verifica se o TELEFONE já está cadastrado
    usuario_por_email = db.query(Usuario).filter(Usuario.email == body.email).first() if body.email else None # Verifica se o EMAIL já está cadastrado

    # Verifica se o telefone ou o email já existem
    if (usuario_por_telefone and usuario_por_telefone.usuario_ativo) or \
       (usuario_por_email and usuario_por_email.usuario_ativo):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Ocorreu um erro ao se cadastrar!'
        )

    usuario = usuario_por_telefone or usuario_por_email

    # Verifica se o usuario EXISTE e esta ATIVO
    if usuario and usuario.usuario_ativo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Ocorreu um erro ao se cadastrar!'
        )


    # Remove todos os caracteres que não sejam numeros e verifica se o telefone inserido possui apenas números
    

    body.telefone = await verificar_e_remover_caracteres_numero(numero=body.telefone)

    # Verifica se o número inserido possui no whatsapp
    
    # if await numero_existe_no_whatsapp(numero_telefone=body.telefone) is False:
    #     raise HTTPException(
    #         status_code=status.HTTP_400_BAD_REQUEST,
    #         detail='Esse número de telefone não existe!'
    #     )


    # ----- Verificações da senha ------------------------

    # Verifica se as senhas são iguais
    if body.confirmar_senha != body.senha:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='As senhas precisam ser iguais!'
        )
    
    # Verifica se a senha possui mais de 6 caracteres
    if len(body.senha) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='A senha precisa possuir mais de 6 caracteres!'
        )

    # Verifica se a senha possui mais de 30 caracteres
    if len(body.senha) > 30:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='A senha precisa ter menos de 30 caracteres!'
        )

    # -----------------------------------------------------

    senha_criptografada = criptografar_senha(body.senha)

    # Verificar se EXISTE mas esta INATIVO
    if usuario and not usuario.usuario_ativo:
        usuario.nome = body.nome
        usuario.telefone = body.telefone
        usuario.senha = senha_criptografada
        usuario.email = body.email

    # Caso o usuario não possua ainda um cadastro
    else:
        usuario = Usuario(
            nome=body.nome,
            tipo='personal',
            telefone=body.telefone,
            email=body.email,
            senha=senha_criptografada
        )
        db.add(usuario)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Ocorreu um erro ao se cadastrar!')
    
    db.refresh(usuario)

    refresh_token = criar_refresh_token(email=body.email,db=db) # Cria o refresh token
    access_token = criar_access_token(email=body.email,db=db) # Cria access token
    
    return {
        'refresh_token':refresh_token,
        'access_token':access_token,
        'type':'Bearer'
        }



# Login do personal
@router.post('/login')
async def login_personal(
    body: LoginPersonal,
    db: Session = Depends(sessao_db)
    ):
    # Verifica se o usuario existe
    usuario = db.query(Usuario).filter(Usuario.email == body.email).first()
    if usuario is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Senha ou email incorretos!'
        )
    
    # Verifica se as senhas coincidem
    if not bcrypt_context.verify(body.senha,usuario.senha):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Senha ou email incorretos!'
        )
    
    refresh_token = criar_refresh_token(email=usuario.email,db=db) # Cria o refresh token
    access_token = criar_access_token(email=usuario.email,db=db) # Cria access token

    return {
        'access_token':access_token,
        'refresh_token':refresh_token,
        'type':'Bearer'
    }

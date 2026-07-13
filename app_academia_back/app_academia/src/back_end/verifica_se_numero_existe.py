import secrets
from fastapi import Depends,APIRouter,HTTPException
from back_end.models import EnvioSMS
from back_end.models import Usuario
from back_end.database import sessao_db,Session
from sqlalchemy import func
from back_end.auth_token.jwt_token import verificar_access_token
from datetime import datetime,timezone,timedelta
import httpx
import os

PHONE_NUMBER_ID = os.getenv('PHONE_NUMBER_ID')
WHATSAPP_TOKEN = os.getenv('WHATSAPP_TOKEN')

router = APIRouter(tags=['Envio do SMS'])

TEMPO_EXPIRACAO_SEGUNDOS = 300
MAX_TENTATIVAS = 5
TEMPO_BLOQUEIO_HORAS = 1

async def gerar_codigo_pro_sms() -> int:
    return secrets.randbelow(900000) + 100000


# Verifica se o código inserido esta válido
async def validar_codigo_usuario(db: Session, usuario_id: int, codigo_digitado: int) -> bool: 
    registro = (
        db.query(EnvioSMS)
        .filter(EnvioSMS.usuario_id == usuario_id)
        .order_by(EnvioSMS.data_criacao.desc())
        .first()
    )

    # Verifica se algum Código foi SOLICITADO
    if not registro:
        raise HTTPException(status_code=400, detail="Nenhum código foi solicitado.")


    # Verifica se o Código ja ta VALIDADO
    if registro.codigo_sms_validado is True:
        raise HTTPException(status_code=400, detail="Este código já foi utilizado ou não existe mais.")

    # Verifica se o total de tentativas passou de 5 na ultima hora
    total_tentativas_ultima_hora = await contar_erros_na_ultima_hora(db=db,usuario_id=usuario_id)
    if total_tentativas_ultima_hora >= MAX_TENTATIVAS:
        raise HTTPException(
            status_code=403,
            detail="Muitas tentativas incorretas recentemente. Tente novamente mais tarde."
        )

    agora = datetime.now(timezone.utc).replace(tzinfo=None)

    # Bloqueia até o usuário de pedir Código por 1 HORA
    if registro.bloqueado_ate and agora < registro.bloqueado_ate:
        tempo_restante = (registro.bloqueado_ate - agora).seconds // 60 
        raise HTTPException(status_code=403, detail=f"Bloqueado. Tente novamente em {tempo_restante} minutos.")

    # Verifica expiração se o SMS está expirado (5 minutos)
    if (agora - registro.data_criacao).total_seconds() >= TEMPO_EXPIRACAO_SEGUNDOS:
        raise HTTPException(status_code=400, detail='Código expirado!')


    # Verifica se o codigo esta certo
    if codigo_digitado != registro.codigo_sms:
        registro.tentativas_erradas += 1
        if registro.tentativas_erradas >= MAX_TENTATIVAS: # Verifica se o máximo de tentativas (5) ultrapassou
            registro.bloqueado_ate = agora + timedelta(hours=TEMPO_BLOQUEIO_HORAS)
        db.commit()
        raise HTTPException(status_code=400, detail="Código incorreto.")

    # Sucesso: invalida o código pra não poder ser reutilizado
    registro.codigo_sms_validado = True  
    registro.tentativas_erradas = 0
    db.commit()

    return True



# Conta quantas vezes o usuário solicitou código na última 1 hora
async def contar_solicitacoes_na_ultima_hora(db: Session, usuario_id: int) -> int:
    uma_hora_atras  = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1)
    
    # Conta quantas solicitações foram enviadas em uma hora
    total = (
        db.query(EnvioSMS)
        .filter(
            EnvioSMS.usuario_id == usuario_id,
            EnvioSMS.data_criacao >= uma_hora_atras
        )
        .count()
    )

    return total



# Conta quantos códigos incorretos o usuário inseriu na última hora
async def contar_erros_na_ultima_hora(db: Session,usuario_id: int) -> int:
    uma_hora_atras = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1)

    resultado = (
        db.query(func.sum(EnvioSMS.tentativas_erradas)) # Conta quantos codigos incorretos foram inseridos na última hora
        .filter(
            EnvioSMS.usuario_id == usuario_id,
            EnvioSMS.data_criacao >= uma_hora_atras
        )
        .scalar()
    )

    return resultado or 0 # Retorna resultado se existir ou 0



# Impede o usuário de solicitar outro codigo no mesmo minuto
async def pode_solicitar_novo_sms(db: Session, usuario_id: int):
    # Pega o último SMS enviado
    ultimo_registro = (
        db.query(EnvioSMS)
        .filter(EnvioSMS.usuario_id == usuario_id)
        .order_by(EnvioSMS.data_criacao.desc())
        .first()
    )

    if ultimo_registro is None:
        return # Nunca pediu antes, libera
    
    agora = datetime.now(timezone.utc).replace(tzinfo=None) 
    segundos_desde_ultimo = (agora - ultimo_registro.data_criacao).total_seconds()
    COOLDOWN_SEGUNDOS = 60

    if segundos_desde_ultimo < COOLDOWN_SEGUNDOS:
        tempo_restante = int(COOLDOWN_SEGUNDOS - segundos_desde_ultimo)
        raise HTTPException(
            status_code=429,
            detail=f"Aguarde {tempo_restante}s para solicitar outro código."
        )



# Verifica se o número colocado existe no whatsapp
async def numero_existe_no_whatsapp(numero_telefone: str) -> bool:
    url = f"https://graph.facebook.com/v21.0/{PHONE_NUMBER_ID}/contacts"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
    payload = {
        'blocking': 'wait',
        'contacts': [numero_telefone],
        'force_check': True
    }
    
    # Faz uma requisição assíncrona http no endpoint da META
    async with httpx.AsyncClient() as client:
        response = await client.post(json=payload,url=url,headers=headers)
        data = response.json()
        
        try:
            return data["contacts"][0]["status"] == "valid" # Retorna True
        except (KeyError, IndexError):
            return False



# Envia o código de 6 digitos pro whatsapp da pessoa
async def enviar_codigo_whatsapp(codigo: int, telefone: str):
    url = f"https://graph.facebook.com/v21.0/{PHONE_NUMBER_ID}/messages"
    
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "messaging_product": "whatsapp",
        "to": telefone,  # formato: 5598999999999 (sem +, com código do país)
        "type": "template",
        "template": {
            "name": "codigo_verificacao",  # nome do template criado e aprovado
            "language": {"code": "pt_BR"},
            "components": [
                {
                    "type": "body",
                    "parameters": [
                        {"type": "text", "text": str(codigo)}
                    ]
                }
            ]
        }
    }



# Tira sinais que possam ter no número de telefone e confirma se é um número
async def verificar_e_remover_caracteres_numero(numero: str):
    numero = numero \
        .replace('-','') \
        .replace('+','') \
        .replace(' ','') \
        .replace('(','') \
        .replace(')','')

    
    if not numero.isnumeric():
        raise HTTPException(
            status_code=400,
            detail='Insira apenas números no número de telefone!'
        )
    
    return numero



# Endpoint que envia o código pro sms do Usuário
@router.post('/enviar-sms')
async def enviar_sms(
    token: Usuario = Depends(verificar_access_token),
    db: Session = Depends(sessao_db)
    ):
    # Pega o código SMS mais recente
    ultimo_registro = (
        db.query(EnvioSMS)
        .filter(EnvioSMS.usuario_id == token.id)
        .order_by(EnvioSMS.data_criacao.desc())
        .first()
    )
    
    agora = datetime.now(timezone.utc).replace(tzinfo=None)
    # Impede gerar código novo enquanto o bloqueio de tentativas erradas estiver ativo
    if ultimo_registro and ultimo_registro.bloqueado_ate and agora < ultimo_registro.bloqueado_ate:
        tempo_restante = (ultimo_registro.bloqueado_ate - agora).seconds // 60
        raise HTTPException(status_code=403, detail=f"Bloqueado. Tente novamente em {tempo_restante} minutos.")

    # Impede gerar código novo se houver mais de 5 erros na última hora
    quantidades_de_erros_na_ultima_hora = await contar_erros_na_ultima_hora(db=db,usuario_id=token.id)
    if quantidades_de_erros_na_ultima_hora >= MAX_TENTATIVAS:
        raise HTTPException(
            status_code=403,
            detail="Muitas tentativas incorretas recentemente. Tente novamente mais tarde."
        )

    await pode_solicitar_novo_sms(db=db,usuario_id=token.id) # cooldown de 60s 

    solicitacoes_na_ultima_hora = await contar_solicitacoes_na_ultima_hora(db=db,usuario_id=token.id)
    # Verifica se a quantidades de solicitações passou de 5
    if solicitacoes_na_ultima_hora >= 5:
        raise HTTPException(
            status_code=429,
            detail='Limite de solicitações atingido. Tente novamente mais tarde.'
        )
    
    codigo_sms = await gerar_codigo_pro_sms()
    
    envio_sms = EnvioSMS(
        usuario_id=token.id,
        telefone=token.telefone,
        codigo_sms=codigo_sms,
    )

    db.add(envio_sms)
    db.commit()
    db.refresh(envio_sms)

    return {"message": "Código enviado com sucesso."}

# Criar scrpit que roda as 3 da manha e apagar registros com mais de 24h ou 7 dias
import secrets
from fastapi import HTTPException
from back_end.services.infra.database.models import EnvioSMS
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select
from datetime import datetime,timezone,timedelta
from back_end.services.infra.sms.whatsapp_service import WhatsAppService


class SmsService:
    TEMPO_EXPIRACAO_SEGUNDOS = 300
    MAX_TENTATIVAS = 5
    TEMPO_BLOQUEIO_HORAS = 1
    COOLDOWN_SEGUNDOS = 60

    def __init__(self, db: AsyncSession):
        self.db = db
        self.whatzapp = WhatsAppService()


    def gerar_codigo_pro_sms(self) -> int:
        return secrets.randbelow(900000) + 100000



    async def validar_codigo_usuario(self, usuario_id: int, codigo_digitado: int) -> bool: 
        query = (
            select(EnvioSMS)
            .filter(EnvioSMS.usuario_id == usuario_id)
            .order_by(EnvioSMS.data_criacao.desc())
        )

        registro = await self.db.execute(query)
        envio = registro.scalar_one_or_none()

        # Verifica se algum Código foi SOLICITADO
        if not envio:
            raise HTTPException(status_code=400, detail="Nenhum código foi solicitado.")

        if envio.codigo_sms_validado is True:
            raise HTTPException(status_code=400, detail="Este código já foi utilizado ou não existe mais.")

        # Verifica se o total de tentativas passou de 5 na ultima hora
        total_tentativas_ultima_hora = self.contar_erros_na_ultima_hora(db=self.db,usuario_id=usuario_id)
        if total_tentativas_ultima_hora >= self.MAX_TENTATIVAS:
            raise HTTPException(
                status_code=403,
                detail="Muitas tentativas incorretas recentemente. Tente novamente mais tarde."
            )

        agora = datetime.now(timezone.utc).replace(tzinfo=None)

        # Bloqueia até o usuário de pedir Código por 1 HORA
        if envio.bloqueado_ate and agora < envio.bloqueado_ate:
            tempo_restante = (envio.bloqueado_ate - agora).seconds // 60 
            raise HTTPException(status_code=403, detail=f"Bloqueado. Tente novamente em {tempo_restante} minutos.")

        # Verifica expiração se o SMS está expirado (5 minutos)
        if (agora - envio.data_criacao).total_seconds() >= self.TEMPO_EXPIRACAO_SEGUNDOS:
            raise HTTPException(status_code=400, detail='Código expirado!')


        # Verifica se o codigo esta certo
        if codigo_digitado != envio.codigo_sms:
            envio.tentativas_erradas += 1
            if envio.tentativas_erradas >= self.MAX_TENTATIVAS: # Verifica se o máximo de tentativas (5) ultrapassou
                envio.bloqueado_ate = agora + timedelta(hours=self.TEMPO_BLOQUEIO_HORAS)
            await self.db.commit()
            await self.db.refresh(envio)
            raise HTTPException(status_code=400, detail="Código incorreto.")

        # Sucesso: invalida o código pra não poder ser reutilizado
        envio.codigo_sms_validado = True  
        envio.tentativas_erradas = 0

        await self.db.commit()
        await self.db.refresh(envio)

        return True



    async def pode_solicitar_novo_sms(self, usuario_id: int):
        # Pega o último SMS enviado
        query = (
            select(EnvioSMS)
            .filter(EnvioSMS.usuario_id == usuario_id)
            .order_by(EnvioSMS.data_criacao.desc())
        )
        resultado = await self.db.execute(query)
        ultimo_envio = resultado.scalar_one_or_none()

        if ultimo_envio is None:
            return # Nunca pediu antes, libera
        
        agora = datetime.now(timezone.utc).replace(tzinfo=None) 
        segundos_desde_ultimo = (agora - ultimo_envio.data_criacao).total_seconds()
        COOLDOWN_SEGUNDOS = 60

        if segundos_desde_ultimo < COOLDOWN_SEGUNDOS:
            tempo_restante = int(COOLDOWN_SEGUNDOS - segundos_desde_ultimo)
            raise HTTPException(
                status_code=429,
                detail=f"Aguarde {tempo_restante}s para solicitar outro código."
            )



    async def contar_erros_na_ultima_hora(self, usuario_id: int) -> int:
        uma_hora_atras = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1)

        query = (
            select(EnvioSMS)
            .func.sum(EnvioSMS.tentativas_erradas) # Conta quantos codigos incorretos foram inseridos na última hora
            .filter(
                EnvioSMS.usuario_id == usuario_id,
                EnvioSMS.data_criacao >= uma_hora_atras
            )
        )
        resultado = await self.db.execute(query)
        quant_codigos_errados = resultado.scalar_one_or_none() or 0 # Retorna o resultado da query se EXISTIR ou 0

        return quant_codigos_errados



# CRIAR UM DECORETOR PRA IMPLEMENTAR SISTEMA DE LOGS
# CRIAR UM DECORETOR PRA IMPLEMENTAR SISTEMA DE LOGS
# CRIAR UM DECORETOR PRA IMPLEMENTAR SISTEMA DE LOGS
# CRIAR UM DECORETOR PRA IMPLEMENTAR SISTEMA DE LOGS
# CRIAR UM DECORETOR PRA IMPLEMENTAR SISTEMA DE LOGS
# CRIAR UM DECORETOR PRA IMPLEMENTAR SISTEMA DE LOGS
# CRIAR UM DECORETOR PRA IMPLEMENTAR SISTEMA DE LOGS
# CRIAR UM DECORETOR PRA IMPLEMENTAR SISTEMA DE LOGS
# CRIAR UM DECORETOR PRA IMPLEMENTAR SISTEMA DE LOGS
# CRIAR UM DECORETOR PRA IMPLEMENTAR SISTEMA DE LOGS
# CRIAR UM DECORETOR PRA IMPLEMENTAR SISTEMA DE LOGS
# CRIAR UM DECORETOR PRA IMPLEMENTAR SISTEMA DE LOGS
# CRIAR UM DECORETOR PRA IMPLEMENTAR SISTEMA DE LOGS
# CRIAR UM DECORETOR PRA IMPLEMENTAR SISTEMA DE LOGS
# CRIAR UM DECORETOR PRA IMPLEMENTAR SISTEMA DE LOGS
# CRIAR UM DECORETOR PRA IMPLEMENTAR SISTEMA DE LOGS
# CRIAR UM DECORETOR PRA IMPLEMENTAR SISTEMA DE LOGS
# CRIAR UM DECORETOR PRA IMPLEMENTAR SISTEMA DE LOGS
# CRIAR UM DECORETOR PRA IMPLEMENTAR SISTEMA DE LOGS

    async def contar_solicitacoes_na_ultima_hora(self, usuario_id: int) -> int:
        uma_hora_atras  = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1)
        
        # Conta quantas solicitações foram enviadas em uma hora
        query = (
            select(func.count(EnvioSMS.usuario_id))
            .filter(
                EnvioSMS.usuario_id == usuario_id,
                EnvioSMS.data_criacao >= uma_hora_atras
            )
        )

        resultado = await self.db.execute(query)
        quant_solicitacoes_enviadas = resultado.scalar()

        return quant_solicitacoes_enviadas


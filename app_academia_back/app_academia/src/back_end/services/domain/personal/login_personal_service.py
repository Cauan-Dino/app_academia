from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, Request
from back_end.services.infra.database.models import Personal
from back_end.schemas.personal_schema import LoginPersonal
from sqlalchemy import select
from back_end.auth.jwt_token import criar_access_token, criar_refresh_token
from back_end.services.infra.criptografia.criptografia_de_senhas import verificar_senha
from back_end.core.logging.logs_settings import logger
from redis.asyncio import Redis
from fastapi.concurrency import run_in_threadpool


HASH_FALSO = '$argon2id$v=19$m=19456,t=3,p=2$hRaBzow8isL6HQZ5WARY0w$fm5xkLOaknkgIHggqgrhp+SjrrZFCHHNdhwDAlYyR/g'


class PersonalLoginService:
    def __init__(self, db: AsyncSession, redis_client: Redis):
        self.db = db
        self.redis_client = redis_client


    async def login_personal(self, body: LoginPersonal, request: Request) -> dict:
        ip = request.client.host if request.client else 'desconhecido' # Caso o ip vem None
        email = body.email

        await self._verificar_cooldown_em_tentativas_de_login(ip=ip, email=email)

        # Verifica se o usuario EXISTE e está ATIVO
        query = select(Personal).where(Personal.email == email)
        resultado = await self.db.execute(query)
        usuario = resultado.scalar_one_or_none()

        hash_alvo  = usuario.senha if usuario else HASH_FALSO 
        senha_ok = await run_in_threadpool(verificar_senha, body.senha, hash_alvo)
        
        if usuario is None or not senha_ok:
            await self._adicionar_cooldown_pra_tentativas_de_login_falhas(ip=ip, email=email)
            raise HTTPException(status_code=401, detail='Senha ou email incorretos!')
        
        # Impede o usuario de entrar se o email NÃO estiver VERIFICADO
        if not usuario.usuario_ativo or not usuario.email_verificado:
            raise HTTPException(status_code=403, detail="Confirme seu e-mail antes de entrar.")
        
        access_token = await criar_access_token(email=usuario.email, token_version=usuario.token_version)
        refresh_token = await criar_refresh_token(email=usuario.email, token_version=usuario.token_version)

        logger.info('Login personal realizado', extra={'usuario_id': usuario.id})

        await self._limpar_contador_email(email=email, ip=ip)

        return {
            'access_token':access_token,
            'refresh_token':refresh_token,
            'type':'Bearer'
        }


    async def _verificar_cooldown_em_tentativas_de_login(self, ip: str, email: str) -> None:
        for chave, tentativas_limite, _ in self._regras_de_cooldown(email=email, ip=ip):
            valor = await self.redis_client.get(chave)
            tentativas = int(valor) if valor is not None else 0
            
            if tentativas >= tentativas_limite:
                logger.warning(
                    'Muitas tentativas de login realizadas',
                    extra={
                        'ip': ip,
                        'email': email,
                        'chave': chave,
                    },
                    exc_info=False
                )
                raise HTTPException(
                    status_code=429,
                    detail="Muitas tentativas. Aguarde alguns minutos."
                )

    
    def _regras_de_cooldown(self, email: str, ip: str) -> list[tuple[str, int, int]]:
        return [
            # (chave, limite de falhas, tempo de cooldown em segundos)
            (f"falhas:email_ip:{email}:{ip}", 5, 60),
            (f"falhas:email:{email}", 50, 3600),
            (f"falhas:ip:{ip}", 30, 3600),
        ]

        
    async def _adicionar_cooldown_pra_tentativas_de_login_falhas(
            self, 
            ip: str,
            email: str,
        ) -> None:
        for chave, _, cooldown in self._regras_de_cooldown(email=email, ip=ip):
            await self._adicionar_numero_de_tentativas_no_redis(chave_redis=chave, tempo_cooldown=cooldown)


    async def _adicionar_numero_de_tentativas_no_redis(
        self,
        chave_redis: str,
        tempo_cooldown: int = 60,
    ) -> None:
        async with self.redis_client.pipeline(transaction=True) as pipe:
            pipe.incr(chave_redis)
            pipe.expire(chave_redis, tempo_cooldown)
            await pipe.execute()


    async def _limpar_contador_email(self, email: str, ip: str) -> None:
        chave_email_ip, _, _ = self._regras_de_cooldown(email=email, ip=ip)[0]
        await self.redis_client.delete(chave_email_ip)
            
            

# usuario erra senha 5 vezes
# Usuario pega cooldown de 60 s
# Tenta fazer login enquanto ta no cooldown = eh bloqueado
# Erra mais 5 vezes dnv bloqueado 120s
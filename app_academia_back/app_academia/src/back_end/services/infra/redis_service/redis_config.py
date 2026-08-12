import redis.asyncio as redis
import os

REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))

redis_pool = redis.BlockingConnectionPool(
    host=REDIS_HOST, 
    port=REDIS_PORT, 
    db=0, 
    decode_responses=True,       # Retorna strings (str) diretamente em vez de bytes (b'valor')
    max_connections=30,         # Limite total de conexões no pool (equivalente a pool_size + max_overflow)
    timeout=30.0,               # Tempo maximo (em seg) esperando uma conexão ficar livre (equivalente ao pool_timeout)
    socket_timeout=5.0,         # Timeout para execução de leitura e escrita de comandos
    socket_connect_timeout=5.0, # Timeout maximo para estabelecer a conexão inicial TCP
    health_check_interval=30,   # Executa PING em conexões ociosas a cada 30s para evitar conexões mortas (equivalente ao pool_recycle)
)

redis_client = redis.Redis(connection_pool=redis_pool)

def get_redis() -> redis.Redis:
    return redis_client 

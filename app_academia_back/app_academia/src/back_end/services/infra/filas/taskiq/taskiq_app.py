from taskiq import SmartRetryMiddleware, TaskiqScheduler
from taskiq.schedule_sources import LabelScheduleSource
from taskiq_redis import RedisStreamBroker, ListRedisScheduleSource

from back_end.services.infra.config.settings import settings

redis_url = f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/0"
redis_password = settings.REDIS_PASSWORD.get_secret_value()

schedule_source = ListRedisScheduleSource(
    url=redis_url,
    password=redis_password,
    prefix="taskiq:retries",
)

broker = RedisStreamBroker(
    url=redis_url,
    queue_name="my_queue",
    # Inclui mensagens publicadas antes da primeira inicialização dos workers.
    consumer_id="0",
    # Recupera mensagens de processos mortos antes de a aula começar (em ms).
    idle_timeout=60_000,
    # A trava do XAUTOCLAIM também precisa expirar se seu dono morrer.
    unacknowledged_lock_timeout=10,
    unacknowledged_batch_size=1,
    xread_count=1,
    max_connection_pool_size=10,
    password=redis_password,
).with_middlewares(
    SmartRetryMiddleware(
        default_retry_count=3, # tenta até 3 vezes
        default_retry_label=False, # cada task precisa habilitar retry explicitamente
        default_delay=5, # espera 5s antes de tentar de novo,
        use_delay_exponent=True, # 5s, 10s, 20s... (backoff exponencial)
        use_jitter=True, # adiciona aleatoriedade no tempo de enviar novamente, ex: 4.2s a 6.1s, evita que várias tasks retentem no mesmo instante
        schedule_source=schedule_source,
    )
)

scheduler = TaskiqScheduler(
    broker=broker,
    sources=[schedule_source, LabelScheduleSource(broker)],
)

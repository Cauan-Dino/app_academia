import logging.config
import yaml
from elasticsearch import AsyncElasticsearch
import os
from datetime import datetime

ES_HOST = os.getenv('ES_HOST', 'localhost')
ES_PORT = os.getenv('ES_PORT', '9200')

# Conecta com o elasticsearch
es_client = AsyncElasticsearch(hosts=[f'http://{ES_HOST}:{ES_PORT}'])

# Pega o caminho absoluto onde esta logs
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Junta o caminho absoluto com o logging.yaml
YAML = os.path.join(BASE_DIR, 'logging.yaml')

with open(YAML, 'r') as f: # Lê o arquivo logging.yaml
    config = yaml.safe_load(f) # Transforma o conteúdo no logging.yaml em dict
    log_path = os.getenv('LOG_FILE_PATH', os.path.join(BASE_DIR, 'logs', 'app.log'))
    config['handlers']['file']['filename'] = log_path

    os.makedirs(os.path.dirname(log_path), exist_ok=True) # Garante que a pasta exista

    logging.config.dictConfig(config)

logger = logging.getLogger(__name__) # Defini o nome dos logs. Nesse caso os nomes serão os nomes dos arquivos 

logger.info(    
    'log',
    extra={
        'endpoint':'/',
        'origem': 'etc'
    }
)
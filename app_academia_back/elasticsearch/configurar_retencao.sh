#!/bin/sh
# Configura a retenção dos logs no Elasticsearch: os índices diários
# app-academia-logs-AAAA.MM.DD são apagados 30 dias depois de criados.
# Roda a cada "docker compose up" (serviço elasticsearch_setup); é seguro
# repetir, porque o PUT apenas sobrescreve a configuração existente.
set -e

ES="http://elasticsearch:9200"

echo "Criando a política de retenção (30 dias)..."
curl -sS --fail -X PUT "$ES/_ilm/policy/app-academia-logs-retencao" \
  -H 'Content-Type: application/json' \
  -d '{
    "policy": {
      "phases": {
        "hot": { "actions": {} },
        "delete": { "min_age": "30d", "actions": { "delete": {} } }
      }
    }
  }'
echo

echo "Aplicando a política aos índices diários de log..."
curl -sS --fail -X PUT "$ES/_index_template/app-academia-logs" \
  -H 'Content-Type: application/json' \
  -d '{
    "index_patterns": ["app-academia-logs-*"],
    "template": {
      "settings": {
        "index.lifecycle.name": "app-academia-logs-retencao",
        "number_of_replicas": 0
      }
    }
  }'
echo
echo "Retenção configurada."

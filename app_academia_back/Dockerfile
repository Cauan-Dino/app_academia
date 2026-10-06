FROM python:3.13-slim

WORKDIR /app

RUN pip install --no-cache-dir poetry

COPY app_academia/src/back_end/poetry.lock app_academia/src/back_end/pyproject.toml ./

RUN poetry config virtualenvs.create false \
    && poetry install --no-root --no-interaction --no-ansi

COPY app_academia/src/back_end/ ./back_end/

# Usuário sem privilégios: precisa vir DEPOIS dos RUN que gravam em /usr/local.
RUN useradd --create-home --uid 1000 appuser \
    && mkdir -p /logs \
    && chown -R appuser:appuser /app /logs

USER appuser

ENV PYTHONPATH=/app
# O "poetry config" acima vale só para o root; sem isto, o "poetry run"
# (ex.: alembic) criaria um venv vazio ao rodar como appuser.
ENV POETRY_VIRTUALENVS_CREATE=false

EXPOSE 8000

CMD ["uvicorn","back_end.main:app","--host","0.0.0.0","--port","8000","--proxy-headers","--forwarded-allow-ips=*"]
FROM python:3.13-slim

WORKDIR /app

RUN pip install --no-cache-dir poetry

COPY app_academia/src/back_end/poetry.lock app_academia/src/back_end/pyproject.toml ./

RUN poetry config virtualenvs.create false \
    && poetry install --no-root --no-interaction --no-ansi

COPY app_academia/src/back_end/ ./back_end/

ENV PYTHONPATH=/app

EXPOSE 8000

CMD ["poetry","run","uvicorn","back_end.main:app","--host","0.0.0.0","--port","8000"]
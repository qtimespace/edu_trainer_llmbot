# API тренажёра: FastAPI + миграции при старте. Песочницы создаёт через /var/run/docker.sock.
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
RUN pip install --no-cache-dir uv==0.12.18
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY packages ./packages
COPY apps ./apps
COPY infra/migrations ./infra/migrations
COPY alembic.ini ./
ENV PYTHONPATH=/app/packages:/app PATH=/app/.venv/bin:$PATH
EXPOSE 8000
# --proxy-headers: настоящий IP ученика от Caddy (ограничение попыток входа); наружу API не опубликован
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn apps.api.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*' --timeout-keep-alive 75"]

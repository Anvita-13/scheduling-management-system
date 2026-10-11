# syntax=docker/dockerfile:1
FROM python:3.12-slim

# PYTHONUNBUFFERED: so `docker compose logs` shows output immediately, not only on buffer flush.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install dependencies first so this layer is reused whenever only application code changes.
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
RUN chmod +x docker-entrypoint.sh

EXPOSE 8000

# Used by `depends_on: condition: service_healthy` (the frontend waits for this) and by `docker ps`.
HEALTHCHECK --interval=10s --timeout=5s --retries=10 --start-period=20s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health', timeout=3)" || exit 1

ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

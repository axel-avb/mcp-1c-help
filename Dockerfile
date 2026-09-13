FROM python:3.11-slim

WORKDIR /app

# p7zip нужен для извлечения .hbk архивов (только для индексации)
RUN apt-get update \
    && apt-get install -y --no-install-recommends p7zip-full \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY scripts/ ./scripts/

# HBK-архивы справки (~74 МБ) вшиваются в образ: daemon не видит хостовые
# bind-пути, поэтому volume для /app/data мёртв, данные живут в образе.
COPY data/hbk/ /app/data/hbk/

ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

CMD ["python", "-m", "src.server"]

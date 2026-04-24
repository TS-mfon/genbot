# Multi-stage production Dockerfile for GenBot
# Includes Node.js to run the genlayer CLI
FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt pyproject.toml README.md ./
COPY bot ./bot
RUN pip install --user --no-cache-dir --no-warn-script-location -r requirements.txt \
    && pip install --user --no-cache-dir --no-warn-script-location setuptools wheel \
    && pip install --user --no-cache-dir --no-warn-script-location --no-build-isolation .

FROM python:3.11-slim

WORKDIR /app

# Install Node.js 22 and genlayer CLI
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && npm install -g genlayer@0.37.1 \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 botuser

COPY --from=builder /root/.local /home/botuser/.local
COPY --chown=botuser:botuser . .

RUN mkdir -p /app/data && chown -R botuser:botuser /app

USER botuser

ENV PATH=/home/botuser/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=10000

EXPOSE 10000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:10000/').read()" || exit 1

CMD ["genbot"]

FROM python:3.12-slim-bookworm

ARG OLLAMA_VERSION=0.40.18

LABEL org.opencontainers.image.title="Orinoco AI"
LABEL org.opencontainers.image.description="Self-hosted personal AI assistant"
LABEL org.opencontainers.image.source="https://github.com/lcswolf/orinoco-ai"
LABEL org.opencontainers.image.licenses="MIT"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Ollama's official installer needs curl and zstd at build time. They are
# removed afterwards; the CPU-only runtime uses the host's CPU and RAM.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl zstd \
    && curl -fsSL -o /tmp/ollama-install.sh https://ollama.com/install.sh \
    && OLLAMA_VERSION="${OLLAMA_VERSION}" sh /tmp/ollama-install.sh \
    && rm -f /tmp/ollama-install.sh \
    && apt-get purge -y --auto-remove curl zstd \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --home-dir /home/container --shell /usr/sbin/nologin container \
    && mkdir -p /opt/orinoco /home/container/data/models

WORKDIR /opt/orinoco

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt \
    && /usr/local/bin/ollama --version \
    && supervisord --version

COPY orinoco ./orinoco
COPY docker/entrypoint.py /usr/local/bin/orinoco-entrypoint
COPY docker/ollama-start.sh /usr/local/bin/orinoco-ollama-start
COPY docker/model-init.sh /usr/local/bin/orinoco-model-init
COPY docker/web-start.sh /usr/local/bin/orinoco-web-start
COPY docker/supervisord.conf /opt/orinoco/docker/supervisord.conf

RUN chmod 755 /usr/local/bin/orinoco-entrypoint \
        /usr/local/bin/orinoco-ollama-start \
        /usr/local/bin/orinoco-model-init \
        /usr/local/bin/orinoco-web-start \
    && chown -R root:root /opt/orinoco \
    && chmod -R a-w /opt/orinoco \
    && chown -R container:container /home/container

ENV USER=container \
    HOME=/home/container \
    PYTHONPATH=/opt/orinoco \
    TZ=Europe/London \
    ORINOCO_ENV=production \
    OLLAMA_HOST=127.0.0.1:11434 \
    OLLAMA_MODELS=/home/container/data/models \
    OLLAMA_NO_CLOUD=1 \
    OLLAMA_CONTEXT_LENGTH=2048 \
    OLLAMA_NUM_PARALLEL=1 \
    OLLAMA_MAX_LOADED_MODELS=1 \
    OLLAMA_MAX_QUEUE=8 \
    OLLAMA_KEEP_ALIVE=5m

WORKDIR /home/container
USER container

ENTRYPOINT ["python", "/usr/local/bin/orinoco-entrypoint"]

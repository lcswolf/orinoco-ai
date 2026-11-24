FROM python:3.12-slim-bookworm

LABEL org.opencontainers.image.title="Orinoco AI"
LABEL org.opencontainers.image.description="Self-hosted personal AI assistant"
LABEL org.opencontainers.image.source="https://github.com/lcswolf/orinoco-ai"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --home-dir /home/container --shell /usr/sbin/nologin container \
    && mkdir -p /opt/orinoco

WORKDIR /opt/orinoco

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY orinoco ./orinoco
COPY docker/entrypoint.py /usr/local/bin/orinoco-entrypoint

RUN chmod 755 /usr/local/bin/orinoco-entrypoint \
    && chown -R root:root /opt/orinoco \
    && chmod -R a-w /opt/orinoco

ENV USER=container \
    HOME=/home/container \
    PYTHONPATH=/opt/orinoco \
    TZ=Europe/London

WORKDIR /home/container
USER container

ENTRYPOINT ["python", "/usr/local/bin/orinoco-entrypoint"]

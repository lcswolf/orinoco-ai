FROM python:3.12-slim-bookworm@sha256:44cf1793efa7c7a476bb0f2cff81443f4a072c90c1cb127e2924933daa3e8c64

# Published SHA-256 for the install.sh asset in the pinned Ollama release.
ARG OLLAMA_VERSION=0.40.18
ARG OLLAMA_INSTALL_SHA256=17659c2456c9e65a3b11056b76da51774911cb822f47bf44f7f3ecc0c40528a8
# Fixed Debian snapshot: update this timestamp deliberately during security maintenance.
ARG DEBIAN_SNAPSHOT=20261125T000000Z

LABEL org.opencontainers.image.title="Orinoco AI"
LABEL org.opencontainers.image.description="Self-hosted personal AI assistant"
LABEL org.opencontainers.image.source="https://github.com/lcswolf/orinoco-ai"
LABEL org.opencontainers.image.licenses="MIT"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Ollama's official installer needs curl and zstd at build time. The release
# installer is checksum-verified before execution; build-only tools are removed.
# Use a fixed Debian archive snapshot so apt dependency resolution is repeatable.
# Check-Valid-Until is disabled because snapshot Release metadata is historical.
# The CPU-only runtime uses the host's CPU and RAM.
RUN printf 'Types: deb\\nURIs: https://snapshot.debian.org/archive/debian/%s/\\nSuites: bookworm bookworm-updates\\nComponents: main\\nSigned-By: /usr/share/keyrings/debian-archive-keyring.gpg\\nCheck-Valid-Until: no\\n\\nTypes: deb\\nURIs: https://snapshot.debian.org/archive/debian-security/%s/\\nSuites: bookworm-security\\nComponents: main\\nSigned-By: /usr/share/keyrings/debian-archive-keyring.gpg\\nCheck-Valid-Until: no\\n' "$DEBIAN_SNAPSHOT" "$DEBIAN_SNAPSHOT" > /etc/apt/sources.list.d/debian.sources \\\n    && apt-get update \\
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends ca-certificates curl zstd tzdata \
    && curl --fail --show-error --location \
        --output /tmp/ollama-install.sh \
        "https://github.com/ollama/ollama/releases/download/v${OLLAMA_VERSION}/install.sh" \
    && printf '%s  %s\n' "${OLLAMA_INSTALL_SHA256}" /tmp/ollama-install.sh | sha256sum --check --status \
    && OLLAMA_VERSION="${OLLAMA_VERSION}" sh /tmp/ollama-install.sh \
    && rm -f /tmp/ollama-install.sh \
    && apt-get purge -y --auto-remove curl zstd \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --home-dir /home/container --shell /usr/sbin/nologin container \
    && mkdir -p /opt/orinoco /home/container/data/models

WORKDIR /opt/orinoco

COPY requirements.lock ./requirements.lock
RUN pip install --no-cache-dir --require-hashes -r requirements.lock \
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

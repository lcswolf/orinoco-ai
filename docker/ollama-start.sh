#!/bin/sh
set -eu

# Validate resource-sensitive settings before starting the local inference service.

MODEL_CONTEXT="${MODEL_CONTEXT:-2048}"
AI_CONCURRENCY="${AI_CONCURRENCY:-1}"

case "$MODEL_CONTEXT" in
    ''|*[!0-9]*) echo "ERROR: MODEL_CONTEXT must be numeric." >&2; exit 2 ;;
esac
if [ "$MODEL_CONTEXT" -lt 1024 ] || [ "$MODEL_CONTEXT" -gt 8192 ]; then
    echo "ERROR: MODEL_CONTEXT must be between 1024 and 8192." >&2
    exit 2
fi

case "$AI_CONCURRENCY" in
    1) ;;
    *) echo "ERROR: AI_CONCURRENCY is currently fixed at 1." >&2; exit 2 ;;
esac

 # Ollama is loopback-only: Pterodactyl must never publish this API as a public port.
export OLLAMA_HOST="127.0.0.1:11434"
export OLLAMA_MODELS="${OLLAMA_MODELS:-/home/container/data/models}"
export OLLAMA_CONTEXT_LENGTH="$MODEL_CONTEXT"
export OLLAMA_NUM_PARALLEL="$AI_CONCURRENCY"
export OLLAMA_MAX_LOADED_MODELS=1
export OLLAMA_MAX_QUEUE=8
export OLLAMA_KEEP_ALIVE=5m
export OLLAMA_NO_CLOUD=1

mkdir -p "$OLLAMA_MODELS"
if [ ! -w "$OLLAMA_MODELS" ]; then
    echo "ERROR: Ollama model directory is not writable: $OLLAMA_MODELS" >&2
    exit 1
fi

echo "Starting local Ollama service on 127.0.0.1:11434"
exec /usr/local/bin/ollama serve

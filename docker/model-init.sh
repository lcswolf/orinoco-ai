#!/bin/sh
set -eu

export OLLAMA_HOST="127.0.0.1:11434"
export OLLAMA_MODELS="${OLLAMA_MODELS:-/home/container/data/models}"

if [ "${AUTO_DOWNLOAD_MODEL:-true}" != "true" ]; then
    echo "Automatic model download is disabled; skipping first-run download."
    exit 0
fi

MODEL="${AI_MODEL:-qwen2.5:1.5b}"
case "$MODEL" in
    qwen2.5:0.5b|qwen2.5:1.5b|qwen2.5:3b) ;;
    *)
        echo "ERROR: Unsupported AI_MODEL '$MODEL'." >&2
        exit 2
        ;;
esac

echo "Waiting for the local Ollama API..."
attempt=0
until /usr/local/bin/ollama list >/dev/null 2>&1; do
    attempt=$((attempt + 1))
    if [ "$attempt" -ge 120 ]; then
        echo "ERROR: Ollama did not become ready within 4 minutes." >&2
        exit 1
    fi
    sleep 2
done

if /usr/local/bin/ollama show "$MODEL" >/dev/null 2>&1; then
    echo "Model $MODEL is already present; no download needed."
else
    echo "Downloading model $MODEL into persistent storage. This may take a while."
    /usr/local/bin/ollama pull "$MODEL"
    echo "Model $MODEL downloaded successfully."
fi

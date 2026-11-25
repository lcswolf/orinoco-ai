#!/bin/sh
set -eu

# First-run model setup is separate from the long-running Ollama service.
# Models are stored on the persistent Pterodactyl data volume.

export OLLAMA_HOST="127.0.0.1:11434"
export OLLAMA_MODELS="${OLLAMA_MODELS:-/home/container/data/models}"

if [ "${AUTO_DOWNLOAD_MODEL:-true}" != "true" ]; then
    echo "Automatic model download is disabled; skipping first-run download."
    exit 0
fi

MODEL="${AI_MODEL:-qwen2.5:1.5b}"
# Only curated model tags are accepted; arbitrary tags are not pulled at startup.
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
    # A transient network or registry failure should not require an operator
    # to restart the Pterodactyl server immediately. Ollama can resume a
    # partial download on the next pull attempt.
    pull_attempt=1
    max_pull_attempts=3
    until /usr/local/bin/ollama pull "$MODEL"; do
        if [ "$pull_attempt" -ge "$max_pull_attempts" ]; then
            echo "ERROR: Model download failed after $max_pull_attempts attempts." >&2
            echo "The web service may be running, but /readyz will remain HTTP 503 until the model is available." >&2
            exit 1
        fi
        pull_attempt=$((pull_attempt + 1))
        echo "Model download failed; retrying ($pull_attempt/$max_pull_attempts) in 30 seconds." >&2
        sleep 30
    done
    echo "Model $MODEL downloaded successfully."
fi

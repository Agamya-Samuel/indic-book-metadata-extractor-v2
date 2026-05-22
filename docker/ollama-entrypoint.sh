#!/bin/bash
set -e

echo "[Ollama Entrypoint] Starting Ollama server in background..."
/bin/ollama serve &
OLLAMA_PID=$!

echo "[Ollama Entrypoint] Waiting for Ollama to be ready..."
for i in $(seq 1 30); do
    if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
        echo "[Ollama Entrypoint] Ollama is ready."
        break
    fi
    if [ $i -eq 30 ]; then
        echo "[Ollama Entrypoint] WARNING: Ollama did not become ready in 30 seconds."
    fi
    sleep 1
done

if [ -n "$OLLAMA_PRELOAD_MODEL" ]; then
    echo "[Ollama Entrypoint] Checking if model '$OLLAMA_PRELOAD_MODEL' is available..."
    if ! ollama list 2>/dev/null | grep -q "$OLLAMA_PRELOAD_MODEL"; then
        echo "[Ollama Entrypoint] Pulling model '$OLLAMA_PRELOAD_MODEL'..."
        ollama pull "$OLLAMA_PRELOAD_MODEL"
        echo "[Ollama Entrypoint] Model '$OLLAMA_PRELOAD_MODEL' pulled successfully."
    else
        echo "[Ollama Entrypoint] Model '$OLLAMA_PRELOAD_MODEL' already available."
    fi
fi

echo "[Ollama Entrypoint] Ollama setup complete. Serving..."
wait $OLLAMA_PID

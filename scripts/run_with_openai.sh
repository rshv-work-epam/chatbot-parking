#!/usr/bin/env bash
set -euo pipefail

# Wrapper to run the demo with OpenAI credentials read from a local file.
# Usage:
#   scripts/run_with_openai.sh                 # reads $HOME/.config/chatbot_parking/.env
#   scripts/run_with_openai.sh /path/to/keyfile
# Key file may contain either a plain API key (single line) or an env-style
# file with OPENAI_API_KEY=sk-... (in which case it will be sourced).

KEY_FILE="${1:-$HOME/.config/chatbot_parking/.env}"

if [ ! -f "$KEY_FILE" ]; then
  echo "Key file not found: $KEY_FILE" >&2
  exit 2
fi

# Load key: support both plain-key files and env files
if grep -q '=' "$KEY_FILE"; then
  # shellcheck disable=SC1090
  source "$KEY_FILE"
else
  export OPENAI_API_KEY="$(cat "$KEY_FILE")"
fi

export EMBEDDINGS_PROVIDER="openai"
export LLM_PROVIDER="openai"
# Optional overrides (can be set in the key file or environment)
export EMBEDDINGS_MODEL="${EMBEDDINGS_MODEL:-text-embedding-3-small}"
export LLM_MODEL="${LLM_MODEL:-gpt-4o-mini}"

echo "Running demo with OpenAI provider (key file: $KEY_FILE)"
PYTHONPATH=./src python -m chatbot_parking.main

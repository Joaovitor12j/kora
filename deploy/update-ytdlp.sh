#!/usr/bin/env bash
# Atualiza o yt-dlp no venv do projeto. O worker roda em lotes, então o próximo lote já usa a versão nova.
# Não mexe no uv.lock: um `uv sync` volta à versão travada. Para fixar a nova, use
# `uv lock --upgrade-package yt-dlp`.
# Com KORA_YTDLP_NIGHTLY=1 (ex.: `systemctl --user edit kora-ytdlp-update`) segue as versões
# nightly, que recebem as correções de sites antes da versão estável.
set -euo pipefail
cd "$(dirname "$0")/.."

antes=$(.venv/bin/yt-dlp --version)
uv pip install --quiet --python .venv/bin/python --upgrade ${KORA_YTDLP_NIGHTLY:+--pre} "yt-dlp[default]"
depois=$(.venv/bin/yt-dlp --version)

if [ "$antes" = "$depois" ]; then
    echo "yt-dlp já está na versão mais recente ($depois)"
    exit 0
fi
echo "yt-dlp atualizado: $antes -> $depois (vale a partir do próximo lote)"

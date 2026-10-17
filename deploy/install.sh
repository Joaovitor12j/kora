#!/usr/bin/env bash
# Instala (ou remove) os serviços do Kora no systemd do usuário.
#   deploy/install.sh              instala e inicia o bot e os timers (lotes do worker e yt-dlp)
#   deploy/install.sh uninstall    para e remove
# Antes, pare o bot e o worker que estiverem rodando em terminais: dois bots com o
# mesmo token disputam as mensagens do Telegram. O worker roda em lotes (kora-worker.timer):
# 1 h depois de ligar e a cada 8 h; o /processar do bot dispara um lote na hora.
set -euo pipefail

REPO=$(cd "$(dirname "$0")/.." && pwd)
DESTINO="$HOME/.config/systemd/user"
UNITS=(kora-bot.service kora-worker.timer kora-ytdlp-update.timer)

if [ "${1:-}" = "uninstall" ]; then
    systemctl --user disable --now "${UNITS[@]}" kora-worker.service kora-ytdlp-update.service 2>/dev/null || true
    rm -f "$DESTINO"/kora-*.service "$DESTINO"/kora-*.timer
    systemctl --user daemon-reload
    echo "serviços do Kora removidos"
    exit 0
fi

[ -x "$REPO/.venv/bin/kora-bot" ] || { echo "rode 'uv sync' em $REPO antes" >&2; exit 1; }
[ -f "$REPO/.env" ] || { echo "falta $REPO/.env (copie de .env.example)" >&2; exit 1; }

mkdir -p "$DESTINO"
# Migração: antes o worker era um serviço contínuo habilitado; agora é um lote disparado pelo timer.
systemctl --user disable --now kora-worker.service 2>/dev/null || true
for arquivo in "$REPO"/deploy/*.service "$REPO"/deploy/*.timer; do
    sed "s|@REPO@|$REPO|g" "$arquivo" > "$DESTINO/$(basename "$arquivo")"
done
systemctl --user daemon-reload
systemctl --user enable --now "${UNITS[@]}"

echo "instalado. Status:   systemctl --user status kora-bot kora-worker"
echo "Logs:                journalctl --user -u kora-worker -f"
echo "Subir sem login:     loginctl enable-linger $USER   (opcional)"

#!/usr/bin/env bash
set -euo pipefail

LABEL="com.carrie.wechatpub-api"
ROOT="/Users/lulu/AIWork/tools/wechatpub-api"
SRC="$ROOT/deploy/$LABEL.plist"
DEST="$HOME/Library/LaunchAgents/$LABEL.plist"

mkdir -p "$HOME/Library/LaunchAgents" "$HOME/Library/Logs"
cp "$SRC" "$DEST"
chmod 644 "$DEST"

launchctl bootout "gui/$(id -u)" "$DEST" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$(id -u)" "$DEST"
launchctl kickstart -k "gui/$(id -u)/$LABEL"

echo "Installed $LABEL"
echo "Health: curl http://127.0.0.1:18831/health"
echo "Logs: $HOME/Library/Logs/wechatpub-api.log"

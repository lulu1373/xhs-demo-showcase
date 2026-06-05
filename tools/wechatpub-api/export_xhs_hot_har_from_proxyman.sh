#!/usr/bin/env bash
set -euo pipefail

PROXYMAN_CLI="${PROXYMAN_CLI:-/Applications/Proxyman.app/Contents/MacOS/proxyman-cli}"
INBOX="${XHS_GLOBAL_HOT_HAR_INBOX:-/Users/lulu/AIWork/xhs-hot-har-inbox}"
WECHATPUB_DIR="/Users/lulu/AIWork/tools/wechatpub-api"

if [[ ! -x "$PROXYMAN_CLI" ]]; then
  echo "proxyman-cli not found: $PROXYMAN_CLI" >&2
  exit 1
fi

mkdir -p "$INBOX"
stamp="$(date +%Y%m%d_%H%M%S)"
har_path="$INBOX/xhs-hot-$stamp.har"

"$PROXYMAN_CLI" export-log \
  --mode domains \
  --domains edith.xiaohongshu.com \
  --domains www.xiaohongshu.com \
  --format har \
  --output "$har_path"

cd "$WECHATPUB_DIR"
./wechatpub xhs-global-hot-keywords --source har --har-file "$(basename "$har_path")"

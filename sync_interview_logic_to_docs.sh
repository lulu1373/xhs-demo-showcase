#!/bin/zsh
set -euo pipefail

ROOT="/Users/lulu/AIWork"
SRC_HTML="$ROOT/xhs_user_profile_676c0410_interview_logic.html"
DEST_HTML="$ROOT/docs/xhs_user_profile_676c0410_interview_logic.html"
ASSET_DIR="$ROOT/docs/assets/xhs"
SRC_IMAGE="/Users/lulu/Downloads/IMG_8857.JPG"
DEST_IMAGE="$ASSET_DIR/IMG_8857.JPG"

mkdir -p "$ASSET_DIR"

cp "$SRC_HTML" "$DEST_HTML"
cp "$SRC_IMAGE" "$DEST_IMAGE"

LC_ALL=C sed -i '' 's#file:///Users/lulu/Downloads/IMG_8857.JPG#assets/xhs/IMG_8857.JPG#g' "$DEST_HTML"

echo "Synced to $DEST_HTML"

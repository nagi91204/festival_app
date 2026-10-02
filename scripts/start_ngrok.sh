#!/usr/bin/env bash
set -euo pipefail

# Django は別のターミナルで `python manage.py runserver 0.0.0.0:8000` を起動してから実行する。
PORT="${1:-8000}"

if ! command -v ngrok >/dev/null 2>&1; then
  echo "ngrok が見つかりません。macOS では: brew install ngrok" >&2
  exit 1
fi

if ! ngrok config check >/dev/null 2>&1; then
  echo "ngrok の認証設定が必要です。次を実行してください:" >&2
  echo "  ngrok config add-authtoken '<YOUR_AUTHTOKEN>'" >&2
  exit 1
fi

echo "Django の localhost:${PORT} を外部公開します。"
echo "表示された Forwarding の https:// URL を参加者へ共有してください。"
exec ngrok http "${PORT}" --log=stdout

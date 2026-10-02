# festival_app

## 初回セットアップ

```bash
cp .env.example .env
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver 0.0.0.0:8000
```

同じ Wi-Fi の端末から接続する場合は、`.env` の `DJANGO_ALLOWED_HOSTS` に司会 PC の IP アドレスを追加してください。教室内の信頼できるネットワークでのみ `*` を使えます。

## Git に含めないもの

`.env`、`.venv`、`db.sqlite3`、`media/` は `.gitignore` によりコミットされません。環境変数の項目だけを共有したい場合は `.env.example` を更新してください。

## ngrok で外部公開する

ngrok はクラウドへ恒久デプロイするサービスではなく、この PC で起動している Django を一時的に HTTPS 公開するトンネルです。PC を終了したり ngrok を停止したりすると URL も利用できなくなります。

1. 初回だけ ngrok をインストール・認証します。

   ```bash
   brew install ngrok
   ngrok config add-authtoken "<ngrok の管理画面で取得したトークン>"
   ```

2. `.env.example` をコピーして `.env` を作成します。`DJANGO_ALLOWED_HOSTS` には ngrok 用ドメインをあらかじめ設定済みです。

   ```bash
   cp .env.example .env
   ```

3. ターミナルを2つ開き、片方で Django、もう片方で ngrok を起動します。

   ```bash
   # ターミナル 1
   source .venv/bin/activate
   python manage.py runserver 0.0.0.0:8000
   ```

   ```bash
   # ターミナル 2
   bash scripts/start_ngrok.sh
   ```

   表示される `Forwarding` の `https://...ngrok-free.app` URL を参加者へ共有してください。WebSocket も同じ HTTPS URL で自動的に接続されます。

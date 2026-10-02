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

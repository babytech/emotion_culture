# WeChat Mini Program Backend Skeleton

This folder contains phase-2 backend scaffolding for the WeChat mini program.

## What is included

- FastAPI app entrypoint
- `/api/health` health check
- `/api/analyze` analysis endpoint
- `/api/send-email` email endpoint
- Request/response schemas
- Service layer split (`analysis`, `email`, `storage`)
- Cloud file resolver (`cloud://` / `http(s)` -> temp local file)
- Self-contained runtime core under `app/core`:
  - logic modules: `culture.py`, `emotion.py`, `speech.py`, `email_utils.py`
  - data: `poems.json`
  - static assets: `images/tangsong`, `images/guochao`

## Current scope

- Supports local debug paths (`image_path`, `audio_path`) for media inputs.
- Supports cloud file IDs:
  - `cloud://...` via WeChat CloudBase `batchdownloadfile`
  - `http(s)://...` direct download
- Temporary files are auto-cleaned after each request.

## Run locally

```bash
cd /Users/babytech/github/emotion_culture/services/wechat-api
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 9000
```

Open:

- http://127.0.0.1:9000/docs
- http://127.0.0.1:9000/api/health

## Cloud file ID config

Set these env vars (see `.env.example`):

- `WECHAT_APP_ID`
- `WECHAT_APP_SECRET`
- `WECHAT_CLOUDBASE_ENV`

If missing, requests using `cloud://` file IDs return `400`.

## Mini Program API contract

See:

- [miniprogram-api.md](/Users/babytech/github/emotion_culture/services/wechat-api/miniprogram-api.md)

## Notes

- This backend intentionally does **not** modify `apps/pc` runtime behavior.
- Backend runtime no longer depends on `apps/pc`; it can be deployed using `services/wechat-api` only.
- For local backend debug, put SMTP vars directly in `services/wechat-api/.env`.

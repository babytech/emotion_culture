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

## Deploy to WeChat Cloud Hosting (Custom Deploy)

This service is ready for Cloud Hosting custom deployment.

### 1) Deploy source path

Use `services/wechat-api` as the deploy directory.

Required files (already prepared):

- `Dockerfile`
- `.dockerignore`
- `requirements.txt`
- `app/**`

### 2) Console steps

In WeChat Cloud Hosting console:

1. Click `自定义部署`.
2. Choose source-code deployment and point to `services/wechat-api`.
3. Keep container listen port as `80` (Dockerfile default).
4. Add environment variables (see below).
5. Deploy and wait for service status to become healthy.

### 3) Required environment variables

Set these in Cloud Hosting environment variables (do not upload `.env`):

- `WECHAT_APP_ID`
- `WECHAT_APP_SECRET`
- `WECHAT_CLOUDBASE_ENV`
- `EMAIL_SENDER_ADDRESS`
- `EMAIL_SENDER_PASSWORD`
- `SMTP_SERVER_HOST`
- `SMTP_SERVER_PORT`

Optional:

- `PORT` (default `80`)

### 4) Post-deploy checks

1. Open `GET /api/health`, expect `{"ok": true}`.
2. Call `POST /api/analyze` from mini program, expect HTTP 200.
3. Call `POST /api/send-email`, expect HTTP 200 with `success=true`.

### 5) Mini program config after backend deploy

Update mini program backend URL from local loopback to your cloud service domain:

- `apps/wechat-mini/config/index.js` -> `apiBaseUrl`

Keep `cloudEnv` unchanged if you still use the same CloudBase environment.

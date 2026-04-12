# WeChat Mini Program Backend Skeleton

This folder contains phase-2 backend scaffolding for the WeChat mini program.

## What is included

- FastAPI app entrypoint
- `/api/health` health check
- `/api/analyze` analysis endpoint
- `/api/analyze/async` async analyze create endpoint
- `/api/analyze/async/{task_id}` async analyze status endpoint
- `/api/send-email` email endpoint
- `/api/retention/calendar` retention calendar endpoint
- `/api/retention/weekly-report` retention weekly report endpoint
- `/api/retention/write-settings` retention write switch endpoint
- `/api/retention/weekly-report(s)` retention weekly snapshot delete endpoint
- `/api/retention/favorites` retention favorites clear endpoint
- `/api/favorites*` favorites endpoints
- `/api/stt/tencent` built-in Tencent STT gateway endpoint
- Request/response schemas
- Service layer split (`analysis`, `email`, `storage`)
- Cloud file resolver (`cloud://` / `http(s)` -> temp local file)
- Self-contained runtime core under `app/core`:
  - logic modules: `culture.py`, `emotion.py`, `speech.py`, `email_utils.py`
  - data: `poems.json`
  - static assets: `images/tangsong`, `images/guochao`

## Current scope

- Supports local debug paths (`image_path`, `audio_path`) for media inputs.
- Voice input follows BE-010 main flow: speech is transcribed to text first, then enters unified text analysis.
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
- `WECHAT_REQUESTS_TRUST_ENV` (default `1`, backend will also retry with `0` on SSL failure)
- `WECHAT_CA_BUNDLE` (custom CA pem path, only when runtime requires custom trust chain)
- `WECHAT_DISABLE_SSL_VERIFY` (default `0`; emergency only)
- `SPEECH_ASR_SERVICE` (`on` | `off`, default `on`; ASR service switch. `off` will skip transcript request regardless of endpoint/provider)
- `SPEECH_STT_PROVIDER` (`auto` | `http` | `mock`, default `auto`)
- `SPEECH_STT_ENDPOINT` (used by `http` provider)
- `SPEECH_STT_TOKEN` (optional bearer token for STT endpoint)
- `SPEECH_STT_AUTH_HEADER` (default `Authorization`)
- `SPEECH_STT_AUTH_SCHEME` (default `Bearer`)
- `SPEECH_STT_TIMEOUT_SEC` (default `18`)
- `SPEECH_STT_MOCK_TEXT` (only for local debug with `SPEECH_STT_PROVIDER=mock`)
- `SPEECH_STT_HTTP_METHOD` (default `POST`)
- `SPEECH_STT_HTTP_MODE` (`multipart` | `raw` | `json_base64`, default `multipart`)
- `SPEECH_STT_FILE_FIELD` (default `audio`, for `multipart`)
- `SPEECH_STT_FILE_MIME` (optional override mime type)
- `SPEECH_STT_RAW_CONTENT_TYPE` (optional content-type for `raw`)
- `SPEECH_STT_JSON_AUDIO_FIELD` (default `audio_base64`, for `json_base64`)
- `SPEECH_STT_JSON_FILENAME_FIELD` (default `filename`, for `json_base64`)
- `SPEECH_STT_FORM_JSON` (optional JSON object string, sent as form fields)
- `SPEECH_STT_JSON_TEMPLATE` (optional JSON object string, merged into JSON request body)
- `SPEECH_STT_HEADERS_JSON` (optional JSON object string, custom request headers)
- `SPEECH_STT_QUERY_JSON` (optional JSON object string, query parameters)
- `SPEECH_STT_RESPONSE_PATHS` (optional comma-separated paths to transcript text)
- `TENCENT_SECRET_ID` / `TENCENT_SECRET_KEY` (Tencent sub-account secret pair for STT gateway)
- `TENCENT_ASR_ENDPOINT` (default `asr.tencentcloudapi.com`)
- `TENCENT_ASR_REGION` (default `ap-guangzhou`)
- `TENCENT_ASR_ENGINE_MODEL_TYPE` (default `16k_zh`)
- `TENCENT_ASR_SUB_SERVICE_TYPE` (default `2`)
- `TENCENT_ASR_PROJECT_ID` (default `0`)
- `TENCENT_ASR_WORD_INFO` (default `0`)
- `TENCENT_ASR_TIMEOUT_SEC` (default `20`)
- `TENCENT_ASR_MAX_AUDIO_BYTES` (default `3145728`)
- `TENCENT_STT_GATEWAY_TOKEN` (required before mini program production launch; used to protect `/api/stt/tencent` from abuse)
- `VOICE_REQUIRE_TRANSCRIPT` (`0` | `1`, default `0`; transcript strictness gate, NOT ASR on/off switch)
- `RETENTION_SERVICE_ENABLED` (`on` | `off`, default `on`; phase-2 retention feature family switch)
- `RETENTION_WEEKLY_REPORT_ENABLED` (`on` | `off`, default `on`; weekly report switch, depends on retention switch)
- `RETENTION_FAVORITES_ENABLED` (`on` | `off`, default `on`; favorites switch, depends on retention switch)
- `FAVORITES_MAX_ITEMS` (default `500`, max favorites per user)
- `WEEKLY_REPORT_CACHE_MAX_ITEMS` (default `32`, max cached weekly report snapshots per user)
- `TODAY_HISTORY_ENABLED` (`on` | `off`, default `on`; “历史上的今天”功能开关)
- `TODAY_HISTORY_PROVIDER` (`auto` | `http` | `seed` | `mock`, default `auto`)
- `TODAY_HISTORY_HTTP_ENDPOINT` (optional external AI/search gateway endpoint)
- `TODAY_HISTORY_HTTP_METHOD` (`GET` | `POST`, default `POST`)
- `TODAY_HISTORY_HTTP_TIMEOUT_SEC` (default `12`)
- `TODAY_HISTORY_HTTP_HEADERS_JSON` (optional JSON headers for gateway auth)
- `TODAY_HISTORY_HTTP_PAYLOAD_JSON` (optional JSON object merged into gateway request payload, for provider-specific params)
- `TODAY_HISTORY_CACHE_PATH` (default `/tmp/emotion_culture/today_history_cache.json`)
- `TODAY_HISTORY_CACHE_TTL_SEC` (default `1209600`, 14 days)
- `TODAY_HISTORY_SENSITIVE_KEYWORDS` (optional comma-separated moderation keywords override)
- `TODAY_HISTORY_EMOTION_HINTS` (optional comma-separated hints for separating companion copy from factual summary)
- `MEDIA_GEN_PROVIDER` (`local_mock` | `static_pool`, default `local_mock`)
- Third-party dynamic image providers (`http` / `qwen` / `hunyuan` / `liblib`) are removed from current codebase.
- `MEDIA_GEN_PROVIDER_MAX_RETRIES` (default `1`, provider retry count on retryable failure)
- `MEDIA_GEN_PROVIDER_RETRY_BACKOFF_MS` (default `220`, retry backoff base milliseconds)
- `MEDIA_GEN_STATIC_POOL_CLASSICAL` / `MEDIA_GEN_STATIC_POOL_TECH` / `MEDIA_GEN_STATIC_POOL_GUOCHAO` (comma-separated static references, recommend COS URLs)
- `MEDIA_GEN_STATIC_POOL_CLASSICAL_JSON` / `MEDIA_GEN_STATIC_POOL_TECH_JSON` / `MEDIA_GEN_STATIC_POOL_GUOCHAO_JSON` (JSON array form, same meaning as above)
- `MEDIA_GEN_STATIC_POOL_COMMON` / `MEDIA_GEN_STATIC_POOL_COMMON_JSON` (optional common fallback pool)
- JSON pool item supports both plain string URL and object form:
  - `id`
  - `url`
  - `style`
  - `emotion_tags`
  - `intensity`
  - `active`
  - `weight`
  - `updated_at`
- `MEDIA_GEN_REQUIRE_CONSENT` (default `1`, require explicit user consent before media generation task)
- `MEDIA_GEN_ENABLE_WEEKLY_QUOTA` (default `1`, enable per-user weekly quota guard)
- `MEDIA_GEN_WEEKLY_LIMIT` (default `1`, max media-generate tasks per user per ISO week)
- `MEDIA_GEN_ENABLE_POINTS` (default `1`, enable points deduction gate)
- `MEDIA_GEN_POINTS_COST` (default `1`, points cost per media-generate task)
- `MEDIA_QUOTA_STORE_PATH` (default `/tmp/emotion_culture/media_quota_store.json`)
- `MEDIA_POINTS_STORE_PATH` (default `/tmp/emotion_culture/media_points_store.json`)
- `FACE_MIN_CANDIDATE_AREA_RATIO` (default `0.01`, tiny box filter for initial face candidates)
- `FACE_DEDUPE_IOU_THRESHOLD` (default `0.3`, merge duplicated overlapping face boxes)
- `FACE_MIN_PRESENCE_EYE_COUNT` (default `1`, minimum eyes for considering a face as valid)
- `FACE_HIGH_AREA_PRESENCE_RATIO` (default `0.08`, large-face fallback even if eye detect is unstable)
- `FACE_MIN_AREA_RATIO` (default `0.022`, minimum primary face area ratio in image)
- `FACE_MULTI_MIN_RATIO` (default `0.8`, secondary/primary face size ratio for multi-face reject)
- `FACE_MULTI_SECONDARY_ABS_RATIO_FACTOR` (default `0.75`, secondary absolute size factor)
- `FACE_MIN_BRIGHTNESS` (default `50`, minimum face brightness)
- `FACE_MIN_LAPLACIAN_VAR` (default `24`, minimum face sharpness)
- `FACE_LARGE_FACE_AREA_RATIO` (default `0.10`, large-face selfie threshold)
- `FACE_LARGE_FACE_MIN_LAPLACIAN_VAR` (default `14`, relaxed sharpness threshold for close-up large-face selfies)

### STT endpoint examples

Tencent ASR gateway in this same backend service (recommended):

```env
SPEECH_ASR_SERVICE=on
SPEECH_STT_PROVIDER=http
SPEECH_STT_ENDPOINT=https://<your-cloud-host-domain>/api/stt/tencent
SPEECH_STT_HTTP_MODE=multipart
SPEECH_STT_FILE_FIELD=audio
SPEECH_STT_RESPONSE_PATHS=text
SPEECH_STT_HEADERS_JSON={"X-STT-GATEWAY-TOKEN":"<same_as_TENCENT_STT_GATEWAY_TOKEN>"}

TENCENT_SECRET_ID=<sub_account_secret_id>
TENCENT_SECRET_KEY=<sub_account_secret_key>
TENCENT_ASR_REGION=ap-guangzhou
TENCENT_ASR_ENGINE_MODEL_TYPE=16k_zh
TENCENT_STT_GATEWAY_TOKEN=<random_long_secret>
```

ASR switch vs strictness:

- Use `SPEECH_ASR_SERVICE=on/off` to control whether backend calls STT service.
- Keep `SPEECH_STT_ENDPOINT` stable in env and switch by `SPEECH_ASR_SERVICE` to reduce misconfiguration risk.
- `VOICE_REQUIRE_TRANSCRIPT` only controls strictness when transcript is empty; it does not enable/disable ASR by itself.

Retention switch semantics:

- Use `RETENTION_SERVICE_ENABLED=on/off` to control phase-2 retention APIs (`/api/retention/*` + `/api/favorites*`).
- Use `RETENTION_WEEKLY_REPORT_ENABLED` to control weekly report endpoint independently.
- Use `RETENTION_FAVORITES_ENABLED` to control favorites endpoints independently.
- These switches are explicit feature flags; do not infer feature enablement from unrelated config values.

Disable ASR but keep endpoint unchanged (admin switch example):

```env
SPEECH_ASR_SERVICE=off
SPEECH_STT_PROVIDER=http
SPEECH_STT_ENDPOINT=https://<your-cloud-host-domain>/api/stt/tencent
VOICE_REQUIRE_TRANSCRIPT=0
```

### Phase-3 media provider note

Current backend no longer calls third-party dynamic image providers.

Mini program can optionally pass extra media-generate context:

- `emotion_code`
- `emotion_label`
- `trigger_tags`

These fields help backend choose a better matching static asset from the configured pool metadata.

- Use `MEDIA_GEN_PROVIDER=local_mock` (or `static_pool`) for phase-3 baseline.
- If provider is configured to removed values (`http/qwen/hunyuan/liblib`), API returns:
  - `MEDIA_GEN_PROVIDER_DISABLED: third-party dynamic image providers are removed; please use MEDIA_GEN_PROVIDER=local_mock`

Built-in gateway endpoint:

- `POST /api/stt/tencent` (multipart form-data, file field supports `audio` / `file` / `voice`)
- Returns `{ "text": "...", "provider": "tencent_asr", ... }`
- Production hardening: always configure `TENCENT_STT_GATEWAY_TOKEN` and pass it via `SPEECH_STT_HEADERS_JSON` (`X-STT-GATEWAY-TOKEN`) before going live.

Whisper-compatible HTTP gateway (multipart):

```env
SPEECH_STT_PROVIDER=http
SPEECH_STT_ENDPOINT=https://your-stt-gateway.example.com/v1/audio/transcriptions
SPEECH_STT_HTTP_MODE=multipart
SPEECH_STT_FILE_FIELD=file
SPEECH_STT_FORM_JSON={"model":"whisper-1","language":"zh"}
SPEECH_STT_RESPONSE_PATHS=text,data.text,result.text
```

Custom JSON-base64 gateway (for internal Tencent/阿里/讯飞 proxy):

```env
SPEECH_STT_PROVIDER=http
SPEECH_STT_ENDPOINT=https://your-internal-stt.example.com/asr
SPEECH_STT_HTTP_MODE=json_base64
SPEECH_STT_JSON_AUDIO_FIELD=audio_base64
SPEECH_STT_JSON_TEMPLATE={"format":"mp3","sample_rate":16000}
SPEECH_STT_HEADERS_JSON={"X-Api-Key":"your-key"}
SPEECH_STT_RESPONSE_PATHS=result.text,data.transcript
```

### 4) Post-deploy checks

1. Open `GET /api/health`, expect `{"ok": true}`.
2. Call `POST /api/analyze` or async flow (`POST /api/analyze/async` -> `GET /api/analyze/async/{task_id}`), expect HTTP 200.
3. Call `POST /api/send-email`, expect HTTP 200 with `success=true`.

### 5) Mini program config after backend deploy

Update mini program backend URL from local loopback to your cloud service domain:

- `apps/wechat-mini/config/index.js` -> `apiBaseUrl`

Keep `cloudEnv` unchanged if you still use the same CloudBase environment.

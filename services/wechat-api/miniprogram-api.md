# Mini Program API Contract

This document is for WeChat mini program frontend integration with `services/wechat-api`.

Runtime note:

- Backend is self-contained under `services/wechat-api/app/core` and does not require `apps/pc` at deploy time.

## Access mode (recommended)

Use `wx.cloud.callContainer` from mini program frontend.

- `config.env`: your cloud environment id
- Header `X-WX-SERVICE`: your cloud hosting service name
- `path`: backend path (for example `/api/analyze`)

Identity strategy (phase-1):

- Mini program uses WeChat natural identity as primary user id.
- Prefer `x-wx-unionid` when available, otherwise fall back to `x-wx-openid`.
- Frontend should not force custom user id in production by default.
- Optional fallback is only for local/dev environments without WeChat identity context.

`apiBaseUrl` is only needed when frontend must resolve relative image paths such as `/assets/...`.

## Base URL (optional)

- Local debug: `http://127.0.0.1:9000`
- Production: your cloud host domain

## 1) Health check

`GET /api/health`

Response:

```json
{
  "ok": true
}
```

## 2) Analyze emotion

`POST /api/analyze`

### Request body fields (normalized)

- `input_modes` optional array: `text | voice | selfie | pc_camera`
- `request_token` optional string: client-generated idempotency token for async create retries
- `text` optional string
- `image` optional object
  - `url` optional string (`https://...`)
  - `file_id` optional string (`cloud://...`)
  - `local_path` optional local debug path (server-side debug only)
- `audio` optional object
  - `url` optional string (`https://...`)
  - `file_id` optional string (`cloud://...`)
  - `local_path` optional local debug path (server-side debug only)
- `client` optional object: `platform`, `version`

### Legacy fields (still supported)

- `image_url` / `image_file_id` / `image_path`
- `audio_url` / `audio_file_id` / `audio_path`

If both normalized and legacy fields are provided, normalized fields take priority.

BE-010 main-chain rule:

- If `text` exists, backend uses `text` as analysis text.
- If `text` is empty and `audio` exists, backend first transcribes audio to text, then runs unified text analysis.
- `speech` emotion remains an auxiliary signal in fusion.
- `SPEECH_ASR_SERVICE` controls ASR switch (`on`/`off`); when `off`, backend skips transcript request regardless of endpoint/provider.
- `VOICE_REQUIRE_TRANSCRIPT` is strictness gate, not ASR switch. If set to `1`, empty transcript will be rejected; if set to `0`, backend keeps voice emotion as auxiliary signal.
- STT provider is integrated via `SPEECH_STT_ENDPOINT` HTTP adapter and can connect to Whisper/腾讯云/阿里云/讯飞 through your own gateway.

Example:

```json
{
  "input_modes": ["text", "selfie", "voice"],
  "text": "今天有点难过",
  "image": {
    "url": "https://tmp-xxx.jpg",
    "file_id": "cloud://env-id/path/user_photo.jpg"
  },
  "audio": {
    "file_id": "cloud://env-id/path/user_audio.mp3"
  },
  "client": {
    "platform": "mp-weixin",
    "version": "1.0.0"
  }
}
```

Response example:

```json
{
  "request_id": "ana_2f3c0cfa5c53",
  "input_modes": ["text", "selfie", "voice"],
  "result_card": {
    "primary_emotion": {
      "code": "sad",
      "label": "悲伤"
    },
    "secondary_emotions": [
      {
        "code": "neutral",
        "label": "平静"
      }
    ],
    "emotion_overview": "综合文本、图像、语音信号，当前以“悲伤”为主。",
    "trigger_tags": ["学业压力", "人际关系"],
    "poem_response": "千山鸟飞绝，万径人踪灭。",
    "poem_interpretation": "...",
    "guochao_comfort": "每个人都会有情绪低落的时候...",
    "daily_suggestion": "给自己 10 分钟安静时间，做 3 次深呼吸，再写下一个可马上完成的小目标。"
  },
  "system_fields": {
    "request_id": "ana_2f3c0cfa5c53",
    "analyzed_at": "2026-03-25T12:34:56Z",
    "input_modes": ["text", "selfie", "voice"],
    "primary_emotion_code": "sad",
    "secondary_emotion_codes": ["neutral"],
    "confidence_level": "medium",
    "trigger_tags": ["学业压力", "人际关系"],
    "poem_id": "poem_8f65f3de1a3b",
    "guochao_id": "gc_5a4f45f4d2e1",
    "mail_sent": false,
    "tts_ready": false,
    "analysis_text": "今天有点难过",
    "speech_transcript": "今天有点难过",
    "speech_transcript_provider": "http",
    "speech_transcript_status": "ok",
    "speech_transcript_error": null,
    "processing_metrics_ms": {
      "resolve_media_ms": 183,
      "asr_transcribe_ms": 1480,
      "voice_quality_check_ms": 5,
      "voice_emotion_ms": 322,
      "text_emotion_ms": 1,
      "face_emotion_ms": 97,
      "fusion_render_ms": 4,
      "total_ms": 2095
    }
  },

  "emotion": {
    "code": "sad",
    "label": "悲伤",
    "sources": {
      "text": "sad",
      "face": "neutral",
      "speech": "sad"
    },
    "weights": {
      "happy": 0.0,
      "sad": 0.7,
      "angry": 0.0,
      "surprise": 0.0,
      "neutral": 0.2,
      "fear": 0.0
    }
  },
  "poem": {
    "poet": "柳宗元",
    "text": "千山鸟飞绝，万径人踪灭。",
    "interpretation": "..."
  },
  "poet_image_url": "/assets/tangsong/柳宗元.png",
  "guochao": {
    "name": "国潮男知书",
    "comfort": "每个人都会有情绪低落的时候..."
  },
  "guochao_image_url": "/assets/guochao/国潮男知书.png"
}
```

Notes:

- `result_card` is the fixed user-facing structure for phase-1 pages/history/email.
- `system_fields` contains internal metadata for history/trend/observability (BE-003).
- `emotion/poem/guochao` are legacy-compatible fields for existing clients.

### 2.1) Async analyze (recommended for real-device stability)

To avoid frontend timeout on heavy inputs (`text + selfie + voice + ASR`), use async flow:

1. `POST /api/analyze/async` to create task
2. poll `GET /api/analyze/async/{task_id}`
3. when `status=succeeded`, read `result` and open result page

#### Create task

`POST /api/analyze/async`

Request body is the same as `POST /api/analyze`.

Response example:

```json
{
  "task_id": "atk_5fce3b81d0a1",
  "status": "queued",
  "accepted_at": "2026-03-28T01:00:00Z",
  "poll_after_ms": 2500,
  "status_message": "排队中"
}
```

#### Query task status

`GET /api/analyze/async/{task_id}`

Response when running:

```json
{
  "task_id": "atk_5fce3b81d0a1",
  "status": "running",
  "accepted_at": "2026-03-28T01:00:00Z",
  "started_at": "2026-03-28T01:00:01Z",
  "finished_at": null,
  "poll_after_ms": 2500,
  "status_message": "分析中",
  "retryable": false,
  "error_detail": null,
  "queue_wait_ms": 142,
  "run_elapsed_ms": 18320,
  "total_elapsed_ms": 18462,
  "result": null
}
```

### 2.2) Media generate task (phase-3 M2/M3 baseline)

Used for user-triggered media enhancement task (style: tech/guochao).  
Current provider baseline is static asset pool; third-party dynamic providers are removed.

Flow:

1. `POST /api/media-generate` create async task
2. poll `GET /api/media-generate/{task_id}`
3. when `status=succeeded`, read `result.generated_image_url`

#### Create task

`POST /api/media-generate`

Request body fields:

- `request_token` optional idempotency token
- `analysis_request_id` optional trace id
- `style` required: `classical | tech | guochao`
- `emotion_code` optional primary emotion code for pool matching
- `emotion_label` optional primary emotion label for pool matching
- `trigger_tags` optional string array for pool matching
- `consent_confirmed` required when `MEDIA_GEN_REQUIRE_CONSENT=1` (default enabled)
- `consent_version` optional text
- `source_image` / `source_image_url` / `source_image_file_id` / `source_image_path` optional (ignored in static-pool mode)

Important:

- call must carry WeChat identity (`x-wx-openid` or `x-wx-unionid`), otherwise returns `401`
- default hard constraints:
  - weekly quota (per user per ISO week)
  - points check and deduction
  - failure rollback for deducted points and consumed quota
- static-pool mode does not call third-party generation providers

Create response example:

```json
{
  "task_id": "mgt_9a01fbe3c4d2",
  "status": "queued",
  "accepted_at": "2026-03-29T12:50:00Z",
  "poll_after_ms": 2200,
  "status_message": "排队中"
}
```

#### Query task status

`GET /api/media-generate/{task_id}`

Succeeded example:

```json
{
  "task_id": "mgt_9a01fbe3c4d2",
  "status": "succeeded",
  "accepted_at": "2026-03-29T12:50:00Z",
  "started_at": "2026-03-29T12:50:01Z",
  "finished_at": "2026-03-29T12:50:02Z",
  "poll_after_ms": 2200,
  "status_message": "选图完成",
  "retryable": false,
  "error_code": null,
  "error_detail": null,
  "result": {
    "generated_image_url": "https://<your-cdn-domain>/emotion/tech/tech_001.jpg",
    "generated_image_file_id": null,
    "provider": "static_pool",
    "style": "tech",
    "generated_at": "2026-03-29T12:50:02Z"
  }
}
```

Failure example:

```json
{
  "task_id": "mgt_xxx",
  "status": "failed",
  "status_message": "选图失败",
  "retryable": false,
  "error_code": "MEDIA_GEN_POOL_EMPTY",
  "error_detail": "MEDIA_GEN_STATIC_POOL_EMPTY: no static assets configured for selected style"
}
```

Hard-constraint error examples:

- `403 MEDIA_GEN_CONSENT_REQUIRED: user consent must be confirmed before generation`
- `429 MEDIA_GEN_WEEKLY_LIMIT_EXCEEDED: week=2026-W13, limit=1`
- `402 MEDIA_GEN_POINTS_INSUFFICIENT: need=1, current=0`

Provider env quick notes:

- `MEDIA_GEN_PROVIDER=local_mock|static_pool`
- Third-party dynamic providers (`qwen`/`hunyuan`/`liblib`/generic `http`) were removed from current codebase.
- If `MEDIA_GEN_PROVIDER` is set to any removed provider, API returns:
  - `MEDIA_GEN_PROVIDER_DISABLED: third-party dynamic image providers are removed; please use MEDIA_GEN_PROVIDER=local_mock`
- `MEDIA_GEN_STATIC_POOL_CLASSICAL` / `MEDIA_GEN_STATIC_POOL_TECH` / `MEDIA_GEN_STATIC_POOL_GUOCHAO`: comma-separated static references (recommend COS/CDN URLs).
- `MEDIA_GEN_STATIC_POOL_CLASSICAL_JSON` / `MEDIA_GEN_STATIC_POOL_TECH_JSON` / `MEDIA_GEN_STATIC_POOL_GUOCHAO_JSON`: JSON array form of static references.
  - each JSON item can be either a plain string URL or an object:
    - `id`
    - `url`
    - `style`
    - `emotion_tags`
    - `intensity`
    - `active`
    - `weight`
    - `updated_at`
- optional common fallback pool:
  - `MEDIA_GEN_STATIC_POOL_COMMON`
  - `MEDIA_GEN_STATIC_POOL_COMMON_JSON`
- If static pool env not configured, backend fallback uses local `/assets/tangsong/*` for `classical`, `/assets/guochao/*` for `guochao`; `tech` requires explicit tech pool config or returns `MEDIA_GEN_STATIC_POOL_EMPTY`.
- M2 hard-constraint env:
  - `MEDIA_GEN_REQUIRE_CONSENT=1`
  - `MEDIA_GEN_ENABLE_WEEKLY_QUOTA=1`
  - `MEDIA_GEN_WEEKLY_LIMIT=1`
  - `MEDIA_GEN_ENABLE_POINTS=1`
  - `MEDIA_GEN_POINTS_COST=1`
  - `MEDIA_GEN_PROVIDER_MAX_RETRIES=1`
  - `MEDIA_GEN_PROVIDER_RETRY_BACKOFF_MS=220`

Timing fields note:

- `system_fields.processing_metrics_ms`: backend stage timing breakdown (ms) for completed analysis.
- `queue_wait_ms`: time from task accepted to task started.
- `run_elapsed_ms`: time spent in running stage.
- `total_elapsed_ms`: total time from accepted to current/finished status.

Response when succeeded:

```json
{
  "task_id": "atk_5fce3b81d0a1",
  "status": "succeeded",
  "accepted_at": "2026-03-28T01:00:00Z",
  "started_at": "2026-03-28T01:00:01Z",
  "finished_at": "2026-03-28T01:00:08Z",
  "poll_after_ms": 1200,
  "status_message": "分析完成",
  "retryable": false,
  "error_detail": null,
  "result": {
    "...": "same payload as POST /api/analyze response"
  }
}
```

Response when failed:

```json
{
  "task_id": "atk_5fce3b81d0a1",
  "status": "failed",
  "accepted_at": "2026-03-28T01:00:00Z",
  "started_at": "2026-03-28T01:00:01Z",
  "finished_at": "2026-03-28T01:00:05Z",
  "poll_after_ms": 1200,
  "status_message": "分析失败",
  "retryable": false,
  "error_detail": "[VOICE_TRANSCRIPT_EMPTY] ...",
  "result": null
}
```

## 3) Send analysis email

`POST /api/send-email`

Request body fields:

- `to_email` required string
- `analysis_request_id` optional string (used to mark mail-sent state in history)
- `thoughts` optional string
- `poem_text` optional string
- `comfort_text` optional string
- `user_image_file_id` optional string (`cloud://...` or `https://...`)
- `poet_image_file_id` optional string (`cloud://...` or `https://...`)
- `guochao_image_file_id` optional string (`cloud://...` or `https://...`)
- `user_audio_file_id` optional string (`cloud://...` or `https://...`, attached in email)
- `user_image_path`/`poet_image_path`/`guochao_image_path` optional local debug paths
- `user_audio_path` optional local debug path

Example:

```json
{
  "to_email": "user@example.com",
  "analysis_request_id": "ana_2f3c0cfa5c53",
  "thoughts": "今天有点难过",
  "poem_text": "千山鸟飞绝，万径人踪灭。",
  "comfort_text": "每个人都会有情绪低落的时候...",
  "user_image_file_id": "cloud://env-id/path/user_photo.jpg",
  "user_audio_file_id": "cloud://env-id/path/user_audio.mp3"
}
```

Response:

```json
{
  "request_id": "mail_f4a12bc39d10",
  "success": true,
  "message": "邮件发送成功！",
  "error_code": null,
  "retryable": false
}
```

Failure example (still HTTP 200, frontend retries only this endpoint):

```json
{
  "request_id": "mail_8f02f6d117ab",
  "success": false,
  "message": "邮件发送失败：SMTP服务器意外断开连接。",
  "error_code": "EMAIL_NETWORK_ERROR",
  "retryable": true
}
```

## 4) Built-in Tencent STT gateway (internal endpoint)

`POST /api/stt/tencent`

Purpose:

- This endpoint is used by backend STT adapter (`SPEECH_STT_ENDPOINT`) when `SPEECH_ASR_SERVICE=on`; it is not required for mini program direct calls.
- It wraps Tencent SentenceRecognition API with server-side credential signing.

Request:

- `multipart/form-data`
- file field supports `audio` / `file` / `voice`

Response example:

```json
{
  "text": "今天有点难过",
  "provider": "tencent_asr",
  "request_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "audio_duration_ms": 2380
}
```

Security recommendation:

- Configure `TENCENT_STT_GATEWAY_TOKEN` and set the same value through `SPEECH_STT_HEADERS_JSON` as `X-STT-GATEWAY-TOKEN`.
- Mini program production launch requirement: this token must be configured before go-live, otherwise the STT gateway is exposed to public abuse risk.

## 5) History APIs

`GET /api/history?limit=20&offset=0`

Response:

```json
{
  "items": [
    {
      "history_id": "his_abc123",
      "request_id": "ana_2f3c0cfa5c53",
      "analyzed_at": "2026-03-26T08:30:00Z",
      "input_modes": ["text", "selfie"],
      "primary_emotion": { "code": "sad", "label": "悲伤" },
      "secondary_emotions": [{ "code": "neutral", "label": "平静" }],
      "emotion_overview_summary": "综合文本、图像信号，当前以“悲伤”为主。",
      "trigger_tags": ["学业压力"],
      "poem_response_summary": "千山鸟飞绝，万径人踪灭。",
      "guochao_name": "国潮男知书",
      "daily_suggestion_summary": "给自己 10 分钟安静时间...",
      "mail_sent": true
    }
  ],
  "total": 1
}
```

`GET /api/history/{history_id}`

Response includes `summary + result_card + internal_fields` for detail replay.

`DELETE /api/history/{history_id}`

Delete one history summary record for current user.

`DELETE /api/history`

Clear all history summary records for current user.

## 6) Retention APIs (phase-2 base)

`GET /api/retention/calendar?month=2026-03`

- `month` optional, format `YYYY-MM`
- if omitted, backend returns current month

Response example:

```json
{
  "month": "2026-03",
  "month_start": "2026-03-01",
  "month_end": "2026-03-31",
  "total_days": 31,
  "checked_days": 8,
  "checked_today": true,
  "current_streak": 3,
  "longest_streak": 5,
  "items": [
    {
      "date": "2026-03-27",
      "has_checkin": true,
      "analyzed_at": "2026-03-27T11:20:35Z",
      "primary_emotion": { "code": "sad", "label": "悲伤" },
      "analyses_count": 2,
      "input_modes": ["text", "voice"]
    }
  ]
}
```

`GET /api/retention/weekly-report?week_start=2026-03-23`

- `week_start` optional, format `YYYY-MM-DD`
- backend will normalize to Monday of that week
- if omitted, backend returns current week report

Response example:

```json
{
  "week_start": "2026-03-23",
  "week_end": "2026-03-29",
  "generated_at": "2026-03-27T12:00:00Z",
  "total_checkin_days": 4,
  "checked_today": true,
  "current_streak": 3,
  "dominant_emotions": [
    { "code": "sad", "label": "悲伤", "days": 2 },
    { "code": "neutral", "label": "平静", "days": 2 }
  ],
  "top_trigger_tags": [
    { "tag": "学业压力", "count": 3 }
  ],
  "suggestion_highlights": [
    "给自己 10 分钟安静时间..."
  ],
  "daily_digests": [],
  "insight": "本周你有 4 天完成记录，主情绪偏向「悲伤」，高频触发因素是「学业压力」。",
  "source": "generated"
}
```

`source` may be:

- `generated`: computed on this request
- `cache`: loaded from per-user weekly report cache

Privacy boundary for retention statistics:

- `calendar.items[].analyzed_at` and `weekly_report.daily_digests[].analyzed_at` are returned as `null` to avoid exporting precise behavior timestamps.
- Retention APIs only expose aggregate/digest fields and do not include internal request ids.

Feature-flag guard:

- If `RETENTION_SERVICE_ENABLED=off`, retention APIs return `503` with `[RETENTION_SERVICE_DISABLED]`.
- If `RETENTION_WEEKLY_REPORT_ENABLED=off`, weekly report API returns `503` with `[RETENTION_WEEKLY_REPORT_DISABLED]`.

Retention management extensions:

- `GET /api/retention/write-settings`
  - returns `{ "write_enabled": true|false, "updated_at": "..." }`
- `PUT /api/retention/write-settings`
  - request body: `{ "write_enabled": true|false }`
  - controls whether new retention writes are allowed for the current user
- `DELETE /api/retention/weekly-report?week_start=YYYY-MM-DD`
  - deletes one weekly report snapshot cache for current user
- `DELETE /api/retention/weekly-reports`
  - clears all weekly report snapshots for current user
- `DELETE /api/retention/favorites?favorite_type=poem|guochao`
  - clears favorites for current user (all types when omitted)

## 7) Favorites APIs (phase-2 base)

`GET /api/favorites?favorite_type=poem&limit=20&offset=0`

- `favorite_type` optional: `poem | guochao`

Response:

```json
{
  "items": [
    {
      "favorite_id": "fav_abc123",
      "favorite_type": "poem",
      "target_id": "poem_8f65f3de1a3b",
      "title": "千山鸟飞绝，万径人踪灭。",
      "subtitle": "柳宗元",
      "content_summary": "综合文本、图像信号...",
      "created_at": "2026-03-27T12:10:00Z",
      "updated_at": "2026-03-27T12:10:00Z"
    }
  ],
  "total": 1
}
```

`GET /api/favorites/status?favorite_type=poem&target_id=poem_8f65f3de1a3b`

```json
{
  "is_favorited": true,
  "item": { "...": "..." }
}
```

`POST /api/favorites`

```json
{
  "favorite_type": "poem",
  "target_id": "poem_8f65f3de1a3b",
  "title": "千山鸟飞绝，万径人踪灭。",
  "subtitle": "柳宗元",
  "content_summary": "综合文本、图像信号...",
  "request_id": "ana_2f3c0cfa5c53",
  "metadata": {}
}
```

`request_id` / `metadata` 仅作为写入侧上下文，出于隐私边界不会在收藏查询接口中回传。

Response:

```json
{
  "success": true,
  "created": true,
  "item": { "...": "..." },
  "message": "已加入收藏。"
}
```

`DELETE /api/favorites/{favorite_id}`

`DELETE /api/favorites?favorite_type=poem`

Feature-flag guard:

- If `RETENTION_FAVORITES_ENABLED=off`, favorites APIs return `503` with `[RETENTION_FAVORITES_DISABLED]`.

## 8) Settings APIs

`GET /api/settings`

```json
{
  "save_history": true,
  "history_retention_days": 180,
  "updated_at": "2026-03-26T08:40:00Z"
}
```

`PUT /api/settings`

```json
{
  "save_history": false
}
```

## 9) Today History API

`GET /api/today-history?date=2026-04-11`

- `date` optional, format `YYYY-MM-DD`
- if omitted, backend uses current date

Response example:

```json
{
  "date": "2026-04-11",
  "month_day": "04-11",
  "available": true,
  "collapsed_default": true,
  "status": "ok",
  "status_message": "可展开查看",
  "cache_hit": false,
  "entry": {
    "month_day": "04-11",
    "event_year": "1970",
    "headline": "阿波罗 13 号从佛罗里达发射升空",
    "summary": "1970 年 4 月 11 日，阿波罗 13 号自肯尼迪航天中心发射...",
    "optional_note": "很多历史节点并不按计划发生，却常常因临场应对而被记住。",
    "source_label": "历史资料"
  }
}
```

Response status semantics:

- `ok`: live or seed content available
- `degraded`: current request fell back to cached content
- `empty`: no safe content available for this date
- `filtered`: content was suppressed by moderation rules

Content-layer semantics:

- `entry.summary`: factual layer only (historical fact summary)
- `entry.optional_note`: optional companion layer (light emotional copy); may be empty on sensitive or strictly factual outputs

Feature-flag guard:

- If `TODAY_HISTORY_ENABLED=off`, API returns `503` with `[TODAY_HISTORY_DISABLED]`.

## 10) Error codes

- `200`: success
- `400`: bad request / missing env / invalid file id / resolver failure
- `409`: retention write disabled for current user (for example favorites upsert)
- `422`: schema validation error
- `500`: internal server error
- `503`: feature disabled by admin config (retention/week report/favorites/today-history)

Voice quality reject details (`400`, from BE-011):

- `[VOICE_TOO_SHORT]`: voice file too short / too quiet
- `[VOICE_TRANSCRIPT_EMPTY]`: transcript empty (only when `VOICE_REQUIRE_TRANSCRIPT=1`)
- `[VOICE_TEXT_TOO_SHORT]`: recognized text too short
- `[VOICE_TEXT_UNSTABLE]`: unstable transcript, suggest re-record in quieter environment
- For `[VOICE_TRANSCRIPT_EMPTY]`, response detail includes current config/status context (for example `VOICE_REQUIRE_TRANSCRIPT=1`, `ASR状态=provider_unconfigured/service_disabled`) to distinguish config issues from user recording issues.

`system_fields.speech_transcript_status` can be used for diagnosis:

- `ok`: transcript available
- `empty`: STT responded but transcript empty
- `service_disabled`: ASR disabled by admin config (`SPEECH_ASR_SERVICE=off`)
- `provider_unconfigured`: endpoint not configured
- `request_failed`: STT HTTP request failed
- `runtime_error`: unexpected STT runtime error

Retention write guard details (`409`):

- `[RETENTION_WRITE_DISABLED]`: current user has disabled retention write; reads/deletes are still allowed.

Email error codes (`/api/send-email` response fields):

- `EMAIL_CONFIG_INVALID`: missing/invalid SMTP config, usually not retryable
- `EMAIL_AUTH_FAILED`: sender auth failed, not retryable until config fixed
- `EMAIL_NETWORK_ERROR`: transient network/server issue, retryable
- `EMAIL_UNKNOWN_ERROR`: unexpected runtime issue, retryable
- `EMAIL_SERVICE_ERROR`: endpoint-level exception fallback, retryable

Face quality reject details (`400`, from BE-012):

- `[FACE_NOT_FOUND]`: no clear face detected
- `[FACE_MULTI_FOUND]`: multiple faces detected
- `[FACE_TOO_SMALL]`: face region too small / too far from camera
- `[FACE_TOO_DARK]`: low-light image
- `[FACE_TOO_BLUR]`: blurred image

## 11) Frontend integration flow (recommended)

1. Upload media from mini program via `wx.cloud.uploadFile`, keep returned `fileID` and `tempFileURL`.
2. Call `/api/analyze` with `text + image/audio` via `wx.cloud.callContainer`.
3. Render `result_card` as primary UI payload.
4. If user sends email, call `/api/send-email` via `wx.cloud.callContainer`.

## 12) Minimal mini program request snippet

```js
wx.cloud.callContainer({
  config: {
    env: CLOUD_ENV,
  },
  path: "/api/analyze",
  method: "POST",
  header: {
    "X-WX-SERVICE": CONTAINER_SERVICE,
    "content-type": "application/json",
  },
  data: {
    input_modes: ["text", "selfie"],
    text: textValue,
    image: {
      url: imageTempUrl,
      file_id: imageFileId,
    },
    client: { platform: "mp-weixin", version: "1.0.0" },
  },
  success(res) {
    console.log("analyze ok", res.data);
  },
  fail(err) {
    console.error("analyze fail", err);
  },
});
```

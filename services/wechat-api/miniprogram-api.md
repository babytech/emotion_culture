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

- Mini program uses WeChat natural identity as primary user id (`x-wx-openid` injected by cloud hosting gateway).
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
    "speech_transcript_error": null
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

Feature-flag guard:

- If `RETENTION_SERVICE_ENABLED=off`, retention APIs return `503` with `[RETENTION_SERVICE_DISABLED]`.
- If `RETENTION_WEEKLY_REPORT_ENABLED=off`, weekly report API returns `503` with `[RETENTION_WEEKLY_REPORT_DISABLED]`.

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
      "request_id": "ana_2f3c0cfa5c53",
      "created_at": "2026-03-27T12:10:00Z",
      "updated_at": "2026-03-27T12:10:00Z",
      "metadata": {}
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

## 9) Error codes

- `200`: success
- `400`: bad request / missing env / invalid file id / resolver failure
- `422`: schema validation error
- `500`: internal server error
- `503`: feature disabled by admin config (retention/week report/favorites)

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

## 10) Frontend integration flow (recommended)

1. Upload media from mini program via `wx.cloud.uploadFile`, keep returned `fileID` and `tempFileURL`.
2. Call `/api/analyze` with `text + image/audio` via `wx.cloud.callContainer`.
3. Render `result_card` as primary UI payload.
4. If user sends email, call `/api/send-email` via `wx.cloud.callContainer`.

## 11) Minimal mini program request snippet

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

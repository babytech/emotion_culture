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
    "speech_transcript_provider": "http"
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
- `user_image_path`/`poet_image_path`/`guochao_image_path` optional local debug paths

Example:

```json
{
  "to_email": "user@example.com",
  "analysis_request_id": "ana_2f3c0cfa5c53",
  "thoughts": "今天有点难过",
  "poem_text": "千山鸟飞绝，万径人踪灭。",
  "comfort_text": "每个人都会有情绪低落的时候...",
  "user_image_file_id": "cloud://env-id/path/user_photo.jpg"
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

## 4) History APIs

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

## 5) Settings APIs

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

## 6) Error codes

- `200`: success
- `400`: bad request / missing env / invalid file id / resolver failure
- `422`: schema validation error
- `500`: internal server error

Voice quality reject details (`400`, from BE-011):

- `[VOICE_TOO_SHORT]`: voice file too short / too quiet
- `[VOICE_TRANSCRIPT_EMPTY]`: transcript empty (silent/noisy input)
- `[VOICE_TEXT_TOO_SHORT]`: recognized text too short
- `[VOICE_TEXT_UNSTABLE]`: unstable transcript, suggest re-record in quieter environment

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

## 7) Frontend integration flow (recommended)

1. Upload media from mini program via `wx.cloud.uploadFile`, keep returned `fileID` and `tempFileURL`.
2. Call `/api/analyze` with `text + image/audio` via `wx.cloud.callContainer`.
3. Render `result_card` as primary UI payload.
4. If user sends email, call `/api/send-email` via `wx.cloud.callContainer`.

## 8) Minimal mini program request snippet

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

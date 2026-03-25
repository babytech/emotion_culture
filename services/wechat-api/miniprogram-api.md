# Mini Program API Contract

This document is for WeChat mini program frontend integration with `services/wechat-api`.

Runtime note:

- Backend is self-contained under `services/wechat-api/app/core` and does not require `apps/pc` at deploy time.

## Access mode (recommended)

Use `wx.cloud.callContainer` from mini program frontend.

- `config.env`: your cloud environment id
- Header `X-WX-SERVICE`: your cloud hosting service name
- `path`: backend path (for example `/api/analyze`)

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

## 3) Send analysis email

`POST /api/send-email`

Request body fields:

- `to_email` required string
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
  "thoughts": "今天有点难过",
  "poem_text": "千山鸟飞绝，万径人踪灭。",
  "comfort_text": "每个人都会有情绪低落的时候...",
  "user_image_file_id": "cloud://env-id/path/user_photo.jpg"
}
```

Response:

```json
{
  "success": true,
  "message": "邮件发送成功！"
}
```

## 4) Error codes

- `200`: success
- `400`: bad request / missing env / invalid file id / resolver failure
- `422`: schema validation error
- `500`: internal server error

## 5) Frontend integration flow (recommended)

1. Upload media from mini program via `wx.cloud.uploadFile`, keep returned `fileID` and `tempFileURL`.
2. Call `/api/analyze` with `text + image/audio` via `wx.cloud.callContainer`.
3. Render returned emotion/poem/comfort data.
4. If user sends email, call `/api/send-email` via `wx.cloud.callContainer`.

## 6) Minimal mini program request snippet

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

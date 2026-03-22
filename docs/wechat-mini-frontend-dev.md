# WeChat Mini Frontend Dev Guide

## 1. Configure backend

Backend location:

- `/Users/babytech/github/emotion_culture/services/wechat-api`

Run backend:

```bash
cd /Users/babytech/github/emotion_culture/services/wechat-api
../../.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 9000
```

If mini program uploads `cloud://` file IDs, configure:

- `WECHAT_APP_ID`
- `WECHAT_APP_SECRET`
- `WECHAT_CLOUDBASE_ENV`

## 2. Configure mini program

Frontend location:

- `/Users/babytech/github/emotion_culture/apps/wechat-mini`

Edit:

- `/Users/babytech/github/emotion_culture/apps/wechat-mini/config/index.js`

Set:

- `apiBaseUrl`
- `cloudEnv`

## 3. Request domain and cloud

In WeChat mini program settings:

- Add backend domain to request legal domain list.
- Enable cloud development and keep `cloudEnv` consistent.

## 4. Main flow

1. User inputs text / image / audio on `/pages/index`.
2. Frontend uploads media with `wx.cloud.uploadFile`.
3. Frontend sends `fileID` to `/api/analyze`.
4. Result page shows emotion + poem + comfort.
5. Optional: send email through `/api/send-email`.

## 5. Troubleshooting

- `400 missing required env var: WECHAT_CLOUDBASE_ENV`
  - Backend env not set, but request includes `cloud://...`.
- `分析失败` on frontend
  - Check `apiBaseUrl` and backend process status.
- Upload fails in mini program
  - Verify cloud permission and `cloudEnv` value.

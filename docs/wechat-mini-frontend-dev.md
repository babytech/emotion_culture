# WeChat Mini Frontend Dev Guide

## 1. Prepare backend service

Backend location:

- `/Users/babytech/github/emotion_culture/services/wechat-api`

Recommended for mini program integration:

- Deploy backend to WeChat Cloud Hosting.
- Keep service name consistent (for example `emotion-culture-api`).
- Set required env vars in Cloud Hosting service settings:
  - `WECHAT_APP_ID`
  - `WECHAT_APP_SECRET`
  - `WECHAT_CLOUDBASE_ENV`
- If email sending is enabled, also set SMTP env vars there.

Optional local backend run (browser/manual debug only):

```bash
cd /Users/babytech/github/emotion_culture/services/wechat-api
../../.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 9000
```

## 2. Configure mini program

Frontend location:

- `/Users/babytech/github/emotion_culture/apps/wechat-mini`

Edit:

- `/Users/babytech/github/emotion_culture/apps/wechat-mini/config/index.js`

Set:

- `cloudEnv`: Cloud Development env id (for `wx.cloud.uploadFile`)
- `containerEnv`: Cloud Hosting env id (for `wx.cloud.callContainer`)
- `containerService`: Cloud Hosting service name
- `apiBaseUrl` (optional): only for resolving relative `/assets/...` image links

## 3. Domain and cloud settings

- Enable cloud development in WeChat DevTools.
- Keep env ids in config consistent with actual deployment.
- API requests now use `wx.cloud.callContainer`, so no `request` legal-domain configuration is required for `/api/*` calls.

## 4. Main flow

1. User inputs text / image / audio on `/pages/index`.
2. Frontend uploads media with `wx.cloud.uploadFile`.
3. Frontend calls container service `/api/analyze` via `wx.cloud.callContainer`.
4. Result page shows emotion + poem + comfort.
5. Optional: send email through `/api/send-email`.

## 5. Troubleshooting

- `wx.cloud.callContainer is unavailable`
  - Check mini program base library version and cloud init in `app.js`.
- `INVALID_HOST` on callContainer
  - Check `containerEnv` and `containerService` first.
- API call fails with service/env errors
  - Verify Cloud Hosting service is running and reachable by cloud call.
- `400 missing required env var: WECHAT_CLOUDBASE_ENV`
  - Backend env not set, but request includes `cloud://...`.
- Relative image URL cannot load
  - Verify `apiBaseUrl` points to your cloud hosting domain and backend static route works.

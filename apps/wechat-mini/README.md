# WeChat Mini Program Frontend

This is the mini program frontend for `services/wechat-api`.

## Structure

- `pages/index`: text/image/audio input and analyze submit
- `pages/result`: result rendering and optional email send
- `services/api.js`: backend request wrapper
- `services/cloud.js`: cloud upload helper (`wx.cloud.uploadFile`)
- `config/index.js`: local config (`apiBaseUrl`, `cloudEnv`)

## Run in WeChat DevTools

1. Open WeChat DevTools.
2. Import this folder as project root:
   - `/Users/babytech/github/emotion_culture/apps/wechat-mini`
3. Set your own appid in `project.config.json`.
4. Update `config/index.js`:
   - `apiBaseUrl` to your backend address
   - `cloudEnv` to your cloud env id
5. Ensure cloud development is enabled and permissions allow upload.

## Backend dependency

Required backend endpoints:

- `POST /api/analyze`
- `POST /api/send-email`
- `GET /api/health`

Contract doc:

- `/Users/babytech/github/emotion_culture/services/wechat-api/miniprogram-api.md`

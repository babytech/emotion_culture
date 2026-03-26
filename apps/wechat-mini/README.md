# WeChat Mini Program Frontend

This is the mini program frontend for `services/wechat-api`.

## Structure

- `pages/index`: text/image/audio input and analyze submit
- `pages/result`: result rendering and optional email send
- `pages/history`: history list and detail replay
- `pages/settings`: save-history toggle and privacy/help entry
- `services/api.js`: backend request wrapper (`wx.cloud.callContainer`)
- `services/cloud.js`: cloud upload helper (`wx.cloud.uploadFile`)
- `config/index.js`: local config (`cloudEnv`, `containerEnv`, `containerService`, optional `apiBaseUrl`)

## Run in WeChat DevTools

1. Open WeChat DevTools.
2. Import this folder as project root:
   - `/Users/babytech/github/emotion_culture/apps/wechat-mini`
3. Set your own appid in `project.config.json`.
4. Update `config/index.js`:
   - `cloudEnv`: WeChat Cloud Development env id (upload/storage)
   - `containerEnv`: Cloud Hosting env id (for `callContainer`)
   - `containerService`: Cloud Hosting service name (for example `emotion-culture-api`)
   - `apiBaseUrl` (optional): only used to resolve relative `/assets/...` image URLs
5. Ensure cloud development is enabled and env ids are correct.

## Backend dependency

Required backend endpoints:

- `POST /api/analyze`
- `POST /api/send-email`
- `GET /api/history`
- `GET /api/history/{history_id}`
- `DELETE /api/history/{history_id}`
- `DELETE /api/history`
- `GET /api/settings`
- `PUT /api/settings`
- `GET /api/health`

Contract doc:

- `/Users/babytech/github/emotion_culture/services/wechat-api/miniprogram-api.md`

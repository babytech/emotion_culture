# emotion_culture - English Overview

## 1. Project Summary

`emotion_culture` is a youth-oriented emotional companion project (non-medical, non-diagnostic).
It turns multi-modal inputs (text / selfie / voice) into structured emotional feedback, then presents cultural responses (poem, interpretation, guochao comfort content) for reflection, retention, and sharing.

This repository includes:

- WeChat Mini Program frontend: `apps/wechat-mini`
- FastAPI backend: `services/wechat-api`
- PC Gradio client: `apps/pc`

---

## 2. Repository Structure

```text
emotion_culture/
├── apps/
│   ├── wechat-mini/                  # Mini Program UI and client logic
│   │   ├── pages/
│   │   ├── services/
│   │   ├── utils/
│   │   ├── app.json
│   │   └── README.md
│   └── pc/                           # Gradio desktop/web client
│       ├── main.py
│       ├── ui.py
│       ├── emotion.py
│       ├── speech.py
│       └── culture.py
├── services/
│   └── wechat-api/                   # FastAPI backend and API schemas
│       ├── app/
│       │   ├── api/
│       │   ├── services/
│       │   ├── schemas/
│       │   └── core/
│       ├── main.py
│       ├── miniprogram-api.md
│       └── README.md
├── docs/
│   ├── product-consensus.md
│   ├── mini-program-followup-plan.md
│   ├── wechat-mini-frontend-dev.md
│   └── stage1/                       # Phase1~Phase5 docs (plans/checklists/QA/acceptance)
├── tools/                            # Phase regression and benchmark scripts
└── README*.md
```

---

## 3. Supported Features

## 3.1 WeChat Mini Program (`apps/wechat-mini`)

### Auth and Identity

- Privacy-first auth entry page (`pages/auth-entry`)
- Explicit privacy authorization, then enter with current WeChat identity
- User binding strategy built around `openid / unionid`

### Analyze Workspace (`pages/analyze`)

- Input modes:
  - Text
  - Selfie (front camera, permission + quality checks)
  - Voice recording (permission + duration/format checks)
- Processing flow:
  - Upload media via CloudBase
  - Create async analyze task + poll status
  - Weak-network retry and pending-task recovery

### Result Page (`pages/result`)

- Structured result output:
  - Primary/secondary emotions
  - Emotion overview
  - Trigger tags
  - Poem response + interpretation
  - Guochao comfort + daily suggestion
- Actions:
  - Send email
  - Add/remove favorites (poem/guochao)
  - Style image switching (classical / tech / guochao, async task)
  - Shortcuts to home/journey/calendar/report/favorites

### Home and Journey

- Home (`pages/home`):
  - Recent history snapshot
  - Weekly insight summary
  - Favorites preview
  - “Today in History” collapsible panel
- Journey (`pages/journey`):
  - History hub and navigation
  - Weekly/calendar entry
  - “Today in History” linked experience

### Share (`pages/share`)

- Canvas-based share card generation
- Supports:
  - Preview generated image
  - Save to album
  - Share to WeChat friends (`onShareAppMessage`)
  - Share current page to Moments (`onShareTimeline`)

### Other Pages

- History list/detail: `pages/history`
- Favorites: `pages/favorites`
- Calendar: `pages/calendar`
- Weekly report: `pages/report`
- Profile: `pages/profile`
- Legacy-compatible pages: `pages/index`, `pages/settings`, `pages/style`

---

## 3.2 PC Client (`apps/pc`)

The PC app is a Gradio-based client focused on desktop testing and companion usage:

- Multi-modal input:
  - Text input
  - Microphone voice input
  - Camera selfie capture + confirm before analyze
- Emotion fusion:
  - Text + face + voice signal fusion
  - Poem and guochao comfort output
- Quality controls:
  - Face quality gate (multi-face/blur/dark/small-face rejection)
  - Voice validity checks
- History and review:
  - Local lightweight history cache
  - History detail and mail-sent status update
- Optional backend bridge:
  - Retention trend, weekly report, and favorites panel via backend API
- Email export:
  - Send current analysis result to email
- Optional TTS playback after analysis

---

## 3.3 Backend (`services/wechat-api`)

FastAPI backend with major domains:

- Analyze: `/api/analyze`, `/api/analyze/async*`
- Bootstrap/Auth: `/api/bootstrap`, `/api/auth/*`
- History: `/api/history*`
- Retention/Reports: `/api/retention/*`, `/api/retention/weekly-report`
- Favorites: `/api/favorites*`
- Email: `/api/send-email`
- STT gateway: `/api/stt/tencent`
- Media generate task: `/api/media-generate*`
- Today history: `/api/today-history`

Implementation highlights:

- User identity resolved primarily from WeChat headers (`x-wx-unionid` / `x-wx-openid`)
- Async queue + polling for analyze and media-generate flows
- “Today in History” with provider + caching + moderation + safe fallback
- Media generation governance via consent, weekly quota, and points switches

---

## 4. Local Development

## 4.1 Backend

```bash
cd services/wechat-api
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 9000
```

- Swagger: `http://127.0.0.1:9000/docs`
- Health: `http://127.0.0.1:9000/api/health`

## 4.2 WeChat Mini Program

1. Import `apps/wechat-mini` in WeChat DevTools.
2. Configure `apps/wechat-mini/config/index.js`:
   - `cloudEnv`
   - `containerEnv`
   - `containerService`
   - `apiBaseUrl` (optional)
3. Keep CloudBase and Cloud Hosting env configuration consistent.

References:

- [apps/wechat-mini/README.md](./apps/wechat-mini/README.md)
- [docs/wechat-mini-frontend-dev.md](./docs/wechat-mini-frontend-dev.md)

## 4.3 PC Client

```bash
cd apps/pc
python main.py
```

The app attempts to launch on `8080` with fallback port scanning.

---

## 5. Documentation Index

- Product consensus: `docs/product-consensus.md`
- Stage documents index (Phase1~Phase5): `docs/stage1/README.md`
- Mini API contract: `services/wechat-api/miniprogram-api.md`
- Backend runtime notes: `services/wechat-api/README.md`

---

## 6. Notes

- This project is an emotional companion tool, not a medical diagnosis/treatment system.
- README layout in this repository:
  - Landing page: `README.md`
  - Chinese detailed doc: `README_cn.md`
  - English detailed doc: `README_en.md`

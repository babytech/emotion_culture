# emotion_culture

Emotion Culture is a multi-end emotion companion project focused on youth-oriented, non-medical emotional support.
It combines:

- WeChat Mini Program frontend (`apps/wechat-mini`)
- FastAPI backend service (`services/wechat-api`)
- PC Gradio client (`apps/pc`)

The product output is centered on structured emotion feedback with poem response, interpretation, and guochao-style comforting content.

## Read In Your Language

- 中文详细介绍: [README_cn.md](./README_cn.md)
- English detailed introduction: [README_en.md](./README_en.md)

## Project Links

- WeChat Mini API contract: [services/wechat-api/miniprogram-api.md](./services/wechat-api/miniprogram-api.md)
- Backend service notes: [services/wechat-api/README.md](./services/wechat-api/README.md)
- Mini frontend notes: [apps/wechat-mini/README.md](./apps/wechat-mini/README.md)
- Stage docs index (Phase1~Phase5): [docs/stage1/README.md](./docs/stage1/README.md)
- Product consensus: [docs/product-consensus.md](./docs/product-consensus.md)

## Repository Structure

```text
emotion_culture/
├── apps/
│   ├── wechat-mini/        # WeChat Mini Program (auth gate, analyze, result, share, retention pages)
│   └── pc/                 # PC Gradio app (text/voice/camera analysis + local history)
├── services/
│   └── wechat-api/         # FastAPI backend (analyze, async task, retention, favorites, today-history, media-gen)
├── docs/
│   ├── product-consensus.md
│   ├── mini-program-followup-plan.md
│   └── stage1/             # Phase1~Phase5 plans/checklists/QA/acceptance docs
└── tools/                  # QA and benchmark scripts (phase regression tooling)
```

## Supported Features (High-level)

- WeChat Mini Program:
  - Privacy-first auth entry and WeChat identity-bound usage.
  - Multi-modal analysis workflow (text + selfie + voice), async processing, weak-network recovery.
  - Result export (email), favorites, retention calendar/weekly report, share card generation and social sharing.
  - “Today in History” module with safe fallback/caching strategy.
- PC:
  - Gradio-based text/voice/camera workflow.
  - Local history panel and optional backend retention/favorites bridge.
  - Email export and optional speech playback.

For complete feature matrices and setup details, read:

- [README_cn.md](./README_cn.md)
- [README_en.md](./README_en.md)

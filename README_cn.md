# emotion_culture 项目中文说明

## 1. 项目简介

`emotion_culture` 是一个“青少年情绪文化陪伴”项目，定位为**非医疗、非诊断**的情绪记录与陪伴工具。

项目通过多模态输入（文字 / 自拍 / 语音）生成结构化情绪反馈，并结合诗词回应、诗词解读、国潮慰藉内容，形成可回看、可分享、可留存的体验闭环。

当前代码库包含三部分：

- 微信小程序前端：`apps/wechat-mini`
- FastAPI 后端：`services/wechat-api`
- PC 端 Gradio 客户端：`apps/pc`

---

## 2. 代码目录结构

```text
emotion_culture/
├── apps/
│   ├── wechat-mini/                  # 微信小程序（授权门、首页、记录、分析、结果、分享、收藏、我的）
│   │   ├── pages/
│   │   ├── services/
│   │   ├── utils/
│   │   ├── app.json
│   │   └── README.md
│   └── pc/                           # PC Gradio 应用（文本/语音/摄像头分析 + 本地历史 + 邮件）
│       ├── main.py
│       ├── ui.py
│       ├── emotion.py
│       ├── speech.py
│       └── culture.py
├── services/
│   └── wechat-api/                   # FastAPI 后端（分析、历史、留存、收藏、分享素材、今日历史）
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
│   └── stage1/                       # Phase1~Phase5 全部阶段文档
├── tools/                            # Phase 回归脚本与 benchmark 脚本
└── README*.md
```

---

## 3. 支持的功能

## 3.1 微信小程序（`apps/wechat-mini`）

### 账号与授权

- 首次进入走授权门页（`pages/auth-entry`）
- 显式隐私授权后，使用当前微信身份进入
- 登录态围绕微信身份字段（`openid / unionid`）收口

### 分析工作台（`pages/analyze`）

- 输入模式：
  - 文字输入
  - 前置自拍（含权限申请和拍照质量校验）
  - 录音输入（含权限申请、录音时长/格式校验）
- 上传与分析：
  - 媒体上传到云开发
  - 调用后端异步分析任务（创建任务 + 轮询结果）
  - 弱网重试与中断恢复（含待完成任务恢复）

### 结果页（`pages/result`）

- 显示结构化结果：
  - 主情绪 / 补充情绪
  - 情绪概述
  - 触发标签
  - 诗词回应 + 解读
  - 国潮慰藉 + 每日建议
- 能力动作：
  - 邮件发送
  - 收藏（诗词/国潮）
  - 风格图切换（古典 / 科技 / 国潮，异步任务）
  - 跳转首页/记录/日历/周报/收藏

### 首页与记录页

- 首页（`pages/home`）：
  - 最近记录摘要
  - 周报洞察摘要
  - 收藏预览
  - “历史上的今天”折叠模块
- 记录页（`pages/journey`）：
  - 历史记录入口
  - 周报、日历入口
  - “历史上的今天”联动展示

### 分享页（`pages/share`）

- 基于 Canvas 生成分享卡片
- 支持：
  - 预览生成图
  - 保存到相册
  - 转发给微信好友（`onShareAppMessage`）
  - 当前页分享到朋友圈（`onShareTimeline`）

### 其他业务页

- 历史列表与详情：`pages/history`
- 收藏页：`pages/favorites`
- 日历页：`pages/calendar`
- 周报页：`pages/report`
- 我的页：`pages/profile`
- 旧链路兼容页：`pages/index`、`pages/settings`、`pages/style`

---

## 3.2 PC 端（`apps/pc`）

PC 端是 Gradio Web 应用，定位为桌面调试与体验补充端，核心能力包括：

- 多模态输入：
  - 文字输入
  - 麦克风语音输入
  - 摄像头拍照并确认后分析
- 情绪融合分析：
  - 文本情绪 + 人脸情绪 + 语音情绪融合
  - 输出诗词、国潮慰藉、行动建议
- 质量与稳定性：
  - 自拍质量校验（多人/模糊/过暗/人脸过小等）
  - 语音文件有效性校验
- 历史与回看：
  - 本地摘要历史
  - 历史详情与邮件发送状态更新
- 留存桥接（可选）：
  - 可配置对接后端留存接口，展示趋势、周报、收藏
- 邮件导出：
  - 将当前分析结果发送至邮箱
- TTS 播报：
  - 分析完成后可进行语音播报（受运行环境影响）

---

## 3.3 后端能力（`services/wechat-api`）

后端采用 FastAPI，主要路由域如下：

- 分析：`/api/analyze`、`/api/analyze/async*`
- 启动信息与身份：`/api/bootstrap`、`/api/auth/*`
- 历史：`/api/history*`
- 留存：`/api/retention/*`、`/api/report`
- 收藏：`/api/favorites*`
- 邮件：`/api/send-email`
- 语音转写网关：`/api/stt/tencent`
- 风格图任务：`/api/media-generate*`
- 历史上的今天：`/api/today-history`

后端实现要点：

- 用户身份解析优先使用微信身份头（`x-wx-unionid` / `x-wx-openid`）
- 分析任务与风格图任务均支持异步队列与轮询
- “历史上的今天”支持 provider + 缓存 + 敏感词过滤 + 降级
- 风格图生成支持配额、积分、同意确认等治理开关

---

## 4. 运行与开发

## 4.1 后端（本地）

```bash
cd services/wechat-api
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 9000
```

- 文档地址：`http://127.0.0.1:9000/docs`
- 健康检查：`http://127.0.0.1:9000/api/health`

## 4.2 微信小程序

1. 微信开发者工具导入 `apps/wechat-mini`
2. 配置 `apps/wechat-mini/config/index.js`：
   - `cloudEnv`
   - `containerEnv`
   - `containerService`
   - `apiBaseUrl`（可选）
3. 确保云开发与 Cloud Hosting 环境一致

可参考：

- [apps/wechat-mini/README.md](./apps/wechat-mini/README.md)
- [docs/wechat-mini-frontend-dev.md](./docs/wechat-mini-frontend-dev.md)

## 4.3 PC 端

```bash
cd apps/pc
python main.py
```

默认会尝试在 `8080` 启动并提供端口回退。

---

## 5. 文档索引

- 产品共识：`docs/product-consensus.md`
- 阶段文档入口（Phase1~Phase5）：`docs/stage1/README.md`
- 小程序接口契约：`services/wechat-api/miniprogram-api.md`
- 后端运行说明：`services/wechat-api/README.md`

---

## 6. 说明

- 项目定位为情绪陪伴与文化表达，不提供医疗诊断和治疗建议。
- 仓库当前 README 体系：
  - 根入口：`README.md`
  - 中文详细版：`README_cn.md`
  - 英文详细版：`README_en.md`

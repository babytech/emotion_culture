# 第一阶段任务分解（可直接开工）

## 使用方式

本文件基于以下三份文档拆解：

- [product-consensus.md](/Users/babytech/github/emotion_culture/docs/product-consensus.md)
- [phase1-implementation-checklist.md](/Users/babytech/github/emotion_culture/docs/phase1-implementation-checklist.md)
- [phase1-development-plan.md](/Users/babytech/github/emotion_culture/docs/phase1-development-plan.md)

任务按 `BE`（后端）、`MINI`（小程序）、`PC`（桌面端）、`DATA`（数据与隐私）、`QA`（回归）编号。  
每个任务均包含：目标、依赖、目标文件、完成定义。

## 阶段 0：接口与数据结构先行（必须先做）

### BE-001 统一分析接口输入结构

- 目标：固定输入模式与字段，支持 `text/voice/selfie/pc_camera`。
- 依赖：无。
- 目标文件：
- [analyze.py](/Users/babytech/github/emotion_culture/services/wechat-api/app/api/analyze.py)
- [analyze.py](/Users/babytech/github/emotion_culture/services/wechat-api/app/schemas/analyze.py)
- 完成定义：接口文档与请求 schema 对齐，输入模式可区分并可回传。

### BE-002 固定结果卡片返回结构

- 目标：统一返回主情绪、补充情绪、概述、触发标签、诗词、解读、国潮慰藉、今日建议。
- 依赖：`BE-001`。
- 目标文件：
- [analysis_service.py](/Users/babytech/github/emotion_culture/services/wechat-api/app/services/analysis_service.py)
- [analyze.py](/Users/babytech/github/emotion_culture/services/wechat-api/app/schemas/analyze.py)
- 完成定义：小程序和 PC 调用同一响应结构，无端侧特有字段分叉。

### BE-003 加入系统内部字段

- 目标：补齐 `request_id/analyzed_at/input_modes/confidence_level/...`。
- 依赖：`BE-002`。
- 目标文件：
- [analysis_service.py](/Users/babytech/github/emotion_culture/services/wechat-api/app/services/analysis_service.py)
- [analyze.py](/Users/babytech/github/emotion_culture/services/wechat-api/app/schemas/analyze.py)
- 完成定义：响应中含内部字段，且不破坏已有前端渲染。

## 阶段 1：后端主链路补齐

### BE-010 语音转文字主链路

- 目标：语音输入统一先转文字，再进入文本分析主链路。
- 依赖：`BE-001`。
- 目标文件：
- [speech.py](/Users/babytech/github/emotion_culture/services/wechat-api/app/core/speech.py)
- [analysis_service.py](/Users/babytech/github/emotion_culture/services/wechat-api/app/services/analysis_service.py)
- 完成定义：语音输入可产出可分析文本并进入统一分析流程。

### BE-011 语音质量校验与拒绝策略

- 目标：识别空文本、过短、噪声过大等，直接返回重录提示。
- 依赖：`BE-010`。
- 目标文件：
- [analysis_service.py](/Users/babytech/github/emotion_culture/services/wechat-api/app/services/analysis_service.py)
- [analyze.py](/Users/babytech/github/emotion_culture/services/wechat-api/app/api/analyze.py)
- 完成定义：不合格语音不会进入后续分析，错误码和文案可被前端识别。

### BE-012 自拍/拍照人脸可用性校验

- 目标：做人脸存在、单人、模糊、过暗、遮挡校验，不合格返回重拍提示。
- 依赖：`BE-001`。
- 目标文件：
- [analysis_service.py](/Users/babytech/github/emotion_culture/services/wechat-api/app/services/analysis_service.py)
- 完成定义：不合格图像阻断分析，返回明确提示。

### BE-013 邮件能力与分析链路解耦

- 目标：邮件发送失败不影响分析结果返回。
- 依赖：`BE-002`。
- 目标文件：
- [email.py](/Users/babytech/github/emotion_culture/services/wechat-api/app/api/email.py)
- [email_service.py](/Users/babytech/github/emotion_culture/services/wechat-api/app/services/email_service.py)
- 完成定义：分析接口成功与邮件接口成功独立，重试仅针对邮件接口。

### BE-014 原始媒体 24 小时清理机制

- 目标：原始图片、自拍、录音最长保留 24 小时并自动清理。
- 依赖：`BE-001`。
- 目标文件：
- [storage_service.py](/Users/babytech/github/emotion_culture/services/wechat-api/app/services/storage_service.py)
- 完成定义：可验证存在过期清理路径，不进入长期历史。

## 阶段 2：小程序主流程与页面

### MINI-001 输入页收敛

- 目标：保留文字、录音、前置自拍；去掉普通相册图片分析入口。
- 依赖：`BE-001`。
- 目标文件：
- [index.js](/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/index/index.js)
- [index.wxml](/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/index/index.wxml)
- 完成定义：UI 中不存在普通图片上传分析入口，三类输入链路可触发。

### MINI-002 自拍拍照确认流程

- 目标：前置摄像头拍照后预览，用户确认再提交分析。
- 依赖：`MINI-001`、`BE-012`。
- 目标文件：
- [index.js](/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/index/index.js)
- [index.wxml](/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/index/index.wxml)
- 完成定义：存在预览与确认步骤，取消后不提交分析。

### MINI-003 语音失败回退路径

- 目标：语音不可用时引导用户重录或改用文字。
- 依赖：`BE-011`。
- 目标文件：
- [index.js](/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/index/index.js)
- 完成定义：语音错误可感知、可重试、不阻塞文字输入。

### MINI-004 结果页固定结构渲染

- 目标：按统一字段渲染主情绪、补充情绪、概述、触发标签、诗词、国潮、建议。
- 依赖：`BE-002`、`BE-003`。
- 目标文件：
- [result.js](/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/result/result.js)
- [result.wxml](/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/result/result.wxml)
- 完成定义：字段齐全，缺失字段有降级显示，不出现空白崩溃。

### MINI-005 状态与可恢复反馈

- 目标：补齐上传中、分析中、结果生成中、失败可重试状态。
- 依赖：`MINI-001`、`MINI-004`。
- 目标文件：
- [index.js](/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/index/index.js)
- [result.js](/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/result/result.js)
- 完成定义：用户知道当前阶段，失败后能继续，不需整页重来。

### MINI-006 邮件发送体验

- 目标：邮箱校验、发送状态、失败重试。
- 依赖：`BE-013`、`MINI-004`。
- 目标文件：
- [result.js](/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/result/result.js)
- [result.wxml](/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/result/result.wxml)
- 完成定义：邮件失败不影响结果展示，重试仅重发邮件。

### MINI-007 简版历史记录页

- 目标：最近记录列表 + 单条详情回看。
- 依赖：`DATA-001`、`BE-003`。
- 目标文件：
- [app.json](/Users/babytech/github/emotion_culture/apps/wechat-mini/app.json)
- 新增 `pages/history/*`
- 完成定义：能查看最近记录并进入详情页。

### MINI-008 极简设置页

- 目标：历史开关、隐私说明、产品说明、反馈入口。
- 依赖：`DATA-002`。
- 目标文件：
- [app.json](/Users/babytech/github/emotion_culture/apps/wechat-mini/app.json)
- 新增 `pages/settings/*`
- 完成定义：`保存我的历史记录` 开关可用且默认开启。

## 阶段 3：PC 能力补齐

### PC-001 摄像头拍照输入

- 目标：新增或完善摄像头拍照入口，支持拍照预览和确认。
- 依赖：`BE-012`。
- 目标文件：
- [ui.py](/Users/babytech/github/emotion_culture/apps/pc/ui.py)
- [main.py](/Users/babytech/github/emotion_culture/apps/pc/main.py)
- 完成定义：可完成拍照 -> 预览 -> 确认 -> 分析。

### PC-002 移除普通本地图片分析主入口

- 目标：不再把任意本地图片作为第一阶段主功能输入。
- 依赖：`PC-001`。
- 目标文件：
- [ui.py](/Users/babytech/github/emotion_culture/apps/pc/ui.py)
- 完成定义：主流程仅支持文字、录音、摄像头拍照。

### PC-003 录音输入与失败恢复

- 目标：录音失败可重试，失败不清空已有输入。
- 依赖：`BE-011`。
- 目标文件：
- [speech.py](/Users/babytech/github/emotion_culture/apps/pc/speech.py)
- [main.py](/Users/babytech/github/emotion_culture/apps/pc/main.py)
- 完成定义：录音链路稳定，失败可恢复。

### PC-004 轻量本地历史能力

- 目标：保留本地轻量历史底座，不做完整历史页面。
- 依赖：`DATA-001`。
- 目标文件：
- [main.py](/Users/babytech/github/emotion_culture/apps/pc/main.py)
- 新增或复用 `apps/pc/cache/` 下历史缓存文件
- 完成定义：可写入和读取最近记录摘要。

## 阶段 4：数据与隐私

### DATA-001 历史摘要数据模型

- 目标：固定历史摘要字段，不存原始媒体。
- 依赖：`BE-003`。
- 目标文件：
- 后端历史相关存储模块（如新增 `app/services/history_service.py`）
- 完成定义：字段与共识文档一致，可被小程序历史页直接消费。

### DATA-002 历史保存开关能力

- 目标：支持用户关闭历史记录保存，且即时生效。
- 依赖：`DATA-001`、`MINI-008`。
- 目标文件：
- 小程序设置页与后端配置接口（如新增 `app/api/settings.py`）
- 完成定义：关闭后新记录不再入库，开启后恢复写入。

### DATA-003 删除能力

- 目标：支持删除单条历史和清空全部历史。
- 依赖：`DATA-001`。
- 目标文件：
- 后端历史接口模块（如新增 `app/api/history.py`）
- 小程序历史页
- 完成定义：删除操作可见、可验证、不可跨用户越权。

## 阶段 5：回归与封板

### QA-001 小程序 A/B/C 主链路回归

- 目标：覆盖文字、语音、自拍三条链路。
- 依赖：`MINI-001` 到 `MINI-008`。
- 完成定义：三类输入各至少一次完整通过，失败路径可恢复。

### QA-002 PC 主链路回归

- 目标：覆盖文字、录音、摄像头拍照三条链路。
- 依赖：`PC-001` 到 `PC-004`。
- 完成定义：三类输入各至少一次完整通过，结果口径与小程序一致。

### QA-003 隐私与保留策略回归

- 目标：验证 24 小时原始媒体清理、180 天摘要策略、删除与开关逻辑。
- 依赖：`DATA-001` 到 `DATA-003`。
- 完成定义：策略可被验证，说明文案与实际行为一致。

### QA-004 稳定性指标回归

- 目标：验证文本/自拍/语音目标耗时和降级策略。
- 依赖：全部开发任务。
- 完成定义：满足第一阶段稳定性标准，不阻塞封板。

## 建议开工顺序（本周可执行）

1. `BE-001` -> `BE-002` -> `BE-003`
2. `BE-010` -> `BE-011` -> `BE-012`
3. `MINI-001` -> `MINI-002` -> `MINI-004` -> `MINI-005`
4. `BE-013` -> `MINI-006`
5. `DATA-001` -> `MINI-007` -> `MINI-008` -> `DATA-002` -> `DATA-003`
6. `PC-001` -> `PC-002` -> `PC-003` -> `PC-004`
7. `QA-001` -> `QA-002` -> `QA-003` -> `QA-004`

## 任务看板建议

建议在 GitHub Projects 或 Issue 看板中按以下列管理：

- `Todo`
- `In Progress`
- `Blocked`
- `Review`
- `Done`

每个任务卡建议携带：

- 任务编号
- 关联文件
- 依赖任务
- 验收标准
- 负责人
- 预计工时

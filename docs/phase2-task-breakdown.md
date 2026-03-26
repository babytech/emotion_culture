# 第二阶段任务分解（方案 B，可直接开工）

## 使用方式

本文件基于以下三份文档拆解：

- [product-consensus.md](/Users/babytech/github/emotion_culture/docs/product-consensus.md)
- [phase2-implementation-checklist.md](/Users/babytech/github/emotion_culture/docs/phase2-implementation-checklist.md)
- [phase2-development-plan.md](/Users/babytech/github/emotion_culture/docs/phase2-development-plan.md)

任务按 `BE`（后端）、`MINI`（小程序）、`PC`（桌面端）、`DATA`（数据与隐私）、`QA`（回归）编号。  
每个任务均包含：目标、依赖、目标文件、完成定义。

## 阶段 0：留存数据底座（必须先做）

### BE-201 留存数据模型扩展

- 目标：新增打卡、周报、收藏的数据模型，复用第一阶段身份口径。
- 依赖：无。
- 目标文件：
- [models.py](/Users/babytech/github/emotion_culture/services/wechat-api/app/db/models.py)
- [database.py](/Users/babytech/github/emotion_culture/services/wechat-api/app/db/database.py)
- 完成定义：模型可迁移、索引可用、字段支持日历聚合和周报查询。

### BE-202 日历聚合与连续打卡计算

- 目标：提供按日聚合的情绪摘要与连续天数计算服务。
- 依赖：`BE-201`。
- 目标文件：
- [analysis_service.py](/Users/babytech/github/emotion_culture/services/wechat-api/app/services/analysis_service.py)
- 新增 `app/services/retention_service.py`
- 完成定义：可按用户返回“某月日历摘要 + 当前连续打卡天数”。

### BE-203 周报聚合接口

- 目标：按周汇总主情绪分布、触发因素、行动建议复盘。
- 依赖：`BE-201`、`BE-202`。
- 目标文件：
- 新增 `app/api/report.py`
- 新增 `app/services/report_service.py`
- 完成定义：周报接口支持按自然周查询，缺数据时有降级文案。

### BE-204 收藏能力接口

- 目标：支持收藏/取消收藏诗词与国潮慰藉内容。
- 依赖：`BE-201`。
- 目标文件：
- 新增 `app/api/favorites.py`
- 新增 `app/services/favorites_service.py`
- 完成定义：收藏写入、去重、分页查询和删除能力可用。

### BE-205 留存配置与守卫生效

- 目标：统一留存开关、周报开关、ASR 开关语义，避免配置误用。
- 依赖：`BE-202`、`BE-203`。
- 目标文件：
- [speech.py](/Users/babytech/github/emotion_culture/services/wechat-api/app/core/speech.py)
- [README.md](/Users/babytech/github/emotion_culture/services/wechat-api/README.md)
- [miniprogram-api.md](/Users/babytech/github/emotion_culture/services/wechat-api/miniprogram-api.md)
- 完成定义：`SPEECH_ASR_SERVICE` 与 `VOICE_REQUIRE_TRANSCRIPT` 语义清晰且一致。

## 阶段 1：小程序留存闭环

### MINI-201 情绪日历页

- 目标：按月展示每日主情绪与是否完成记录。
- 依赖：`BE-202`。
- 目标文件：
- [app.json](/Users/babytech/github/emotion_culture/apps/wechat-mini/app.json)
- 新增 `pages/calendar/*`
- 完成定义：可切换月份并查看当日摘要状态。

### MINI-202 连续打卡入口

- 目标：在结果页和日历页展示连续天数与当日打卡状态。
- 依赖：`MINI-201`、`BE-202`。
- 目标文件：
- [result.js](/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/result/result.js)
- [result.wxml](/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/result/result.wxml)
- 完成定义：完成一次分析后可自动刷新打卡状态与 streak。

### MINI-203 周报页与趋势摘要

- 目标：展示本周情绪趋势、触发因素和建议复盘。
- 依赖：`BE-203`。
- 目标文件：
- [app.json](/Users/babytech/github/emotion_culture/apps/wechat-mini/app.json)
- 新增 `pages/report/*`
- 完成定义：周报可查看、无数据可降级、页面不崩溃。

### MINI-204 收藏入口与列表

- 目标：结果页支持收藏诗词/角色，设置或单独页面可回看收藏。
- 依赖：`BE-204`、`MINI-203`。
- 目标文件：
- [result.js](/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/result/result.js)
- [result.wxml](/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/result/result.wxml)
- 新增 `pages/favorites/*`
- 完成定义：收藏状态可切换、列表可分页、取消收藏即时生效。

### MINI-205 分享卡片导出（非 AI）

- 目标：支持将本次结果导出为基础分享卡片。
- 依赖：`MINI-203`。
- 目标文件：
- 新增 `pages/share/*`
- 完成定义：可生成并保存/转发基础卡片，不依赖外部 AI 生成服务。

## 阶段 2：PC 轻量留存能力

### PC-201 留存摘要面板

- 目标：`PC` 展示最近 7/30 天主情绪趋势摘要。
- 依赖：`BE-202`。
- 目标文件：
- [ui.py](/Users/babytech/github/emotion_culture/apps/pc/ui.py)
- [main.py](/Users/babytech/github/emotion_culture/apps/pc/main.py)
- 完成定义：可查看趋势摘要，不影响现有主流程。

### PC-202 周报回看入口

- 目标：`PC` 可查看最近周报摘要与建议。
- 依赖：`BE-203`、`PC-201`。
- 目标文件：
- [main.py](/Users/babytech/github/emotion_culture/apps/pc/main.py)
- 完成定义：可切周查看，空数据有提示。

### PC-203 收藏回看能力

- 目标：`PC` 可回看收藏的诗词/角色条目。
- 依赖：`BE-204`。
- 目标文件：
- [main.py](/Users/babytech/github/emotion_culture/apps/pc/main.py)
- 完成定义：列表可读、状态和小程序一致。

## 阶段 3：数据与隐私收口

### DATA-201 留存数据保留策略

- 目标：定义并实现日历/周报/收藏的保留周期与清理机制。
- 依赖：`BE-201`。
- 目标文件：
- 新增 `app/services/retention_cleanup_service.py`
- 完成定义：可验证按策略清理过期数据。

### DATA-202 删除与开关能力扩展

- 目标：支持删除周报快照、清空收藏、关闭留存写入。
- 依赖：`DATA-201`、`BE-204`。
- 目标文件：
- 新增 `app/api/retention.py`
- 小程序留存相关页面
- 完成定义：删除能力可见可验，关闭后新数据不再入库。

### DATA-203 统计脱敏与导出边界

- 目标：限制对外导出的字段，避免用户敏感信息过度暴露。
- 依赖：`DATA-201`。
- 目标文件：
- 新增或更新留存相关 schema 模块
- 完成定义：接口返回字段通过脱敏审查，符合既有隐私边界。

## 阶段 4：回归与封板

### QA-201 小程序留存链路回归

- 目标：覆盖日历、打卡、周报、收藏、分享链路。
- 依赖：`MINI-201` 到 `MINI-205`。
- 完成定义：核心场景通过，失败场景有恢复路径。

### QA-202 后端聚合与权限回归

- 目标：覆盖多接口一致性、越权保护、配置守卫。
- 依赖：`BE-201` 到 `BE-205`。
- 完成定义：数据口径一致，跨用户访问被正确拦截。

### QA-203 PC 留存能力回归

- 目标：覆盖趋势、周报、收藏回看链路。
- 依赖：`PC-201` 到 `PC-203`。
- 完成定义：`PC` 回看能力可用，不影响主分析稳定性。

### QA-204 性能与稳定性回归

- 目标：验证新增留存接口和页面的性能目标与降级策略。
- 依赖：全部开发任务。
- 完成定义：聚合接口与页面满足阶段性能目标。

## 方案 A/C 预留任务（不纳入本阶段交付）

### RES-A-301 月报与深度趋势

- 目标：补齐月报、同比环比、异常波动解释。
- 计划：下一阶段优先包。

### RES-A-302 多维筛选与检索

- 目标：支持按情绪、触发因素、时间区间筛选。
- 计划：下一阶段与月报能力一并落地。

### RES-C-301 积分/虚拟币账本

- 目标：建立积分累计、扣减、过期、审计能力。
- 计划：下一阶段独立风控评审后落地。

### RES-C-302 AI 奖励能力

- 目标：支持 AI 海报、AI 头像、情绪明信片等奖励内容。
- 计划：下一阶段结合成本与供应商评估落地。

## 建议开工顺序（本周可执行）

1. `BE-201` -> `BE-202` -> `BE-203`
2. `BE-204` -> `BE-205`
3. `MINI-201` -> `MINI-202` -> `MINI-203`
4. `MINI-204` -> `MINI-205`
5. `PC-201` -> `PC-202` -> `PC-203`
6. `DATA-201` -> `DATA-202` -> `DATA-203`
7. `QA-201` -> `QA-202` -> `QA-203` -> `QA-204`

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


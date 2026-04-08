# 第五阶段任务分解（M1-M4 对齐版）

## 使用方式

本文件用于将 [phase5-development-plan.md](/Users/babytech/github/emotion_culture/docs/phase5-development-plan.md) 中已经达成共识的里程碑继续下钻到可执行任务层。  
编号规则如下：

- `BE`：后端接口与服务
- `MINI`：小程序前端
- `DATA`：缓存、审核、内容治理
- `QA`：回归与验收

## 里程碑 M1：首次授权门与微信身份收口

### MINI-511 首次进入授权页与首页前置拦截

- 目标：首次打开小程序时，先进入授权门，而不是直接进入首页。
- 依赖：无。
- 目标文件：
- [apps/wechat-mini/app.js](/Users/babytech/github/emotion_culture/apps/wechat-mini/app.js)
- [apps/wechat-mini/app.json](/Users/babytech/github/emotion_culture/apps/wechat-mini/app.json)
- 新增 `apps/wechat-mini/pages/auth-entry/*`
- 完成定义：
- 首次进入时未完成授权门则不进入首页
- 授权完成后才允许进入首页
- 后续进入可依据本地状态跳过重复说明

### MINI-512 授权门信息架构与隐私说明

- 目标：在授权门中明确说明身份绑定、历史记录、积分/会员与微信身份关系。
- 依赖：`MINI-511`。
- 目标文件：
- 新增 `apps/wechat-mini/pages/auth-entry/*`
- 完成定义：
- 授权页包含用途说明、隐私说明、继续进入按钮
- 用户知道历史、积分、会员将绑定当前微信身份
- 不把复杂设置堆进首次进入流程

### BE-511 身份自检与启动信息接口

- 目标：提供一个轻量启动接口，返回当前解析到的微信身份与基础开关状态。
- 依赖：无。
- 目标文件：
- 新增 `services/wechat-api/app/api/bootstrap.py`
- 新增 `services/wechat-api/app/schemas/bootstrap.py`
- `services/wechat-api/app/core/user_identity.py`
- 完成定义：
- 接口可返回 `identity_type/openid_present/unionid_present`
- 可返回当前与首页启动相关的基础开关
- 匿名或身份异常场景有明确返回语义

### MINI-513 自拍前摄像头权限前置校验

- 目标：自拍入口在拍摄前显式检查并请求摄像头权限。
- 依赖：`MINI-511`。
- 目标文件：
- [apps/wechat-mini/pages/analyze/index.js](/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/analyze/index.js)
- [apps/wechat-mini/pages/analyze/index.wxml](/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/analyze/index.wxml)
- 完成定义：
- 自拍前检查 `scope.camera`
- 用户拒绝时直接返回，不进入拍摄流程
- 拒绝后可引导打开设置

### MINI-514 录音中提交自动收口

- 目标：录音未结束时点击提交，优先自动停止录音，失败后再阻断。
- 依赖：无。
- 目标文件：
- [apps/wechat-mini/pages/analyze/index.js](/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/analyze/index.js)
- 完成定义：
- 录音中点击提交时不再静默丢失录音
- 自动停止录音成功则继续提交
- 自动停止失败则明确提示“请先结束录音”

### QA-511 首次授权门与权限治理回归

- 目标：覆盖首次进入、身份绑定、摄像头授权、录音中提交等关键场景。
- 依赖：`BE-511`、`MINI-511` ~ `MINI-514`。
- 完成定义：
- 首次进入不再直接落首页
- 授权完成后可正常进入首页
- 自拍权限拒绝场景可恢复
- 录音中提交场景行为符合预期

## 里程碑 M2：主链路稳定性专项

### DATA-521 主链路关键耗时埋点

- 目标：补齐“点击分析 -> 结果页打开”全链路关键时延指标。
- 依赖：无。
- 目标文件：
- [apps/wechat-mini/pages/analyze/index.js](/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/analyze/index.js)
- [services/wechat-api/app/services/analyze_async_service.py](/Users/babytech/github/emotion_culture/services/wechat-api/app/services/analyze_async_service.py)
- [services/wechat-api/app/api/analyze.py](/Users/babytech/github/emotion_culture/services/wechat-api/app/api/analyze.py)
- 完成定义：
- 上传、建任务、排队、执行、轮询、打开结果页等环节有埋点
- 能区分前端超时、后端慢、轮询失败等类型

### BE-521 异步分析任务稳定性优化

- 目标：继续优化异步分析任务的排队、执行、重试与错误语义。
- 依赖：`DATA-521`。
- 目标文件：
- [services/wechat-api/app/services/analyze_async_service.py](/Users/babytech/github/emotion_culture/services/wechat-api/app/services/analyze_async_service.py)
- [services/wechat-api/app/api/analyze.py](/Users/babytech/github/emotion_culture/services/wechat-api/app/api/analyze.py)
- 完成定义：
- 常见超时错误被区分并可识别
- 轮询返回更稳定的 `status/poll_after_ms/status_message`
- 失败时保留足够诊断信息

### MINI-521 分析页自动恢复待完成任务

- 目标：用户回到分析页时，若存在待完成任务，自动恢复查询，而不是只等待再次点击。
- 依赖：`BE-521`。
- 目标文件：
- [apps/wechat-mini/pages/analyze/index.js](/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/analyze/index.js)
- 完成定义：
- `pendingTask` 进入页面后可自动恢复
- 页面可显示“继续查询中”状态
- 恢复失败后给出可理解的重试路径

### MINI-522 上传与弱网体验优化

- 目标：继续优化图片压缩、音频上传、状态文案与弱网提示。
- 依赖：`DATA-521`。
- 目标文件：
- [apps/wechat-mini/pages/analyze/index.js](/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/analyze/index.js)
- [apps/wechat-mini/services/cloud.js](/Users/babytech/github/emotion_culture/apps/wechat-mini/services/cloud.js)
- [apps/wechat-mini/services/api.js](/Users/babytech/github/emotion_culture/apps/wechat-mini/services/api.js)
- 完成定义：
- 自拍与录音上传耗时有进一步控制
- 云端超时提示更明确
- 弱网时用户知道系统还在做什么

### MINI-523 再次分析默认清空旧输入

- 目标：结果页返回分析工作台时，默认清空上一次文字、自拍、录音与提交状态。
- 依赖：无。
- 目标文件：
- [apps/wechat-mini/pages/result/result.js](/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/result/result.js)
- [apps/wechat-mini/pages/analyze/index.js](/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/analyze/index.js)
- 完成定义：
- “再次分析”进入分析页后是干净工作台
- 不再误带上一次自拍和录音
- 如需保留旧内容，应另设次级入口

### QA-521 5G / 弱网主链路回归

- 目标：覆盖上传、建任务、轮询、恢复、结果页打开等真实网络波动场景。
- 依赖：`DATA-521`、`BE-521`、`MINI-521` ~ `MINI-523`。
- 完成定义：
- 5G 下主链路成功率提升
- 弱网下超时可恢复
- “任务仍在处理中”路径可闭环


## 里程碑 M3-A：当前分享页分享到朋友圈

### MINI-531 分享页支持当前页分享到朋友圈

- 目标：在现有分享页基础上补齐“当前页分享到朋友圈”能力。
- 依赖：无。
- 目标文件：
- [apps/wechat-mini/pages/share/index.js](/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/share/index.js)
- [apps/wechat-mini/pages/share/index.wxml](/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/share/index.wxml)
- [apps/wechat-mini/pages/share/index.json](/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/share/index.json)
- 完成定义：
- 页面支持 `onShareTimeline`
- 分享入口文案明确是“分享到朋友圈”
- 分享失败或受限时有可理解提示

### MINI-532 分享页信息收敛与隐私裁剪

- 目标：确保分享到朋友圈的内容足够轻、不过度暴露隐私输入。
- 依赖：`MINI-531`。
- 目标文件：
- [apps/wechat-mini/pages/share/index.js](/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/share/index.js)
- 完成定义：
- 朋友圈分享内容不直接带用户原始长文本
- 朋友圈分享内容不强依赖自拍图
- 主标题、摘要、卡面文案长度受控

### MINI-533 朋友圈分享卡面适配

- 目标：让现有分享卡更适合朋友圈传播场景，而不是仅适合保存到相册。
- 依赖：`MINI-532`。
- 目标文件：
- [apps/wechat-mini/pages/share/index.js](/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/share/index.js)
- [apps/wechat-mini/pages/share/index.wxml](/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/share/index.wxml)
- [apps/wechat-mini/pages/share/index.wxss](/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/share/index.wxss)
- 完成定义：
- 卡面在朋友圈场景中主信息更聚焦
- 情绪、建议、诗意回应三者层级清晰
- 生成后的图片既可保存，也可作为分享预览辅助素材

### MINI-534 分享链路状态反馈统一

- 目标：统一“生成卡片 / 保存相册 / 分享到朋友圈”的状态反馈。
- 依赖：`MINI-531`、`MINI-533`。
- 目标文件：
- [apps/wechat-mini/pages/share/index.js](/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/share/index.js)
- 完成定义：
- 生成中、保存中、可分享、失败重试状态明确
- 相册权限拒绝后可引导用户进入设置
- 分享操作不影响已有生成卡片能力

### QA-531 当前页分享到朋友圈回归

- 目标：验证朋友圈分享能力可用，且不破坏现有页面分享与保存链路。
- 依赖：`MINI-531` ~ `MINI-534`。
- 完成定义：
- 当前分享页可触发分享到朋友圈
- 现有 `onShareAppMessage` 不回退
- 分享卡生成、保存、朋友圈分享三条链路可独立使用

## 里程碑 M3-B：“历史上的今天”AI 搜索折叠板块

### BE-531 “历史上的今天”统一输出接口

- 目标：提供按日期查询的“历史上的今天”后端接口，统一返回已收敛内容。
- 依赖：无。
- 目标文件：
- 新增 `services/wechat-api/app/api/today_history.py`
- 新增 `services/wechat-api/app/schemas/today_history.py`
- 新增 `services/wechat-api/app/services/today_history_service.py`
- 完成定义：
- 接口按日期返回结构化结果
- 返回字段稳定，不把 AI 原始搜索文本直接暴露给前端
- 当日无合适结果时支持明确降级

### BE-532 AI 搜索与结果整理服务

- 目标：由后端调用成熟 AI 模型进行搜索 / 检索增强，并输出短摘要。
- 依赖：`BE-531`。
- 目标文件：
- 新增 `services/wechat-api/app/services/today_history_service.py`
- 完成定义：
- 基于日期执行联网搜索或检索增强
- 输出固定结构：
- `headline`
- `summary`
- `optional_note`
- 输出长度受控，适合首页或记录页展示

### BE-533 历史事实与情绪文案分层

- 目标：区分“事实内容”和“陪伴型轻文案”，避免 AI 过度发挥。
- 依赖：`BE-532`。
- 目标文件：
- `services/wechat-api/app/services/today_history_service.py`
- 完成定义：
- 事实层与延伸文案层字段分离
- 不将情绪安慰文案混入事实描述
- 敏感日期可直接不返回延伸文案

### DATA-531 查询缓存与降级策略

- 目标：降低重复搜索成本，提升页面打开稳定性。
- 依赖：`BE-531`。
- 目标文件：
- `services/wechat-api/app/services/today_history_service.py`
- 可复用后续 Phase5 数据层能力
- 完成定义：
- 高频日期结果有缓存
- AI 搜索超时或失败时可降级到缓存结果
- 无缓存且搜索失败时允许不展示模块

### DATA-532 内容审核与敏感事件治理

- 目标：避免极端事件、灾难事件、政治争议事件直接暴露到首页陪伴场景。
- 依赖：`BE-532`、`DATA-531`。
- 目标文件：
- `services/wechat-api/app/services/today_history_service.py`
- 新增审核规则配置或数据文件
- 完成定义：
- 对高敏感主题有过滤或降级规则
- 输出内容长度、语气、风险词受控
- “不展示”是允许的合法结果

### MINI-535 首页 / 记录页“历史上的今天”折叠板块

- 目标：在首页或记录页增加独立折叠板块，不打断主任务。
- 依赖：`BE-531`。
- 目标文件：
- [apps/wechat-mini/pages/home/index.js](/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/home/index.js)
- [apps/wechat-mini/pages/home/index.wxml](/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/home/index.wxml)
- [apps/wechat-mini/pages/journey/index.js](/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/journey/index.js)
- [apps/wechat-mini/pages/journey/index.wxml](/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/journey/index.wxml)
- 完成定义：
- 默认收拢
- 可展开查看
- 不影响首页主 Hero 和分析入口

### MINI-536 “提交今天情绪后顺带感知历史”联动体验

- 目标：让用户完成情绪记录后，更容易在首页或记录页看到当日历史事件。
- 依赖：`MINI-535`。
- 目标文件：
- [apps/wechat-mini/pages/result/result.js](/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/result/result.js)
- [apps/wechat-mini/pages/home/index.js](/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/home/index.js)
- 完成定义：
- 本次完成分析后返回首页/记录页时，用户能明显看到该板块更新
- 不要求把该内容塞回结果页主结构
- 保持它是“独立补充板块”，不是分析结果的一部分

### MINI-537 模块空态 / 降级态 / 审核拦截态

- 目标：避免该板块因接口波动或审核结果为空而产生空白区域。
- 依赖：`MINI-535`。
- 目标文件：
- [apps/wechat-mini/pages/home/index.js](/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/home/index.js)
- [apps/wechat-mini/pages/journey/index.js](/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/journey/index.js)
- 完成定义：
- 搜索失败时可隐藏或显示轻提示
- 审核拦截时不显示异常错误给用户
- 空态样式与首页/记录页整体视觉一致

### QA-532 “历史上的今天”模块回归

- 目标：覆盖正常展示、折叠展开、搜索失败、审核拦截、缓存命中等场景。
- 依赖：`BE-531` ~ `DATA-532`、`MINI-535` ~ `MINI-537`。
- 完成定义：
- 正常日期可展示
- 无合适内容时可安全降级
- 敏感内容不会直接暴露
- 页面不因该模块失败而影响主链路

## 里程碑 M4：视觉升级收口

### MINI-541 首页视觉二次升级

- 目标：进一步强化首页 Hero、卡片层次与整体记忆点。
- 依赖：无。
- 目标文件：
- [apps/wechat-mini/pages/home/index.wxml](/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/home/index.wxml)
- [apps/wechat-mini/pages/home/index.wxss](/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/home/index.wxss)
- 完成定义：
- 首页主视觉辨识度提升
- Hero、摘要卡、洞察区层次更清晰

### MINI-542 结果页视觉与动作区二次升级

- 目标：让结果页更像主结果页，而不是功能集合页。
- 依赖：无。
- 目标文件：
- [apps/wechat-mini/pages/result/result.wxml](/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/result/result.wxml)
- [apps/wechat-mini/pages/result/result.wxss](/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/result/result.wxss)
- 完成定义：
- 摘要区、内容区、动作区层级更稳定
- 固定动作区与键盘/邮箱输入避让关系更自然

### MINI-543 分享页传播感升级

- 目标：提升分享页作为传播页的品牌感和完成度。
- 依赖：`MINI-531`、`MINI-533`。
- 目标文件：
- [apps/wechat-mini/pages/share/index.wxml](/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/share/index.wxml)
- [apps/wechat-mini/pages/share/index.wxss](/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/share/index.wxss)
- 完成定义：
- 页面不再只是工具页
- 传播感与收藏/保存/分享到朋友圈路径一致

### MINI-544 记录页 / 我的页视觉细节统一

- 目标：统一记录页与我的页的空态、间距、按钮与卡片语言。
- 依赖：无。
- 目标文件：
- [apps/wechat-mini/pages/journey/index.wxml](/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/journey/index.wxml)
- [apps/wechat-mini/pages/journey/index.wxss](/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/journey/index.wxss)
- [apps/wechat-mini/pages/profile/index.wxml](/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/profile/index.wxml)
- [apps/wechat-mini/pages/profile/index.wxss](/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/profile/index.wxss)
- 完成定义：
- 页面细节统一
- 空态与长文案场景无明显割裂

### QA-541 全局视觉与真机回归

- 目标：覆盖首页、结果页、分享页、记录页、我的页的视觉一致性与真机表现。
- 依赖：`MINI-541` ~ `MINI-544`。
- 完成定义：
- iPhone 窄屏 / 刘海屏 / Android 全面屏无遮挡
- 关键动效与状态反馈无明显回退

## 输出结构建议（供接口和前端对齐）

建议“历史上的今天”接口固定返回如下字段：

- `date`
- `headline`
- `summary`
- `optional_note`
- `source_mode`
- `cache_hit`
- `displayable`

建议前端展示规则如下：

- 收拢态只展示 `headline`
- 展开态展示 `summary`
- `optional_note` 仅在审核通过时展示
- `displayable=false` 时前端直接隐藏模块

## 建议开工顺序

1. `MINI-511` -> `MINI-512` -> `BE-511` -> `MINI-513` -> `MINI-514` -> `QA-511`
2. `DATA-521` -> `BE-521` -> `MINI-521` -> `MINI-522` -> `MINI-523` -> `QA-521`
3. `MINI-531` -> `MINI-532` -> `MINI-533` -> `MINI-534` -> `QA-531`
4. `BE-531` -> `BE-532` -> `BE-533` -> `DATA-531` -> `DATA-532`
5. `MINI-535` -> `MINI-536` -> `MINI-537` -> `QA-532`
6. `MINI-541` -> `MINI-542` -> `MINI-543` -> `MINI-544` -> `QA-541`

## 后续衔接

本文件当前已细化第五阶段 `M1`、`M2`、`M3`、`M4`。

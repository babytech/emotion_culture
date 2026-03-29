# 第三阶段任务分解（动态图稳定链路，必须完成）

## 使用方式

本文件对应第三阶段“动态图能力稳定化”目标，任务编号沿用现有规则：

- `BE`：后端
- `MINI`：小程序
- `DATA`：数据与安全
- `QA`：回归与验收

## 阶段 0：后端中转底座（必须先做）

### BE-301 动态图任务接口

- 目标：提供“创建任务 + 查询状态”的统一接口。
- 依赖：无。
- 目标文件：
- 新增 `services/wechat-api/app/api/media_generate.py`
- 新增 `services/wechat-api/app/services/media_generate_service.py`
- 完成定义：可返回任务 `queued/running/succeeded/failed` 状态与结果引用。

### BE-302 供应商适配层

- 目标：封装腾讯云/第三方（如 liblib）请求差异。
- 依赖：`BE-301`。
- 目标文件：
- 新增 `services/wechat-api/app/services/image_provider_service.py`
- 完成定义：新增供应商时不改上层业务流程。

### BE-303 中转上传与自有域名输出

- 目标：生成图先落自有存储，再返回可在小程序加载的 URL 或 file_id。
- 依赖：`BE-302`。
- 目标文件：
- `services/wechat-api/app/services/storage_service.py`
- `services/wechat-api/app/services/media_generate_service.py`
- 完成定义：响应中不再直接暴露第三方临时 URL。

### BE-304 幂等缓存与重试

- 目标：同参数请求复用已生成结果，减少重复消耗。
- 依赖：`BE-303`。
- 目标文件：
- `services/wechat-api/app/services/media_generate_service.py`
- 完成定义：支持 hash 命中缓存、失败重试和超时中止。

### BE-305 开关与降级策略

- 目标：支持动态生图开关与供应商故障降级。
- 依赖：`BE-302`。
- 目标文件：
- 新增/更新配置读取模块（`services/wechat-api/app/core/*`）
- `services/wechat-api/README.md`
- 完成定义：供应商故障时主分析结果不受阻塞，图片链路可降级。

### BE-306 微信身份识别与用户配额键

- 目标：基于微信身份（`openid/unionid`）识别用户并作为配额与积分主键。
- 依赖：`BE-301`。
- 目标文件：
- `services/wechat-api/app/core/user_identity.py`
- `services/wechat-api/app/api/media_generate.py`
- 完成定义：未识别到微信身份时拒绝动态生图，返回明确错误码。

### BE-307 周限额与积分扣减

- 目标：同一用户每自然周仅允许生图 1 次，且每次生图都扣减积分。
- 依赖：`BE-306`。
- 目标文件：
- 新增 `services/wechat-api/app/services/quota_service.py`
- 新增 `services/wechat-api/app/services/points_service.py`
- `services/wechat-api/app/services/media_generate_service.py`
- 完成定义：超限拒绝、积分不足拒绝、任务失败可回滚积分。

## 阶段 1：小程序接入

### MINI-301 结果页改造为统一图片来源

- 目标：结果页只消费后端统一返回的图片引用。
- 依赖：`BE-303`。
- 目标文件：
- `apps/wechat-mini/pages/result/result.js`
- `apps/wechat-mini/pages/result/result.wxml`
- 完成定义：小程序不直连第三方域名。

### MINI-302 动态图状态反馈

- 目标：增加“生成中/已完成/失败”的状态提示。
- 依赖：`BE-301`、`MINI-301`。
- 目标文件：
- `apps/wechat-mini/pages/result/result.js`
- `apps/wechat-mini/pages/result/result.wxml`
- 完成定义：用户可感知当前图片生成状态。

### MINI-303 本地静态图兜底

- 目标：远端图失败时自动回退本地资源，避免空白占位。
- 依赖：`MINI-301`。
- 目标文件：
- `apps/wechat-mini/pages/result/result.js`
- `apps/wechat-mini/assets/tangsong/*`
- `apps/wechat-mini/assets/guochao/*`
- 完成定义：真机场景下不再长期出现“图片暂不可用”空白态。

### MINI-304 用户主动触发与授权确认

- 目标：动态生图仅由用户主动点击触发，并显示授权说明。
- 依赖：`BE-301`、`BE-306`。
- 目标文件：
- `apps/wechat-mini/pages/result/result.js`
- `apps/wechat-mini/pages/result/result.wxml`
- 完成定义：用户拒绝授权时立即取消，不发起生图请求。

### MINI-305 风格选择（科技类/国潮类）

- 目标：提供可见按钮让用户选择风格并作为生图请求条件。
- 依赖：`MINI-304`、`BE-302`。
- 目标文件：
- `apps/wechat-mini/pages/result/result.js`
- `apps/wechat-mini/pages/result/result.wxml`
- 完成定义：未选风格不得提交，已选风格可透传给后端供应商适配层。

### MINI-306 UI 设计 Token 与组件规范

- 目标：统一颜色、字号、圆角、间距、按钮主次和卡片样式。
- 依赖：无。
- 目标文件：
- `apps/wechat-mini/app.wxss`
- `apps/wechat-mini/pages/**/**/*.wxss`
- 完成定义：三大页面共享同一套视觉 token，不再各写各的样式。

### MINI-307 首页 UI 重构

- 目标：重构首页信息层级，突出“今日状态 + 核心输入 + 主操作”。
- 依赖：`MINI-306`。
- 目标文件：
- `apps/wechat-mini/pages/index/index.wxml`
- `apps/wechat-mini/pages/index/index.wxss`
- 完成定义：首屏核心信息清晰，操作路径不超过两次点击。

### MINI-308 结果页 UI 重构

- 目标：重构结果页信息结构，消除内容堆叠与视觉噪声。
- 依赖：`MINI-306`、`MINI-301`、`MINI-302`。
- 目标文件：
- `apps/wechat-mini/pages/result/result.wxml`
- `apps/wechat-mini/pages/result/result.wxss`
- 完成定义：主结果、诗词、国潮、邮件、生图区域层次分明，状态提示统一。

### MINI-309 分享页 UI 重构

- 目标：重构分享页预览体验，明确“文本内容”和“图片预览”边界。
- 依赖：`MINI-306`。
- 目标文件：
- `apps/wechat-mini/pages/share/index.wxml`
- `apps/wechat-mini/pages/share/index.wxss`
- 完成定义：已生成卡片预览与用户自拍预览默认折叠、可展开，布局不重复不混叠。

### MINI-310 统一状态反馈组件化

- 目标：将加载中/失败/空态/重试统一为可复用样式和文案模式。
- 依赖：`MINI-306`。
- 目标文件：
- `apps/wechat-mini/pages/index/index.wxml`
- `apps/wechat-mini/pages/result/result.wxml`
- `apps/wechat-mini/pages/share/index.wxml`
- 完成定义：同类状态在不同页面视觉和文案一致。

## 阶段 2：数据与安全

### DATA-301 生成图保留与清理

- 目标：定义动态生成图保留期与自动清理策略。
- 依赖：`BE-303`。
- 目标文件：
- 新增 `services/wechat-api/app/services/media_cleanup_service.py`
- 完成定义：生成图有生命周期管理，不无限累积。

### DATA-302 域名与访问策略校验

- 目标：确保小程序仅使用合法可控域名加载图片。
- 依赖：`BE-303`、`MINI-301`。
- 目标文件：
- `apps/wechat-mini/config/index.js`
- 部署与配置文档
- 完成定义：体验版与正式版域名策略一致可验。

### DATA-303 授权与扣减审计

- 目标：记录用户授权、配额命中、积分扣减/回滚，支持审计追踪。
- 依赖：`BE-307`。
- 目标文件：
- 新增 `services/wechat-api/app/services/media_audit_service.py`
- `services/wechat-api/app/services/history_service.py`
- 完成定义：可按请求追踪“是否授权、是否扣分、是否回滚”。

## 阶段 3：回归与封板

### QA-301 供应商可用性回归

- 目标：覆盖正常、超时、限流、返回异常等场景。
- 依赖：`BE-301` 到 `BE-305`。
- 完成定义：主链路不因供应商异常整体失败。

### QA-302 真机弱网回归

- 目标：覆盖 5G/弱网下的图片加载与兜底效果。
- 依赖：`MINI-301` 到 `MINI-303`。
- 完成定义：页面可稳定展示图片或兜底图。

### QA-303 页面与邮件一致性回归

- 目标：同一次分析中，页面与邮件图片来源可追踪。
- 依赖：全部任务。
- 完成定义：不再出现“邮件有图、页面无图”。

### QA-304 授权/配额/积分规则回归

- 目标：覆盖“用户拒绝授权、同周超限、积分不足、失败回滚”场景。
- 依赖：`BE-306`、`BE-307`、`MINI-304`、`MINI-305`、`DATA-303`。
- 完成定义：规则行为和文案提示与产品要求一致。

### QA-305 UI 一致性与可用性回归

- 目标：覆盖首页/结果页/分享页的视觉一致性和交互可用性。
- 依赖：`MINI-306`、`MINI-307`、`MINI-308`、`MINI-309`、`MINI-310`。
- 完成定义：无文字重叠、无关键按钮误触、无长时间空白占位，iOS/Android 视觉一致。

## 建议开工顺序

1. `BE-301` -> `BE-302` -> `BE-303`
2. `BE-304` -> `BE-305` -> `BE-306` -> `BE-307`
3. `MINI-301` -> `MINI-302` -> `MINI-303` -> `MINI-304` -> `MINI-305`
4. `MINI-306` -> `MINI-307` -> `MINI-308` -> `MINI-309` -> `MINI-310`
5. `DATA-301` -> `DATA-302` -> `DATA-303`
6. `QA-301` -> `QA-302` -> `QA-303` -> `QA-304` -> `QA-305`

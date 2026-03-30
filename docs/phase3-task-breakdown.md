# 第三阶段任务分解（M2-M5 对齐版）

## 使用方式

本文件用于把第三阶段拆成里程碑交付，编号规则：

- `BE`：后端
- `MINI`：小程序
- `DATA`：数据与策略
- `QA`：回归与验收

当前第三阶段基线仍是“静态图池 + 云存储分发”。  
M3 的“授权弹窗/风格按钮/生成状态”按可插拔增强链路设计，默认可运行在静态图池模式，不阻塞主分析链路。

## 里程碑 M2：成本与风控闭环（硬约束）

### BE-304 幂等缓存与失败重试

- 目标：媒体增强请求具备幂等能力，并对可重试失败自动重试。
- 目标文件：
- `services/wechat-api/app/services/media_generate_service.py`
- `services/wechat-api/app/api/media_generate.py`
- 完成定义：
- `request_token` 同参重复提交可复用任务快照
- 上游失败按策略重试（重试次数/退避可配置）
- 失败返回统一 `error_code` 与 `retryable`

### BE-305 微信身份识别（openid/unionid）

- 目标：统一支持 `x-wx-openid` / `x-wx-unionid` 身份识别。
- 目标文件：
- `services/wechat-api/app/core/user_identity.py`
- `services/wechat-api/app/api/media_generate.py`
- 完成定义：
- 同时支持 openid 与 unionid
- 匿名请求返回 401
- 日志可识别 identity_type

### BE-306 周配额与积分校验

- 目标：实现每用户每自然周 1 次配额 + 积分校验/扣减/失败回滚。
- 目标文件：
- `services/wechat-api/app/services/quota_service.py`
- `services/wechat-api/app/services/points_service.py`
- `services/wechat-api/app/services/media_generate_service.py`
- 完成定义：
- 默认周配额=1（可配）
- 积分不足直接拒绝
- 任务失败自动触发积分回滚与配额释放

### BE-307 授权/配额/扣分审计日志

- 目标：关键风控动作可追踪、可审计。
- 目标文件：
- `services/wechat-api/app/services/media_generate_service.py`
- 完成定义：
- 记录授权校验、配额消耗、扣分、回滚、任务终态日志
- 日志具备 task_id、user_id、identity_type、reason 关键信息

### DATA-303 规则验收用例沉淀

- 目标：沉淀硬约束回归用例，保证后续迭代不回退。
- 目标文件：
- `docs/phase3-qa-regression-report.md`
- 完成定义：
- 四类场景回归可复现并通过：
- 拒绝授权
- 超周限额
- 积分不足
- 失败回滚

## 里程碑 M3：小程序生图交互上线（功能层）

### MINI-301 用户主动触发媒体增强

- 目标：用户点击后才触发媒体增强任务。
- 目标文件：
- `apps/wechat-mini/pages/result/*`
- `apps/wechat-mini/services/api.js`

### MINI-302 授权弹窗与同意记录

- 目标：明确告知“会使用自拍图进行媒体增强处理”，用户同意后才提交。
- 目标文件：
- `apps/wechat-mini/pages/result/*`
- 完成定义：
- 拒绝授权时不发请求
- 同意版本号随请求上送（`consent_version`）

### MINI-303 风格按钮（科技/国潮）

- 目标：用户可选风格后发起任务。
- 目标文件：
- `apps/wechat-mini/pages/result/*`
- 完成定义：支持 `tech` / `guochao` 风格参数传递

### MINI-304 状态反馈统一

- 目标：统一展示“生成中/失败/重试/完成”。
- 目标文件：
- `apps/wechat-mini/pages/result/*`
- `apps/wechat-mini/services/api.js`

### MINI-305 远端失败静态兜底

- 目标：增强链路失败时，自动回退静态图池，不影响主分析与邮件。
- 目标文件：
- `apps/wechat-mini/pages/result/*`
- `services/wechat-api/app/services/image_provider_service.py`

### MINI-310 主链路保护

- 目标：媒体增强为“可降级副链路”，失败不阻塞分析和邮件功能。
- 目标文件：
- `apps/wechat-mini/pages/index/*`
- `apps/wechat-mini/pages/result/*`
- `services/wechat-api/app/api/analyze.py`
- `services/wechat-api/app/api/email.py`

## 里程碑 M4：UI 重构上线（体验层）

### MINI-306 全局 UI Token

- 目标：建立统一 token（色彩、字号、间距、圆角、按钮层级）。
- 目标文件：
- `apps/wechat-mini/app.wxss`

### MINI-307 首页重构

- 目标：优化输入流与操作主次，减少拥挤与误触。
- 目标文件：
- `apps/wechat-mini/pages/index/*`

### MINI-308 结果页重构

- 目标：优化信息层级、图片区、反馈区，消除遮挡和重叠。
- 目标文件：
- `apps/wechat-mini/pages/result/*`

### MINI-309 分享页重构

- 目标：优化分享卡导出体验，避免信息重复与排版拥挤。
- 目标文件：
- `apps/wechat-mini/pages/share/*`

## 里程碑 M5：数据与域名策略收口 + 全量回归

### DATA-301 生成图生命周期治理

- 目标：临时资源可追踪、可清理，避免长期堆积。
- 目标文件：
- `services/wechat-api/app/services/media_retention_service.py`
- `services/wechat-api/app/services/retention_cleanup_service.py`

### DATA-302 域名策略校验

- 目标：体验版/正式版域名策略一致，真机加载稳定。
- 目标文件：
- `apps/wechat-mini/config/index.js`
- 部署文档

### QA-301 图池命中回归

- 覆盖不同情绪与风格下命中正确性。

### QA-302 5G/弱网回归

- 覆盖网络抖动场景的加载、重试与兜底。

### QA-303 页面与邮件一致性回归

- 避免“页面无图、邮件有图”不一致。

### QA-304 风控约束回归

- 覆盖授权拒绝、周限额、积分不足、失败回滚四类场景。

### QA-305 全量回归与封板报告

- 输出自动化 + 真机专项回归结论，并更新 checklist 全量勾选状态。


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

## 建议开工顺序

1. `BE-301` -> `BE-302` -> `BE-303`
2. `BE-304` -> `BE-305`
3. `MINI-301` -> `MINI-302` -> `MINI-303`
4. `DATA-301` -> `DATA-302`
5. `QA-301` -> `QA-302` -> `QA-303`

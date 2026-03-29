# 第三阶段任务分解（静态图池稳定链路，必须完成）

## 使用方式

本文件对应第三阶段“静态图池能力稳定化”目标，任务编号沿用现有规则：

- `BE`：后端
- `MINI`：小程序
- `DATA`：数据与安全
- `QA`：回归与验收

## 阶段 0：后端图池底座（必须先做）

### BE-301 图片素材元数据模型

- 目标：建立“科技/国潮静态图池”元数据结构。
- 依赖：无。
- 目标文件：
- 新增 `services/wechat-api/app/services/media_asset_service.py`
- 新增 `services/wechat-api/app/schemas/media_asset.py`
- 完成定义：可按风格、标签、权重筛选候选素材。

### BE-302 图池选择策略

- 目标：根据情绪语境（主情绪、触发标签）做加权随机选图。
- 依赖：`BE-301`。
- 目标文件：
- `services/wechat-api/app/services/media_generate_service.py`
- 完成定义：同一语境可输出多样化结果，不固定同一张图。

### BE-303 用户去重策略

- 目标：同一用户短期内尽量不重复命中同一素材。
- 依赖：`BE-302`。
- 目标文件：
- `services/wechat-api/app/services/media_generate_service.py`
- 完成定义：支持按用户维度做近 7 天去重。

### BE-304 云存储 URL 统一化

- 目标：素材统一从腾讯云存储（COS/云存储）域名输出。
- 依赖：`BE-301`。
- 目标文件：
- `services/wechat-api/app/services/storage_service.py`
- `services/wechat-api/app/services/media_generate_service.py`
- 完成定义：小程序只接收自有域名 URL 或 file_id。

### BE-305 兜底与开关

- 目标：图池命中失败时回退到本地静态兜底图。
- 依赖：`BE-304`。
- 目标文件：
- `services/wechat-api/app/services/image_provider_service.py`
- 完成定义：任何情况下主分析结果不受阻塞。

## 阶段 1：小程序接入

### MINI-301 结果页统一图片来源

- 目标：结果页只消费后端统一返回的图片引用。
- 依赖：`BE-304`。
- 目标文件：
- `apps/wechat-mini/pages/result/result.js`
- `apps/wechat-mini/pages/result/result.wxml`
- 完成定义：不再依赖第三方生图 URL。

### MINI-302 状态反馈统一

- 目标：保留“加载中/成功/失败/兜底”状态提示。
- 依赖：`MINI-301`。
- 目标文件：
- `apps/wechat-mini/pages/result/result.js`
- `apps/wechat-mini/pages/result/result.wxml`
- 完成定义：用户可明确感知当前展示状态。

### MINI-303 UI 优化收口

- 目标：继续优化首页/结果页/分享页视觉层级与可读性。
- 依赖：无。
- 目标文件：
- `apps/wechat-mini/pages/index/*`
- `apps/wechat-mini/pages/result/*`
- `apps/wechat-mini/pages/share/*`
- 完成定义：无重叠、无遮挡、主次清晰。

## 阶段 2：数据与安全

### DATA-301 图池运维机制

- 目标：支持素材上下线、权重调整、标签维护。
- 依赖：`BE-301`。
- 目标文件：
- 新增 `services/wechat-api/app/services/media_asset_admin_service.py`
- 完成定义：可运维地迭代图池内容。

### DATA-302 域名与访问策略

- 目标：确保体验版/正式版可稳定访问云存储图片域名。
- 依赖：`BE-304`、`MINI-301`。
- 目标文件：
- `apps/wechat-mini/config/index.js`
- 部署文档
- 完成定义：真机访问无跨域/白名单问题。

## 阶段 3：回归与封板

### QA-301 图池命中回归

- 目标：覆盖不同情绪标签下的素材命中正确性。
- 依赖：`BE-301` 到 `BE-303`。
- 完成定义：科技/国潮均可稳定命中。

### QA-302 弱网真机回归

- 目标：覆盖 5G/弱网下图片加载与兜底表现。
- 依赖：`MINI-301`、`MINI-302`。
- 完成定义：无长期空白区域。

### QA-303 页面与邮件一致性回归

- 目标：确保页面展示图片与邮件图片来源一致。
- 依赖：全部任务。
- 完成定义：不再出现“邮件有图、页面无图”。

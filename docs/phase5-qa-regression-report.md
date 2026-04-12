# 第五阶段 QA 回归报告

- 执行时间(UTC+8): `2026-04-12`
- 代码仓库: `/Users/babytech/github/emotion_culture`
- 总体结果: **执行中（主链路真机回归已补齐，专项边界验证待继续）**

## 文档说明

本文件用于承接第五阶段回归结果。当前阶段已开始真机回归，但仍处于分批执行阶段，因此本报告先记录已经确认通过的真机结果，并保留剩余待测项。

配套文档：

- [phase5-development-plan.md](/Users/babytech/github/emotion_culture/docs/phase5-development-plan.md)
- [phase5-task-breakdown.md](/Users/babytech/github/emotion_culture/docs/phase5-task-breakdown.md)
- [phase5-implementation-checklist.md](/Users/babytech/github/emotion_culture/docs/phase5-implementation-checklist.md)
- [phase5-m1-device-smoke-checklist.md](/Users/babytech/github/emotion_culture/docs/phase5-m1-device-smoke-checklist.md)

## 分任务汇总（执行中）

| QA 任务 | 通过/总数 | 结果 |
|---|---:|---|
| QA-511 | 核心项通过 | 已通过 |
| QA-521 | 8/8 | 已通过 |
| QA-531 | 2/2 | 本轮新增用例通过 |
| QA-532 | 主链路真机通过 | 执行中 |
| QA-541 | 7/7（结果页首轮） | 执行中 |

## 最新真机进展（截至 2026-04-12）

截至 `2026-04-12`，已确认通过的真机用例如下：

- `CASE-511` 首次进入授权门、同意后进入、再次打开不重复拦截、自拍权限前置、录音中提交自动收口等核心链路已通过
- `CASE-521-R5` 结果页“返回继续分析”后，文字 / 自拍 / 录音 / 提交态已默认清空
- `CASE-521-R6` 历史详情“继续分析”后，分析工作台为干净状态
- `CASE-521-R7` 存在未完成任务时，重新进入分析页会自动续查
- `CASE-531-R1` 分享页可通过右上角菜单正常分享到朋友圈
- `CASE-531-R2` 转发给好友、保存相册、预览生成图片链路未回退
- 首页“历史上的今天”折叠板块展示通过
- 记录页“历史上的今天”折叠板块展示通过
- 当日历史内容展开查看通过
- `2026-04-12` 在 `seed` 模式下可正常展示当天“历史上的今天”内容
- 分析结果页已补 `首页 / 记录页` 直达入口，真机跳转通过
- 完成一次分析后，从结果页切到 `首页 / 记录页` 时，“历史上的今天”可自动展开
- 自拍清晰度调优与 `FACE_TOO_BLUR / FACE_NOT_FOUND` 回归通过
- `M2` 弱网专项新增回归通过：上传重试、轮询中断自动恢复、长耗时状态文案、失败可重试提示、待完成任务恢复闭环
- 结果页视觉二次升级首轮真机回归通过（`CASE-541-R1` ~ `CASE-541-R7` 全部 PASS）

配套说明：

- 上述结果与 [phase5-m1-device-smoke-checklist.md](/Users/babytech/github/emotion_culture/docs/phase5-m1-device-smoke-checklist.md) 中最新复测项一致
- 自拍页“重拍 / 使用这张”真机链路此前也已通过
- 自拍清晰度与 `FACE_TOO_BLUR / FACE_NOT_FOUND` 调优已在最新体验版 + 最新后端上完成专项回归
- “历史上的今天”仍待继续补 `BE-532/BE-533` 的外部 AI 搜索接入与事实分层
- `QA-532` 当前先记为“主链路真机通过”，缓存命中 / 搜索失败降级 / 审核拦截等专项回归仍待继续补测
- `QA-541` 当前先记为“结果页首轮通过”，全局视觉项（首页 / 记录页 / 分享页 / 我的页）仍待继续补测

## 计划回归范围

### QA-511 首次授权门与权限治理回归

- 首次进入不再直接落首页
- 授权完成后可正常进入首页
- 自拍权限拒绝后可恢复
- 录音中提交场景行为符合预期
- 建议先执行一轮最小真机冒烟清单：
- [phase5-m1-device-smoke-checklist.md](/Users/babytech/github/emotion_culture/docs/phase5-m1-device-smoke-checklist.md)

### QA-521 5G / 弱网主链路回归

- 上传、建任务、轮询、恢复、结果页打开链路稳定
- “任务仍在处理中”路径可闭环
- 再次分析默认清空旧输入

### QA-531 当前页分享到朋友圈回归

- 当前分享页可触发分享到朋友圈
- `onShareAppMessage` 不回退
- 生成卡片、保存相册、朋友圈分享三条链路互不干扰

### QA-532 “历史上的今天”模块回归

- 正常日期可展示
- 分析完成后可从结果页切入首页 / 记录页并联动展开
- 缓存命中可展示
- 搜索失败可安全降级
- 审核拦截不暴露异常信息

### QA-541 全局视觉与真机回归

- 首页、结果页、分享页、记录页、我的页视觉一致
- iPhone 窄屏 / 刘海屏 / Android 全面屏无遮挡
- 关键动效与状态反馈无明显回退

## 用例明细（持续补充）

| 用例ID | QA | 用例 | 结果 | 耗时(ms) | 说明 |
|---|---|---|---|---:|---|
| CASE-521-R5 | QA-521 | 结果页返回继续分析后清空旧输入 | PASS | TBD | 真机已通过 |
| CASE-521-R6 | QA-521 | 历史详情继续分析后清空旧输入 | PASS | TBD | 真机已通过 |
| CASE-521-R7 | QA-521 | 待完成任务返回分析页自动续查 | PASS | TBD | 真机已通过 |
| CASE-521-R8 | QA-521 | 弱网下上传自动重试并可继续分析 | PASS | TBD | 真机已通过 |
| CASE-521-R9 | QA-521 | 轮询中断自动恢复并最终出结果 | PASS | TBD | 真机已通过 |
| CASE-521-R10 | QA-521 | 长耗时状态文案可读且分阶段 | PASS | TBD | 真机已通过 |
| CASE-521-R11 | QA-521 | 网络失败提示可重试且不丢输入 | PASS | TBD | 真机已通过 |
| CASE-521-R12 | QA-521 | 待完成任务恢复查询链路闭环 | PASS | TBD | 真机已通过 |
| CASE-531-R1 | QA-531 | 当前分享页分享到朋友圈 | PASS | TBD | 真机已通过 |
| CASE-531-R2 | QA-531 | 好友转发与保存相册不回退 | PASS | TBD | 真机已通过 |
| CASE-532-H1 | QA-532 | 首页展示“历史上的今天”折叠板块 | PASS | TBD | 真机已通过 |
| CASE-532-H2 | QA-532 | 记录页展示“历史上的今天”折叠板块 | PASS | TBD | 真机已通过 |
| CASE-532-H3 | QA-532 | 历史内容展开查看 | PASS | TBD | 真机已通过 |
| CASE-532-H4 | QA-532 | 结果页展示“首页 / 记录页”直达入口 | PASS | TBD | 真机已通过 |
| CASE-532-H5 | QA-532 | `2026-04-12` 在 `seed` 模式下展示当天历史内容 | PASS | TBD | 真机已通过 |
| CASE-532-H6 | QA-532 | 分析完成后切至首页 / 记录页自动展开历史上的今天 | PASS | TBD | 真机已通过 |
| CASE-522-S1 | QA-521 | 自拍清晰度与人脸质检调优回归 | PASS | TBD | 真机已通过 |
| CASE-541-R1 | QA-541 | 结果页“继续查看”导航区层级清晰 | PASS | TBD | 真机已通过 |
| CASE-541-R2 | QA-541 | 结果页“快捷动作”层级与强调正确 | PASS | TBD | 真机已通过 |
| CASE-541-R3 | QA-541 | 结果页四个快捷动作功能不回退 | PASS | TBD | 真机已通过 |
| CASE-541-R4 | QA-541 | 结果页六个导航入口可正确跳转 | PASS | TBD | 真机已通过 |
| CASE-541-R5 | QA-541 | iPhone 小屏动作台无遮挡 | PASS | TBD | 真机已通过 |
| CASE-541-R6 | QA-541 | 邮箱面板开合与动作台无冲突 | PASS | TBD | 真机已通过 |
| CASE-541-R7 | QA-541 | 弱网下结果页动作区样式稳定 | PASS | TBD | 真机已通过 |

## 稳定性指标（待补）

- `analyze_create_task_success_ratio`: `TBD`
- `analyze_poll_complete_ratio`: `TBD`
- `result_open_success_ratio`: `TBD`
- `share_timeline_success_ratio`: `TBD`
- `today_history_cache_hit_ratio`: `TBD`

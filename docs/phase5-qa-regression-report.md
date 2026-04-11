# 第五阶段 QA 回归报告

- 执行时间(UTC): `2026-04-11`
- 代码仓库: `/Users/babytech/github/emotion_culture`
- 总体结果: **执行中（部分真机用例已通过）**

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
| QA-511 | 0/0 | 执行中 |
| QA-521 | 3/3 | 本轮新增用例通过 |
| QA-531 | 2/2 | 本轮新增用例通过 |
| QA-532 | 0/0 | TBD |
| QA-541 | 0/0 | TBD |

## 最新真机进展（2026-04-11）

本轮新增确认通过的真机用例如下：

- `CASE-521-R5` 结果页“返回继续分析”后，文字 / 自拍 / 录音 / 提交态已默认清空
- `CASE-521-R6` 历史详情“继续分析”后，分析工作台为干净状态
- `CASE-521-R7` 存在未完成任务时，重新进入分析页会自动续查
- `CASE-531-R1` 分享页可通过右上角菜单正常分享到朋友圈
- `CASE-531-R2` 转发给好友、保存相册、预览生成图片链路未回退

配套说明：

- 上述结果与 [phase5-m1-device-smoke-checklist.md](/Users/babytech/github/emotion_culture/docs/phase5-m1-device-smoke-checklist.md) 中最新复测项一致
- 自拍页“重拍 / 使用这张”真机链路此前也已通过
- 自拍清晰度与 `FACE_TOO_BLUR / FACE_NOT_FOUND` 调优已完成代码修改，但尚未在最新体验版 + 最新后端上完成专项回归

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
| CASE-531-R1 | QA-531 | 当前分享页分享到朋友圈 | PASS | TBD | 真机已通过 |
| CASE-531-R2 | QA-531 | 好友转发与保存相册不回退 | PASS | TBD | 真机已通过 |

## 稳定性指标（待补）

- `analyze_create_task_success_ratio`: `TBD`
- `analyze_poll_complete_ratio`: `TBD`
- `result_open_success_ratio`: `TBD`
- `share_timeline_success_ratio`: `TBD`
- `today_history_cache_hit_ratio`: `TBD`

# 第五阶段 QA 回归报告

- 执行时间(UTC): `TBD`
- 代码仓库: `/Users/babytech/github/emotion_culture`
- 总体结果: **待执行**

## 文档说明

本文件用于承接第五阶段回归结果。当前阶段尚未进入正式 QA 执行，因此先保留回归结构与目标任务，待实现完成后再补充实际结果。

配套文档：

- [phase5-development-plan.md](/Users/babytech/github/emotion_culture/docs/phase5-development-plan.md)
- [phase5-task-breakdown.md](/Users/babytech/github/emotion_culture/docs/phase5-task-breakdown.md)
- [phase5-implementation-checklist.md](/Users/babytech/github/emotion_culture/docs/phase5-implementation-checklist.md)

## 分任务汇总（待执行）

| QA 任务 | 通过/总数 | 结果 |
|---|---:|---|
| QA-511 | 0/0 | TBD |
| QA-521 | 0/0 | TBD |
| QA-531 | 0/0 | TBD |
| QA-532 | 0/0 | TBD |
| QA-541 | 0/0 | TBD |

## 计划回归范围

### QA-511 首次授权门与权限治理回归

- 首次进入不再直接落首页
- 授权完成后可正常进入首页
- 自拍权限拒绝后可恢复
- 录音中提交场景行为符合预期

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

## 用例明细（待补）

| 用例ID | QA | 用例 | 结果 | 耗时(ms) | 说明 |
|---|---|---|---|---:|---|
| 待补 | TBD | TBD | TBD | TBD | 待执行后补充 |

## 稳定性指标（待补）

- `analyze_create_task_success_ratio`: `TBD`
- `analyze_poll_complete_ratio`: `TBD`
- `result_open_success_ratio`: `TBD`
- `share_timeline_success_ratio`: `TBD`
- `today_history_cache_hit_ratio`: `TBD`

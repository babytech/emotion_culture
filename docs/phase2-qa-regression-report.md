# 第二阶段 QA 回归报告

- 执行时间(UTC): `2026-03-27T16:19:58Z`
- 代码仓库: `/Users/babytech/github/emotion_culture`
- 历史存储隔离路径: `/var/folders/bz/0pr9vt717cx_1q06t_g5_v5c0000gn/T/phase2_qa_829o_yn5/history_store.json`
- 总体结果: **PASS** (`15/15` 已执行通过，`15/15` 已执行)

## 分任务汇总

| QA 任务 | 通过/总数 | 结果 |
|---|---:|---|
| QA-201 | 4/4 | PASS |
| QA-202 | 4/4 | PASS |
| QA-203 | 3/3 | PASS |
| QA-204 | 4/4 | PASS |

## 用例明细

| 用例ID | QA | 用例 | 结果 | 耗时(ms) | 说明 |
|---|---|---|---|---:|---|
| QA-201-1 | QA-201 | 小程序日历链路通过 | PASS | 13.2 | PASS |
| QA-201-2 | QA-201 | 小程序连续打卡链路通过 | PASS | 8.0 | PASS |
| QA-201-3 | QA-201 | 小程序周报链路通过 | PASS | 10.3 | PASS |
| QA-201-4 | QA-201 | 小程序收藏链路通过 | PASS | 8.3 | PASS |
| QA-202-1 | QA-202 | 后端日历聚合口径一致 | PASS | 6.8 | PASS |
| QA-202-2 | QA-202 | 后端周报聚合口径一致 | PASS | 8.2 | PASS |
| QA-202-3 | QA-202 | 收藏接口权限与越权保护 | PASS | 11.9 | PASS |
| QA-202-4 | QA-202 | 配置守卫语义一致 | PASS | 8.5 | PASS |
| QA-203-1 | QA-203 | PC 趋势摘要回看可用 | PASS | 1063.6 | PASS |
| QA-203-2 | QA-203 | PC 周报回看可用 | PASS | 23.3 | PASS |
| QA-203-3 | QA-203 | PC 收藏回看可用 | PASS | 18.1 | PASS |
| QA-204-1 | QA-204 | 日历聚合接口耗时达标 | PASS | 18.2 | PASS |
| QA-204-2 | QA-204 | 周报聚合接口耗时达标 | PASS | 38.7 | PASS |
| QA-204-3 | QA-204 | 收藏写接口耗时达标 | PASS | 22.6 | PASS |
| QA-204-4 | QA-204 | 留存接口失败不阻塞主分析 | PASS | 8.9 | PASS |

## 稳定性指标

- `calendar_latency_max_s`: `0.0040`
- `weekly_report_latency_max_s`: `0.0246`
- `favorite_write_latency_max_s`: `0.0038`
- `retention_fallback_ratio`: `1.0000`

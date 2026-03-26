# 第一阶段 QA 回归报告

- 执行时间(UTC): `2026-03-26T12:09:10Z`
- 代码仓库: `/Users/babytech/github/emotion_culture`
- 历史存储隔离路径: `/var/folders/bz/0pr9vt717cx_1q06t_g5_v5c0000gn/T/phase1_qa_sh1niaem/history_store.json`
- 总体结果: **PASS** (`21/21` 通过)

## 分任务汇总

| QA 任务 | 通过/总数 | 结果 |
|---|---:|---|
| QA-001 | 5/5 | PASS |
| QA-002 | 6/6 | PASS |
| QA-003 | 6/6 | PASS |
| QA-004 | 4/4 | PASS |

## 用例明细

| 用例ID | QA | 用例 | 结果 | 耗时(ms) | 说明 |
|---|---|---|---|---:|---|
| QA-001-1 | QA-001 | 小程序文本链路通过 | PASS | 10.1 | PASS |
| QA-001-2 | QA-001 | 小程序语音链路通过 | PASS | 2186.7 | PASS |
| QA-001-3 | QA-001 | 小程序自拍链路通过 | PASS | 170.8 | PASS |
| QA-001-4 | QA-001 | 小程序语音失败后可恢复 | PASS | 9.2 | PASS |
| QA-001-5 | QA-001 | 小程序自拍失败后可恢复 | PASS | 21.8 | PASS |
| QA-002-1 | QA-002 | PC 文本链路通过 | PASS | 71.3 | PASS |
| QA-002-2 | QA-002 | PC 录音链路通过 | PASS | 307.6 | PASS |
| QA-002-3 | QA-002 | PC 摄像头链路通过 | PASS | 173.2 | PASS |
| QA-002-4 | QA-002 | PC 录音失败后可恢复 | PASS | 66.3 | PASS |
| QA-002-5 | QA-002 | PC 拍照失败后可恢复 | PASS | 75.7 | PASS |
| QA-002-6 | QA-002 | PC 与小程序主情绪口径一致 | PASS | 68.4 | PASS |
| QA-003-1 | QA-003 | 历史摘要不存原始媒体字段 | PASS | 405.5 | PASS |
| QA-003-2 | QA-003 | 历史保存开关即时生效 | PASS | 13.4 | PASS |
| QA-003-3 | QA-003 | 支持删除单条与清空全部历史 | PASS | 15.6 | PASS |
| QA-003-4 | QA-003 | 180 天摘要保留策略可验证 | PASS | 7.3 | PASS |
| QA-003-5 | QA-003 | 原始媒体临时文件可自动清理 | PASS | 385.7 | PASS |
| QA-003-6 | QA-003 | cloud file_id 过期媒体可自动清理 | PASS | 401.5 | PASS |
| QA-004-1 | QA-004 | 文本分析耗时 <= 3s | PASS | 11.4 | PASS |
| QA-004-2 | QA-004 | 自拍/拍照分析耗时 <= 8s | PASS | 440.8 | PASS |
| QA-004-3 | QA-004 | 语音分析耗时 <= 12s | PASS | 759.7 | PASS |
| QA-004-4 | QA-004 | 邮件失败不阻塞主结果且可重试 | PASS | 4013.9 | PASS |

## 稳定性指标

- `analyze_vs_email_analyze_s`: `0.003`
- `analyze_vs_email_send_s`: `2.003`
- `selfie_latency_max_s`: `0.154`
- `text_latency_max_s`: `0.003`
- `voice_latency_max_s`: `0.26`

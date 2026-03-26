# 第一阶段 QA 回归报告

- 执行时间(UTC): `2026-03-26T16:58:35Z`
- 代码仓库: `/Users/babytech/github/emotion_culture`
- 历史存储隔离路径: `/var/folders/bz/0pr9vt717cx_1q06t_g5_v5c0000gn/T/phase1_qa_7ij4n7j9/history_store.json`
- 总体结果: **PASS** (`26/26` 通过)

## 分任务汇总

| QA 任务 | 通过/总数 | 结果 |
|---|---:|---|
| QA-001 | 9/9 | PASS |
| QA-002 | 6/6 | PASS |
| QA-003 | 6/6 | PASS |
| QA-004 | 5/5 | PASS |

## 用例明细

| 用例ID | QA | 用例 | 结果 | 耗时(ms) | 说明 |
|---|---|---|---|---:|---|
| QA-001-1 | QA-001 | 小程序文本链路通过 | PASS | 6.1 | PASS |
| QA-001-2 | QA-001 | 小程序语音链路通过 | PASS | 2023.8 | PASS |
| QA-001-3 | QA-001 | 小程序自拍链路通过 | PASS | 157.8 | PASS |
| QA-001-4 | QA-001 | 小程序语音失败后可恢复 | PASS | 3.9 | PASS |
| QA-001-5 | QA-001 | 小程序自拍失败后可恢复 | PASS | 19.8 | PASS |
| QA-001-6 | QA-001 | 文本+语音在空转写时自动降级 | PASS | 224.6 | PASS |
| QA-001-7 | QA-001 | ASR 关闭时语音链路仍可用 | PASS | 240.8 | PASS |
| QA-001-8 | QA-001 | SPEECH_STT_ENDPOINT 支持可配置请求格式 | PASS | 220.7 | PASS |
| QA-001-9 | QA-001 | 内置腾讯 STT 网关可用 | PASS | 3.2 | PASS |
| QA-002-1 | QA-002 | PC 文本链路通过 | PASS | 76.1 | PASS |
| QA-002-2 | QA-002 | PC 录音链路通过 | PASS | 282.2 | PASS |
| QA-002-3 | QA-002 | PC 摄像头链路通过 | PASS | 160.3 | PASS |
| QA-002-4 | QA-002 | PC 录音失败后可恢复 | PASS | 55.7 | PASS |
| QA-002-5 | QA-002 | PC 拍照失败后可恢复 | PASS | 97.7 | PASS |
| QA-002-6 | QA-002 | PC 与小程序主情绪口径一致 | PASS | 59.7 | PASS |
| QA-003-1 | QA-003 | 历史摘要不存原始媒体字段 | PASS | 385.1 | PASS |
| QA-003-2 | QA-003 | 历史保存开关即时生效 | PASS | 13.5 | PASS |
| QA-003-3 | QA-003 | 支持删除单条与清空全部历史 | PASS | 15.6 | PASS |
| QA-003-4 | QA-003 | 180 天摘要保留策略可验证 | PASS | 6.6 | PASS |
| QA-003-5 | QA-003 | 原始媒体临时文件可自动清理 | PASS | 368.1 | PASS |
| QA-003-6 | QA-003 | cloud file_id 过期媒体可自动清理 | PASS | 369.5 | PASS |
| QA-004-1 | QA-004 | 文本分析耗时 <= 3s | PASS | 12.8 | PASS |
| QA-004-2 | QA-004 | 自拍/拍照分析耗时 <= 8s | PASS | 408.7 | PASS |
| QA-004-3 | QA-004 | 语音分析耗时 <= 12s | PASS | 698.2 | PASS |
| QA-004-4 | QA-004 | 邮件失败不阻塞主结果且可重试 | PASS | 4013.7 | PASS |
| QA-004-5 | QA-004 | 邮件接口可接收用户录音附件 | PASS | 1.7 | PASS |

## 稳定性指标

- `analyze_vs_email_analyze_s`: `0.003`
- `analyze_vs_email_send_s`: `2.008`
- `selfie_latency_max_s`: `0.15`
- `text_latency_max_s`: `0.004`
- `voice_latency_max_s`: `0.234`

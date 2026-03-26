# 第一阶段 QA 回归报告

- 执行时间(UTC): `2026-03-26T16:52:03Z`
- 代码仓库: `/Users/babytech/github/emotion_culture`
- 历史存储隔离路径: `/var/folders/bz/0pr9vt717cx_1q06t_g5_v5c0000gn/T/phase1_qa_7u6a05u5/history_store.json`
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
| QA-001-1 | QA-001 | 小程序文本链路通过 | PASS | 6.8 | PASS |
| QA-001-2 | QA-001 | 小程序语音链路通过 | PASS | 2366.5 | PASS |
| QA-001-3 | QA-001 | 小程序自拍链路通过 | PASS | 162.7 | PASS |
| QA-001-4 | QA-001 | 小程序语音失败后可恢复 | PASS | 4.2 | PASS |
| QA-001-5 | QA-001 | 小程序自拍失败后可恢复 | PASS | 21.1 | PASS |
| QA-001-6 | QA-001 | 文本+语音在空转写时自动降级 | PASS | 268.6 | PASS |
| QA-001-7 | QA-001 | ASR 关闭时语音链路仍可用 | PASS | 268.8 | PASS |
| QA-001-8 | QA-001 | SPEECH_STT_ENDPOINT 支持可配置请求格式 | PASS | 268.7 | PASS |
| QA-001-9 | QA-001 | 内置腾讯 STT 网关可用 | PASS | 3.3 | PASS |
| QA-002-1 | QA-002 | PC 文本链路通过 | PASS | 78.3 | PASS |
| QA-002-2 | QA-002 | PC 录音链路通过 | PASS | 316.1 | PASS |
| QA-002-3 | QA-002 | PC 摄像头链路通过 | PASS | 199.5 | PASS |
| QA-002-4 | QA-002 | PC 录音失败后可恢复 | PASS | 66.8 | PASS |
| QA-002-5 | QA-002 | PC 拍照失败后可恢复 | PASS | 55.8 | PASS |
| QA-002-6 | QA-002 | PC 与小程序主情绪口径一致 | PASS | 62.5 | PASS |
| QA-003-1 | QA-003 | 历史摘要不存原始媒体字段 | PASS | 420.7 | PASS |
| QA-003-2 | QA-003 | 历史保存开关即时生效 | PASS | 13.5 | PASS |
| QA-003-3 | QA-003 | 支持删除单条与清空全部历史 | PASS | 32.7 | PASS |
| QA-003-4 | QA-003 | 180 天摘要保留策略可验证 | PASS | 10.6 | PASS |
| QA-003-5 | QA-003 | 原始媒体临时文件可自动清理 | PASS | 409.1 | PASS |
| QA-003-6 | QA-003 | cloud file_id 过期媒体可自动清理 | PASS | 418.4 | PASS |
| QA-004-1 | QA-004 | 文本分析耗时 <= 3s | PASS | 31.6 | PASS |
| QA-004-2 | QA-004 | 自拍/拍照分析耗时 <= 8s | PASS | 544.8 | PASS |
| QA-004-3 | QA-004 | 语音分析耗时 <= 12s | PASS | 800.5 | PASS |
| QA-004-4 | QA-004 | 邮件失败不阻塞主结果且可重试 | PASS | 4036.2 | PASS |
| QA-004-5 | QA-004 | 邮件接口可接收用户录音附件 | PASS | 1.9 | PASS |

## 稳定性指标

- `analyze_vs_email_analyze_s`: `0.004`
- `analyze_vs_email_send_s`: `2.022`
- `selfie_latency_max_s`: `0.239`
- `text_latency_max_s`: `0.005`
- `voice_latency_max_s`: `0.271`

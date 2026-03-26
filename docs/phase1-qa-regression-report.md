# 第一阶段 QA 回归报告

- 执行时间(UTC): `2026-03-26T14:40:33Z`
- 代码仓库: `/Users/babytech/github/emotion_culture`
- 历史存储隔离路径: `/var/folders/bz/0pr9vt717cx_1q06t_g5_v5c0000gn/T/phase1_qa_n2gg35j6/history_store.json`
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
| QA-001-1 | QA-001 | 小程序文本链路通过 | PASS | 5.5 | PASS |
| QA-001-2 | QA-001 | 小程序语音链路通过 | PASS | 1625.9 | PASS |
| QA-001-3 | QA-001 | 小程序自拍链路通过 | PASS | 109.3 | PASS |
| QA-001-4 | QA-001 | 小程序语音失败后可恢复 | PASS | 3.6 | PASS |
| QA-001-5 | QA-001 | 小程序自拍失败后可恢复 | PASS | 17.3 | PASS |
| QA-001-6 | QA-001 | 文本+语音在空转写时自动降级 | PASS | 182.8 | PASS |
| QA-001-7 | QA-001 | 无 STT 配置时语音链路仍可用 | PASS | 180.4 | PASS |
| QA-001-8 | QA-001 | SPEECH_STT_ENDPOINT 支持可配置请求格式 | PASS | 175.3 | PASS |
| QA-001-9 | QA-001 | 内置腾讯 STT 网关可用 | PASS | 3.0 | PASS |
| QA-002-1 | QA-002 | PC 文本链路通过 | PASS | 61.4 | PASS |
| QA-002-2 | QA-002 | PC 录音链路通过 | PASS | 220.7 | PASS |
| QA-002-3 | QA-002 | PC 摄像头链路通过 | PASS | 114.3 | PASS |
| QA-002-4 | QA-002 | PC 录音失败后可恢复 | PASS | 44.6 | PASS |
| QA-002-5 | QA-002 | PC 拍照失败后可恢复 | PASS | 60.4 | PASS |
| QA-002-6 | QA-002 | PC 与小程序主情绪口径一致 | PASS | 47.3 | PASS |
| QA-003-1 | QA-003 | 历史摘要不存原始媒体字段 | PASS | 267.7 | PASS |
| QA-003-2 | QA-003 | 历史保存开关即时生效 | PASS | 11.3 | PASS |
| QA-003-3 | QA-003 | 支持删除单条与清空全部历史 | PASS | 13.9 | PASS |
| QA-003-4 | QA-003 | 180 天摘要保留策略可验证 | PASS | 6.4 | PASS |
| QA-003-5 | QA-003 | 原始媒体临时文件可自动清理 | PASS | 269.4 | PASS |
| QA-003-6 | QA-003 | cloud file_id 过期媒体可自动清理 | PASS | 268.8 | PASS |
| QA-004-1 | QA-004 | 文本分析耗时 <= 3s | PASS | 10.0 | PASS |
| QA-004-2 | QA-004 | 自拍/拍照分析耗时 <= 8s | PASS | 297.1 | PASS |
| QA-004-3 | QA-004 | 语音分析耗时 <= 12s | PASS | 511.7 | PASS |
| QA-004-4 | QA-004 | 邮件失败不阻塞主结果且可重试 | PASS | 4031.2 | PASS |
| QA-004-5 | QA-004 | 邮件接口可接收用户录音附件 | PASS | 4.5 | PASS |

## 稳定性指标

- `analyze_vs_email_analyze_s`: `0.003`
- `analyze_vs_email_send_s`: `2.013`
- `selfie_latency_max_s`: `0.101`
- `text_latency_max_s`: `0.003`
- `voice_latency_max_s`: `0.171`

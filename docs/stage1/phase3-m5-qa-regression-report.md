# 第三阶段 M5 QA 回归报告

- 执行时间(UTC): `2026-04-01T14:55:35Z`
- 代码仓库: `/Users/babytech/github/emotion_culture`
- 隔离工作目录: `/var/folders/bz/0pr9vt717cx_1q06t_g5_v5c0000gn/T/phase3_qa_ynon_olz`
- 总体结果: **PASS** (`11/11` 通过)

## 分任务汇总

| 任务 | 通过/总数 | 结果 |
|---|---:|---|
| DATA-301 | 1/1 | PASS |
| DATA-302 | 1/1 | PASS |
| QA-301 | 2/2 | PASS |
| QA-302 | 2/2 | PASS |
| QA-303 | 1/1 | PASS |
| QA-304 | 4/4 | PASS |

## 用例明细

| 用例ID | 任务 | 用例 | 结果 | 耗时(ms) | 说明 |
|---|---|---|---|---:|---|
| DATA-301-1 | DATA-301 | 媒体生命周期追踪与过期清理有效 | PASS | 0.7 | PASS |
| DATA-302-1 | DATA-302 | 小程序域名与云环境配置口径一致 | PASS | 0.7 | PASS |
| QA-301-1 | QA-301 | 古典风图池按情绪标签命中 | PASS | 6.0 | PASS |
| QA-301-2 | QA-301 | 国潮风图池按触发标签命中 | PASS | 2.0 | PASS |
| QA-302-1 | QA-302 | 弱网下 URL 失败可回退 file_id/本地素材 | PASS | 0.1 | PASS |
| QA-302-2 | QA-302 | 风格图空池失败不阻塞主分析与邮件 | PASS | 56.2 | PASS |
| QA-303-1 | QA-303 | 页面与邮件解析的静态图片来源一致 | PASS | 32.9 | PASS |
| QA-304-1 | QA-304 | 拒绝授权时直接阻断 | PASS | 1.0 | PASS |
| QA-304-2 | QA-304 | 超周限额时返回明确错误 | PASS | 3.2 | PASS |
| QA-304-3 | QA-304 | 积分不足时返回明确错误 | PASS | 0.8 | PASS |
| QA-304-4 | QA-304 | 任务失败后积分回滚且配额释放 | PASS | 5.6 | PASS |

## 关键说明

- `QA-301` 已覆盖静态图池的风格 + 情绪/触发标签命中。
- `QA-302` 为本地弱网/失败模拟回归，覆盖 URL 失败回退与空池失败不阻塞主链路。
- `QA-303` 验证结果页静态图与邮件发送解析到同一素材来源。
- `QA-304` 复核第三阶段硬约束，避免 M5 收口时回退。

## 指标与配置快照

- `api_base_url`: `https://emotion-culture-api-237560-9-1415063583.sh.run.tcloudbase.com`
- `cloud_env`: `prod-9gok8bmyd517976f`

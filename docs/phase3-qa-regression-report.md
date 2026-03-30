# 第三阶段回归报告（草案）

> 状态：进行中（Draft）
>
> 本文档先记录 M2 本地回归结果；真机与部署后回归在后续迭代补齐。

## M2 本地回归（代码级）

执行时间：2026-03-30  
执行方式：本地 Python 脚本调用 `media_generate_service`。

### 场景 1：拒绝授权

- 输入：`consent_confirmed=false`，`MEDIA_GEN_REQUIRE_CONSENT=1`
- 结果：返回 `MEDIA_GEN_CONSENT_REQUIRED`
- 结论：通过

### 场景 2：超周限额

- 输入：同用户在同周内第 2 次创建任务，`MEDIA_GEN_WEEKLY_LIMIT=1`
- 结果：返回 `MEDIA_GEN_WEEKLY_LIMIT_EXCEEDED`
- 结论：通过

### 场景 3：积分不足

- 输入：`MEDIA_GEN_POINTS_COST=999`，默认余额不足
- 结果：返回 `MEDIA_GEN_POINTS_INSUFFICIENT`
- 结论：通过

### 场景 4：失败回滚

- 输入：先扣分后强制触发 provider 失败（非法 provider）
- 结果：任务失败，积分恢复到失败前（`points_restored=True`），且可再次创建任务
- 结论：通过

## 未完成项

- 部署环境日志核对（审计日志关键字）
- 真机链路回归（5G/弱网）
- 小程序 M3 交互回归（授权弹窗/风格按钮/状态机）
- M4 UI 验收回归
- M5 全量回归与封板报告


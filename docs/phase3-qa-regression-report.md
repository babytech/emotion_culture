# 第三阶段回归报告（M2 已封板，后续持续更新）

> 状态：M2 完成
>
> 本文档先记录 M2 本地与线上回归结果；M3-M5 回归在后续迭代继续补齐。

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

## M2 线上回归（云托管环境）

执行时间：2026-03-31  
执行方式：直接调用云托管正式访问域名 `https://emotion-culture-api-237560-9-1415063583.sh.run.tcloudbase.com`

### 场景 1：拒绝授权

- 请求：`consent_confirmed=false`
- 返回：`403 MEDIA_GEN_CONSENT_REQUIRED`
- 结论：通过

### 场景 2：超周限额

- 请求：同一用户在同一自然周内连续创建两次任务
- 返回：第 1 次 `200`，第 2 次 `429 MEDIA_GEN_WEEKLY_LIMIT_EXCEEDED`
- 结论：通过

### 场景 3：积分不足

- 前置配置：`MEDIA_GEN_POINTS_COST=999`
- 返回：`402 MEDIA_GEN_POINTS_INSUFFICIENT: need=999, current=12`
- 结论：通过

### 场景 4：失败回滚

- 前置配置：`MEDIA_GEN_PROVIDER=invalid_provider`、`MEDIA_GEN_POINTS_COST=12`
- 第 1 步返回：创建任务 `200`，随后任务终态 `failed`
- 失败原因：`MEDIA_GEN_PROVIDER_DISABLED`
- 回滚验证：恢复 `MEDIA_GEN_PROVIDER=local_mock`、`MEDIA_GEN_POINTS_COST=1` 后，使用同一 `x-openid` 再次创建任务返回 `200`
- 结论：通过

## M2 封板结论

- M2 四类硬约束场景均已通过
- 当前可判定：
- `BE-304` 完成
- `BE-305` 完成
- `BE-306` 完成
- `BE-307` 完成
- `DATA-303` 完成
- M2 可封板，第三阶段进入 `M3`

## 未完成项

- 真机链路回归（5G/弱网）
- 小程序 M3 交互回归（静态风格切换/风格按钮/状态机）
- M4 UI 验收回归
- M5 全量回归与封板报告

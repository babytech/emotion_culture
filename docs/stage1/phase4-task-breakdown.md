# 第四阶段任务分解（M1-M4 对齐版）

## 使用方式

本文件基于以下文档拆解：

- [product-consensus.md](/Users/babytech/github/emotion_culture/docs/product-consensus.md)
- [phase4-development-plan.md](/Users/babytech/github/emotion_culture/docs/stage1/phase4-development-plan.md)

任务按 `MINI`（小程序前端）与 `QA`（回归）编号。  
第四阶段不新增后端 schema，不引入新的核心依赖接口，因此本阶段以小程序壳层重构与真机收口为主。

## 里程碑 M1：壳层与一级导航稳定

### MINI-401 custom-tab-bar 与全局壳层

- 目标：稳定 5 个主入口与统一壳层视觉语言。
- 依赖：无。
- 目标文件：
- [apps/wechat-mini/custom-tab-bar/index.js](/Users/babytech/github/emotion_culture/apps/wechat-mini/custom-tab-bar/index.js)
- [apps/wechat-mini/custom-tab-bar/index.wxml](/Users/babytech/github/emotion_culture/apps/wechat-mini/custom-tab-bar/index.wxml)
- [apps/wechat-mini/custom-tab-bar/index.wxss](/Users/babytech/github/emotion_culture/apps/wechat-mini/custom-tab-bar/index.wxss)
- [apps/wechat-mini/app.json](/Users/babytech/github/emotion_culture/apps/wechat-mini/app.json)
- 完成定义：
- 5 个 tab 稳定切换
- 安全区、底部遮挡、选中态一致

### MINI-402 首页仪表盘化重做

- 目标：完成首页 Hero、摘要卡、本周洞察、最近结果、收藏预览的产品化重构。
- 依赖：`MINI-401`。
- 目标文件：
- [apps/wechat-mini/pages/home/index.js](/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/home/index.js)
- [apps/wechat-mini/pages/home/index.wxml](/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/home/index.wxml)
- [apps/wechat-mini/pages/home/index.wxss](/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/home/index.wxss)
- 完成定义：
- 首页信息层级清晰
- 弱网、空态、接口失败时有明确降级

### MINI-403 分析工作台重做

- 目标：完成分析页工作台化重构，统一文字、自拍、录音三模块。
- 依赖：`MINI-401`。
- 目标文件：
- [apps/wechat-mini/pages/analyze/index.js](/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/analyze/index.js)
- [apps/wechat-mini/pages/analyze/index.wxml](/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/analyze/index.wxml)
- [apps/wechat-mini/pages/analyze/index.wxss](/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/analyze/index.wxss)
- 完成定义：
- 固定工作台与内容卡不重叠
- 文字 / 自拍 / 录音的操作主次清晰

## 里程碑 M2：主链路页面重构完成

### MINI-404 结果页摘要区与动作区重做

- 目标：完成结果页摘要区、图片区、动作区重构。
- 依赖：`MINI-403`。
- 目标文件：
- [apps/wechat-mini/pages/result/result.js](/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/result/result.js)
- [apps/wechat-mini/pages/result/result.wxml](/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/result/result.wxml)
- [apps/wechat-mini/pages/result/result.wxss](/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/result/result.wxss)
- 完成定义：
- 结果页更像主结果页而非功能集合页
- 邮件、分享、再次分析、换风格层级清晰

### MINI-405 记录页中枢重做

- 目标：完成记录页的总览 Hero、主卡与入口分发重构。
- 依赖：`MINI-402`。
- 目标文件：
- [apps/wechat-mini/pages/journey/index.js](/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/journey/index.js)
- [apps/wechat-mini/pages/journey/index.wxml](/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/journey/index.wxml)
- [apps/wechat-mini/pages/journey/index.wxss](/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/journey/index.wxss)
- 完成定义：
- 记录页具备中枢化角色
- 日历 / 周报 / 历史入口分发清晰

### MINI-406 收藏页统一视觉改造

- 目标：去除收藏页重复说明与重复信息，统一收藏浏览体验。
- 依赖：`MINI-401`。
- 目标文件：
- [apps/wechat-mini/pages/favorites/index.js](/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/favorites/index.js)
- [apps/wechat-mini/pages/favorites/index.wxml](/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/favorites/index.wxml)
- [apps/wechat-mini/pages/favorites/index.wxss](/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/favorites/index.wxss)
- 完成定义：
- 列表信息密度合适
- 空态 / 错误态 / 分页状态清晰

### MINI-407 我的页个人中心化重做

- 目标：完成“我的页”作为个人中心入口的重构。
- 依赖：`MINI-401`。
- 目标文件：
- [apps/wechat-mini/pages/profile/index.js](/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/profile/index.js)
- [apps/wechat-mini/pages/profile/index.wxml](/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/profile/index.wxml)
- [apps/wechat-mini/pages/profile/index.wxss](/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/profile/index.wxss)
- 完成定义：
- 历史保存状态卡、快捷入口、隐私说明、反馈区层级清晰

## 里程碑 M3：真机收尾与状态统一

### MINI-408 分析页真机收尾

- 目标：继续修正分析页 fixed 工作台与底部 tab、内容卡的相对关系。
- 依赖：`MINI-403`。
- 目标文件：
- [apps/wechat-mini/pages/analyze/index.wxml](/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/analyze/index.wxml)
- [apps/wechat-mini/pages/analyze/index.wxss](/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/analyze/index.wxss)
- 完成定义：
- 窄屏、刘海屏、Android 全面屏无遮挡

### MINI-409 结果页键盘 / 邮箱 / 动作区避让收口

- 目标：解决键盘弹起时邮箱输入与底部动作区之间的避让问题。
- 依赖：`MINI-404`。
- 目标文件：
- [apps/wechat-mini/pages/result/result.js](/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/result/result.js)
- [apps/wechat-mini/pages/result/result.wxss](/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/result/result.wxss)
- 完成定义：
- 键盘弹起时无错位、遮挡、误触

### MINI-410 全局空态 / 错误态 / 加载态统一

- 目标：统一首页、记录页、收藏页、我的页在弱网和空数据下的状态表现。
- 依赖：`MINI-402`、`MINI-405`、`MINI-406`、`MINI-407`。
- 目标文件：
- [apps/wechat-mini/pages/home/index.js](/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/home/index.js)
- [apps/wechat-mini/pages/journey/index.js](/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/journey/index.js)
- [apps/wechat-mini/pages/favorites/index.js](/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/favorites/index.js)
- [apps/wechat-mini/pages/profile/index.js](/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/profile/index.js)
- 完成定义：
- 空态、加载态、失败态风格统一

### QA-401 真机视觉回归

- 目标：覆盖 iPhone 窄屏、刘海屏、Android 全面屏的核心页面视觉与交互。
- 依赖：`MINI-401` ~ `MINI-410`。
- 完成定义：
- 关键页面无遮挡、无重叠、无明显错位

## 里程碑 M4：封板与文档收口

### QA-402 弱网 / 空数据 / 接口失败全量回归

- 目标：验证 5 个 tab 页在弱网、空数据、接口失败场景下都有明确降级状态。
- 依赖：`QA-401`。
- 完成定义：
- 页面不白屏、不崩溃、状态可理解

### QA-403 第四阶段验收报告与封板

- 目标：输出第四阶段 QA 回归报告与验收报告，完成封板闭环。
- 依赖：`QA-401`、`QA-402`。
- 目标文件：
- 新增 [docs/stage1/phase4-qa-regression-report.md](/Users/babytech/github/emotion_culture/docs/stage1/phase4-qa-regression-report.md)
- 新增 [docs/stage1/phase4-acceptance-report.md](/Users/babytech/github/emotion_culture/docs/stage1/phase4-acceptance-report.md)
- 完成定义：
- 第四阶段实施清单可勾选
- 回归报告可归档
- 验收口径清晰

## 建议开工顺序

1. `MINI-401` -> `MINI-402` -> `MINI-403`
2. `MINI-404` -> `MINI-405` -> `MINI-406` -> `MINI-407`
3. `MINI-408` -> `MINI-409` -> `MINI-410`
4. `QA-401` -> `QA-402` -> `QA-403`

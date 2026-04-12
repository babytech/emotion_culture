# 第四阶段开发计划（前端壳层重构版）

## 阶段定位

配套文档：

- [phase4-task-breakdown.md](/Users/babytech/github/emotion_culture/docs/stage1/phase4-task-breakdown.md)
- [phase4-implementation-checklist.md](/Users/babytech/github/emotion_culture/docs/stage1/phase4-implementation-checklist.md)
- [phase4-qa-regression-report.md](/Users/babytech/github/emotion_culture/docs/stage1/phase4-qa-regression-report.md)
- [phase4-acceptance-report.md](/Users/babytech/github/emotion_culture/docs/stage1/phase4-acceptance-report.md)

第四阶段定义为“前端壳层重构阶段”。

本阶段的目标不是新增后端业务能力，而是在保持现有分析、留存、收藏、邮件与静态图链路不变的前提下，完成小程序主壳层、首页、分析页、结果页、记录页、收藏页、我的页的产品化重构。

本阶段固定采用以下 5 个底部入口：

- 首页
- 记录
- 分析
- 收藏
- 我的

## 当前范围

第四阶段当前纳入正式交付范围的事项如下：

- `custom-tab-bar` 与全局壳层重构
- 首页仪表盘化重做
- 分析工作台重做
- 结果页摘要区与动作区重做
- 记录页、收藏页、我的页统一视觉与导航体验
- 保持后端接口口径不变

本阶段明确不新增后端 schema，不引入新的核心依赖接口，不重构分析主链路协议。

## 实施顺序

第四阶段按以下顺序推进：

1. `custom-tab-bar` 与全局壳层
2. 首页仪表盘化重做
3. 分析工作台重做
4. 结果页摘要区与动作区重做
5. 记录页、收藏页、我的页统一体验
6. 真机端微调与回归收尾

该顺序的原则如下：

- 先稳定一级导航和壳层，再重做各 tab 页面
- 先处理主入口和主链路，再处理留存页与个人页
- 结果页虽不是 tab，但属于分析主链路核心页面，优先级高于次级留存页
- 所有阶段都以“真机无遮挡、无重叠、状态可理解”为验收底线

## 当前已落地进展

截至当前版本，第四阶段已完成或基本完成的事项如下：

- 已启用 `custom-tab-bar`，形成 `首页 / 记录 / 分析 / 收藏 / 我的` 5 个主入口
- 已形成统一壳层视觉语言，包括：
  - 暖米色基底
  - 统一右上角 badge
  - 统一卡片圆角、阴影、状态胶囊
  - 页面底部安全区与 tab 遮挡处理
- 首页已重做为仪表盘页，完成 Hero、轻量摘要卡、本周洞察、最近结果、收藏预览重构
- 分析页已重做为工作台页，完成：
  - Hero 轻量化
  - 文字 / 自拍 / 录音三模块重组
  - 固定工作台底栏
  - 多轮真机遮挡修正
- 记录页已重做为“记录中枢页”，完成：
  - 顶部总览 Hero
  - 本周回看主卡
  - 日历 / 周报 / 历史入口分发
  - 最近记录轨迹区
- 收藏页已完成统一视觉改造，去除重复说明与重复时间信息
- 我的页已完成个人中心化重构，完成：
  - 历史保存状态卡
  - 快捷入口
  - 隐私说明
  - 反馈与支持区
- 结果页已完成一轮重构，并拆出独立“风格切换”页面，避免主结果页交互拥挤

当前已落地的主要前端文件如下：

- `custom-tab-bar`：[/Users/babytech/github/emotion_culture/apps/wechat-mini/custom-tab-bar/index.wxml](/Users/babytech/github/emotion_culture/apps/wechat-mini/custom-tab-bar/index.wxml)
- 首页：[/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/home/index.wxml](/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/home/index.wxml)
- 记录页：[/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/journey/index.wxml](/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/journey/index.wxml)
- 分析页：[/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/analyze/index.wxml](/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/analyze/index.wxml)
- 收藏页：[/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/favorites/index.wxml](/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/favorites/index.wxml)
- 我的页：[/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/profile/index.wxml](/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/profile/index.wxml)
- 结果页：[/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/result/result.wxml](/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/result/result.wxml)
- 风格页：[/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/style/index.wxml](/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/style/index.wxml)

## 封板说明

第四阶段原定的收尾事项已完成封板复核，当前不再继续保留“阶段内剩余任务”。

本阶段最终收口结论如下：

- 结果页主结构、邮箱面板与底部动作区已经完成分层
- 分析页 fixed 工作台、提交状态与失败恢复链路已经稳定
- 收藏页、我的页、首页、记录页已形成统一的空态 / 错误态 / 加载态表达
- `custom-tab-bar`、安全区、键盘避让、页面壳层语言已完成统一
- 第四阶段已具备实施清单、QA 回归、验收报告三份正式封板产物

封板详情见：

- [phase4-implementation-checklist.md](/Users/babytech/github/emotion_culture/docs/stage1/phase4-implementation-checklist.md)
- [phase4-qa-regression-report.md](/Users/babytech/github/emotion_culture/docs/stage1/phase4-qa-regression-report.md)
- [phase4-acceptance-report.md](/Users/babytech/github/emotion_culture/docs/stage1/phase4-acceptance-report.md)

## 第四阶段暂不纳入事项

除“按住说话转文字”外，以下事项也不纳入当前第四阶段正式交付：

- 新增后端聚合接口
- 变更分析请求 schema
- 新增多轮对话式分析能力
- 新增长语音复杂转写能力
- 新增会员、积分、商业化组件

第四阶段的性质仍然固定为：

- 以前端壳层重构为主
- 以现有后端能力复用为前提
- 以主链路稳定优先于功能扩张为原则

## 分析工作台边界

分析工作台在第四阶段中，固定承接以下现有能力：

- 文字输入
- 前置自拍
- 录音输入
- 开始分析
- 异步分析状态反馈
- 失败可恢复

分析工作台的重构重点是：

- 信息层级更清晰
- 文字密度下降
- 主按钮与状态反馈集中
- 真机下无重叠、无遮挡、无误触

## “按住说话转文字”能力决策

围绕分析工作台中的文字输入卡片，团队评估过增加一个增强输入按钮：

- 按钮名称固定为：`按住说话转文字`

该能力的产品定义固定如下：

- 它属于“文字输入增强方式”
- 它不等于现有“录音分析”
- 它的目标是把短语音转写成文字，并追加到文本框
- 现有录音区域继续保持为“录音分析”能力，不与其合并

第四阶段对该能力的正式决策如下：

- 当前阶段不上线
- 当前阶段不纳入第四阶段正式交付范围
- 待分析主链路稳定性达标后，再重新评估

## 当前暂不纳入的原因

当前不将“按住说话转文字”纳入第四阶段的原因如下：

- 该能力会在“开始分析”前新增一次实时后端请求，增加链路复杂度
- 用户对“松手后快速出字”的反馈预期极高，失败感知会强于普通分析失败
- 真机户外 `5G` 实测下，当前云端超时仍是“点击分析后结果页出不来”的核心问题之一
- 在主分析链路尚未完全稳定前，再叠加 `ASR/STT` 请求，容易放大失败曝光
- 该按钮放在文字卡中后，潜在使用频率会较高，因此稳定性要求高于现有录音分析入口

## 未来重启评估条件

未来如果要重新评估“按住说话转文字”，必须同时满足以下条件：

- “点击开始分析 -> 结果页稳定打开”不再是高频问题
- 小程序主链路已具备稳定的超时恢复与失败重试体验
- `ASR/STT` 网关已完成独立压测和真机网络波动场景验证
- 转写失败不会阻塞用户继续手动输入
- 转写失败不会影响现有录音分析链路
- 前端能提供完整的按住、松开、取消、转写中、转写失败反馈

## 未来实现边界

当条件成熟后，如果启动该能力，默认边界如下：

- 前端录制短语音后调用后端 `ASR/STT` 服务完成转写
- 优先复用现有后端语音转写网关与腾讯云 `ASR` 能力
- 转写结果默认追加到文本框，不覆盖已有内容
- 转写失败时只提示用户改为手动输入或使用现有录音分析
- 初次上线必须采用灰度或白名单方式验证，不能直接全量开放

## 第四阶段当前判断原则

第四阶段对该能力的判断原则固定为：

- 产品上认可价值
- 工程上暂缓实现
- 当前以“稳定性优先于输入便捷性”为执行原则

## 收尾验收标准

第四阶段封板前，至少满足以下验收标准：

- 5 个 tab 页面均可稳定切换
- tab 页面底部无内容被遮挡后仍可见的“漂浮感”
- 分析页固定工作台不与底部 tab 重叠，也不压住内容卡
- 首页、记录页、收藏页、我的页不存在明显重复信息与冗余说明
- 结果页主操作在真机上易发现、易点击、无键盘错位
- 所有 tab 页在弱网、空数据、接口失败时都有明确降级状态
- 当前重构不改变既有后端口径，不引入新的主链路不稳定因素

## 封板后衔接

第四阶段封板后，不再继续扩张为“身份体系增强”或“增长能力阶段”。

以下事项统一转入第五阶段处理：

- 首次进入授权门与微信身份收口
- 主分析链路 5G / 弱网稳定性专项优化
- 自拍摄像头权限前置校验
- 录音中提交流程治理
- 再次分析默认清空旧输入
- 朋友圈分享链路
- “历史上的今天”内容模块
- UI 视觉二次升级

对应文档见：[phase5-development-plan.md](/Users/babytech/github/emotion_culture/docs/stage1/phase5-development-plan.md)

## 文档对齐

本文件与以下文档保持一致：

- [product-consensus.md](/Users/babytech/github/emotion_culture/docs/product-consensus.md)

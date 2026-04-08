# 小程序后续改进计划（基于当前代码与 Phase 状态）

## 文档目的

本文件用于基于 `emotion_culture` 当前仓库代码、已完成 phase 文档与现有小程序实现，判断当前真实遗留问题，并设计后续一段时间的小程序改进计划。

本文件不替代已有 `phase1 ~ phase4` 文档，主要承担两个作用：

- 对“哪些能力已经完成”给出当前判断
- 对“接下来优先补什么、为什么补、按什么顺序补”形成执行建议

## 当前阶段判断

### 已完成阶段

- 第一阶段能力补齐已完成，文字 / 语音 / 自拍分析、邮件、历史、设置等基础闭环已经落地，见 [phase1-implementation-checklist.md](/Users/babytech/github/emotion_culture/docs/phase1-implementation-checklist.md)
- 第二阶段留存底座已完成，日历、周报、收藏、基础分享卡片已经落地，见 [phase2-implementation-checklist.md](/Users/babytech/github/emotion_culture/docs/phase2-implementation-checklist.md)
- 第三阶段 `M2-M5` 已于 `2026-04-01` 验收封板，风控、静态风格图、UI 重构首轮、全量回归均已完成，见 [phase3-acceptance-report.md](/Users/babytech/github/emotion_culture/docs/phase3-acceptance-report.md)

### 当前所在阶段

- 第四阶段“前端壳层重构阶段”已于 `2026-04-09` 正式封板，见 [phase4-acceptance-report.md](/Users/babytech/github/emotion_culture/docs/phase4-acceptance-report.md)
- `custom-tab-bar`、首页、记录页、分析页、收藏页、我的页、结果页的重构与状态统一已形成正式闭环
- 当前项目已进入“Phase5 启动前准备 / 按新阶段需求推进”的状态

## 当前遗留问题

### P0：必须优先处理的问题

#### 1. 前端壳层已重做，但旧页面体系仍与新壳层并存

当前 `app.json` 同时保留了新的 5 个 tab 页面和旧的 `calendar/report/history/settings/index` 页面，见 [app.json](/Users/babytech/github/emotion_culture/apps/wechat-mini/app.json)。

同时：

- 记录页仍把用户分发到旧的日历 / 周报 / 历史页面，见 [journey/index.js](/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/journey/index.js)
- 我的页仍通过快捷入口跳到旧的历史页和设置页，见 [profile/index.js](/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/profile/index.js)

这说明当前信息架构还没有彻底统一，问题包括：

- 新壳层与旧功能页并存，用户路径割裂
- 视觉语言和状态反馈存在二次维护成本
- 后续继续做体验优化时，容易出现“tab 页面改好了，二级旧页面没跟上”的分裂

#### 2. 分析异步任务具备恢复能力，但恢复动作仍偏手动

分析页已经实现了异步任务缓存与轮询机制，`pendingTaskId` 会写入本地缓存，见 [analyze/index.js](/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/analyze/index.js)。

但当前实现里：

- `onLoad` 只恢复任务状态
- `onShow` 只设置 tab 选中态
- 用户通常仍需要再次点击“开始分析”来继续查询结果

这意味着“弱网 / 切后台 / 页面回退后继续恢复结果”的体验还不够自动，仍然存在一次额外心智负担。

#### 3. 首页与记录页都在前端侧重复拼装留存数据

首页在 `onShow` 中并发请求日历、周报、历史、收藏 4 个接口，见 [home/index.js](/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/home/index.js)。

记录页在 `onShow` 中又重复请求日历、周报、历史 3 个接口，见 [journey/index.js](/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/journey/index.js)。

当前问题不是“接口不能用”，而是：

- 页面切换会重复拉同一批聚合数据
- 聚合逻辑散落在多个页面文件中
- 前端自己做容错与拼装，后续维护成本会继续升高

这已经开始偏离第二阶段里“端侧只做渲染和交互，聚合计算统一由后端输出”的原则。

#### 4. 留存、积分、配额、媒体生命周期仍以本地 JSON 存储为主

当前服务端仍大量使用 `/tmp/emotion_culture/*.json` 存储业务状态：

- 历史 / 周报缓存 / 收藏 / 设置：见 [history_service.py](/Users/babytech/github/emotion_culture/services/wechat-api/app/services/history_service.py)
- 周配额：见 [quota_service.py](/Users/babytech/github/emotion_culture/services/wechat-api/app/services/quota_service.py)
- 积分账本：见 [points_service.py](/Users/babytech/github/emotion_culture/services/wechat-api/app/services/points_service.py)
- 媒体保留清理索引：见 [media_retention_service.py](/Users/babytech/github/emotion_culture/services/wechat-api/app/services/media_retention_service.py)

这一实现对单机验证很方便，但对正式云托管会带来明显风险：

- 多实例下数据不一致
- 实例重启后缓存或状态丢失
- 周配额、积分扣减、收藏写入缺少更稳妥的持久化底座
- 后续想做更强的留存分析或运营功能时，扩展性不足

这个问题已经不再只是“技术债”，而是会影响后续产品功能可信度的基础问题。

### P1：第四阶段封板前需要收口的问题

#### 5. 结果页仍承担过多次级操作，主次层级还不够稳定

第四阶段计划中已经明确写到“结果页要避免像功能集合页”，见 [phase4-development-plan.md](/Users/babytech/github/emotion_culture/docs/phase4-development-plan.md)。

从当前结果页状态可以看到它同时承载了：

- 结果摘要展示
- 诗词 / 国潮收藏
- 邮件发送
- 分享卡片
- 风格切换
- 打卡状态回看
- 自拍图预览

见 [result/result.js](/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/result/result.js)。

当前说明问题不在“功能缺失”，而在“结果页信息密度和动作密度仍偏高”，尤其是邮箱输入、键盘避让、固定动作区之间仍有较多手工状态处理。

#### 6. 我的页与设置页存在职责重叠

当前“我的页”已经具备：

- 历史保存开关
- 清空历史
- 隐私说明
- 反馈入口

见 [profile/index.js](/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/profile/index.js)。

但仓库中仍保留一套独立设置页，并继续维护相似能力，见 [settings/index.js](/Users/babytech/github/emotion_culture/apps/wechat-mini/pages/settings/index.js)。

这会导致：

- 配置能力入口重复
- UI 改动需要双处维护
- 用户对“我的”和“设置”的边界感知不清晰

#### 7. 第四阶段缺少标准化封板产物

前三个阶段都有较完整的：

- 开发计划
- 实施清单
- QA 回归报告
- 验收报告

但第四阶段目前只有开发计划文档，尚未形成同等严格的封板闭环，见 [phase4-development-plan.md](/Users/babytech/github/emotion_culture/docs/phase4-development-plan.md)。

这会影响两个动作：

- 团队很难判断“第四阶段到底什么时候算结束”
- 第五阶段若直接启动，容易把未收口的问题继续带入下一阶段

### P2：可以排在收口之后的增强项

#### 8. 留存内容已具备底座，但还没有形成更强的“回看收益”

现在已经有日历、周报、收藏、分享卡片，但仍偏“基础可回看”，还没有把用户最需要的几个价值做得足够强：

- 最近一次分析之后，下一步该做什么
- 近 7 天 / 30 天是否有明显情绪变化
- 哪些触发因素反复出现
- 哪些收藏内容更值得再次回看

这部分已经有数据基础，但还没有形成真正的“持续回来就有收益”的产品体验。

#### 9. “按住说话转文字”仍应维持 deferred 状态

该能力在 [product-consensus.md](/Users/babytech/github/emotion_culture/docs/product-consensus.md) 和 [phase4-development-plan.md](/Users/babytech/github/emotion_culture/docs/phase4-development-plan.md) 中都已经被明确标记为“当前不纳入正式交付”。

结合当前代码状态，这个判断仍然成立：

- 主分析链路虽然已经比前期稳定，但第四阶段本身还没封板
- 异步任务恢复、结果页收口、数据持久化这些更底层的问题优先级更高

因此它应该继续保留在条件性候选项，而不是近期主计划。

## 后续改进原则

- 先封板，再扩张：第四阶段已完成封板，后续新增需求统一按 Phase5 推进
- 先统一壳层，再精修页面：优先解决新旧页面并存与信息架构分裂
- 先稳数据底座，再做更强留存：历史、收藏、积分、配额必须先具备云端可持续性
- 端侧尽量少拼装，聚合逻辑尽量后移：减少重复请求和多页散装逻辑
- 新能力继续遵守“稳定性优先于便捷性”的原则

## 建议迭代计划

### 迭代 A：第四阶段封板收口（已完成）

目标：完成壳层重构的正式封板，让小程序从“重构中”进入“可稳定运营”。

#### 建议范围

- 统一信息架构，明确旧页面去留：
  - 保留二级能力页，但统一视觉和导航语义
  - 或将 `calendar/report/history/settings` 进一步吸收到新壳层逻辑中
- 结果页减负：
  - 把邮件、分享、风格切换、收藏动作重新分层
  - 结果页只保留最核心动作，其余动作进入次级承接
- 分析页恢复体验收口：
  - 进入分析页时自动检测并恢复 `pendingTask`
  - 明确展示“继续查询结果”状态，而不是只靠用户再次点击
- 统一全局空态 / 错误态 / 加载态文案和组件表现
- 产出第四阶段专属：
  - 实施清单
  - 真机回归报告
  - 验收报告

#### 迭代 A 验收结果

- 5 个 tab 与其二级页的信息架构边界已明确
- 结果页已完成主结果页化收口
- 第四阶段已形成实施清单、QA 回归与验收报告
- 当前新增需求统一转入 Phase5 承接

### 迭代 B：数据底座与接口收口（建议 1.5~2 周）

目标：把当前“能跑”的留存与风控状态，升级为“可长期稳定运营”的服务底座。

#### 建议范围

- 将以下状态从本地 JSON 存储迁移到正式云端数据层：
  - 历史摘要
  - 日历打卡
  - 周报缓存
  - 收藏
  - 风格图周配额
  - 积分账本
  - 媒体生命周期索引
- 为首页 / 记录页补一个统一聚合接口，例如：
  - `dashboard summary`
  - `journey overview`
- 增加关键可观测指标：
  - 异步任务创建成功率
  - 轮询完成率
  - 结果页打开成功率
  - 收藏写入成功率
  - 邮件发送成功率
- 明确多实例下的一致性策略：
  - 幂等
  - 扣分与回滚原子性
  - 周限额校验一致性

#### 迭代 B 验收标准

- 小程序核心留存与风控状态不再依赖单实例 `/tmp` 文件
- 首页 / 记录页请求数下降，前端聚合逻辑减少
- 数据层能够支撑后续继续做留存增强而不需要再返工底座

### 迭代 C：留存收益强化（建议 1~1.5 周）

目标：不扩张大主题，只把“用户回来之后真的有收益”做强。

#### 建议范围

- 首页强化“继续回来”的理由：
  - 最近一次结果后的建议动作
  - 本周变化一句话摘要
  - 收藏内容回看入口
- 记录页强化回看效率：
  - 历史分页
  - 按主情绪 / 输入方式做轻筛选
  - 高频触发因素的更明确展示
- 收藏页强化复用价值：
  - 收藏分组
  - 最近收藏 / 最常回看
  - 收藏内容再次分享
- 分享链路收口：
  - 页面分享、图片分享、邮件导出在内容结构上更一致

#### 迭代 C 验收标准

- 用户从首页或记录页能快速获得“最近状态 + 本周变化 + 下一步建议”
- 留存页不只是“查看历史”，而是“帮助复盘”
- 分享与收藏不再是孤立动作，而成为回看链路的一部分

## 暂缓项

以下事项建议继续暂缓，不进入最近两轮主计划：

- 按住说话转文字
- 长语音深度转写与复杂对话分析
- 新会员 / 商业化体系
- 新增重账号体系
- AI 奖励内容扩张

## 推荐执行顺序

1. 先完成迭代 A，正式封掉第四阶段
2. 第五阶段正式承接身份收口、稳定性增强、分享与内容增强、视觉升级，见 [phase5-development-plan.md](/Users/babytech/github/emotion_culture/docs/phase5-development-plan.md)
3. 原迭代 B 的“数据底座与接口收口”作为第五阶段底层专项推进
4. 原迭代 C 的“留存收益强化”作为第五阶段中后段能力推进

## 当前建议结论

当前项目不缺“大方向”，也不缺“功能点”，真正的关键是把现有能力从“已做出来”推进到“已收口、可持续、可运营”。

因此后续小程序改进的主轴不应再是继续加新主题，而应是：

- 完成第四阶段封板
- 解决留存与风控状态的正式持久化问题
- 在已有数据基础上做更强的回看与复盘价值
- 将身份授权、主链路稳定性、朋友圈分享和视觉升级纳入第五阶段正式规划

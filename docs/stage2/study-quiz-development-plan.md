# Stage2 伴学小测开发计划（首页主入口 + 英语单科试点）

## 1. 阶段目标

Stage2 目标从“仅预研”升级为“正式上线首版伴学小测（英语单科）”。

首版必须达成：

- 首页提供伴学小测主入口（并保留直接情绪分析入口）
- 小测完成后可直接进入情绪分析
- 历史记录统一时间线可查询两类记录：情绪分析、伴学小测
- 小测记录绑定微信身份（`unionid` 优先，`openid` 兜底）

## 2. 用户流程

核心主线：

`首页 -> 伴学小测 -> 小测结果 -> 去做情绪分析 -> 情绪结果`

并行主线：

`首页 -> 直接情绪分析`

关键设计：

- 小测不是强制门槛，用户可跳过直达分析页
- 小测结果页提供“去做情绪分析”主按钮
- 从小测结果进入分析页时，携带 `source=study_quiz` 与 `quiz_record_id` 上下文
- 情绪结果页只提供“学习节奏联动建议”，不做“情绪导致成绩”的因果结论

## 3. examUI 逻辑映射（仅复用逻辑，不复用 UI）

复用能力：

- 题型：单选（`radio`）、多选（`check`）、填空（`fill`）
- 判分：按题计分，填空支持按空部分得分
- 错题：输出错题清单并累计到错题本
- 等级：按总分映射等级（A+/A/B/C/D）

不迁移能力：

- 桌面端 UI（Tkinter 页面、窗口流程）
- 本地文件导入导出 UI（Excel/JSON 工具栏）
- 桌面端用户注册/登录流程

## 4. 题库标准（QuestionBank v1）

首版题库为 `services/wechat-api/app/core/study_quiz_english_seed.json`，结构如下：

- 元信息：`course`、`title`、`version`
- 题目集合：`questions[]`

每题字段：

- `question_id`: 题目唯一标识
- `type`: `radio | check | fill`
- `stem`: 题干
- `options[]`: 选项（单选/多选）
- `fills[]`: 填空位（填空题）
- `answer`: 标准答案（仅服务端使用，不下发到前端）
- `audio`、`tags`、`difficulty`: 扩展字段

补充：卷子导入链路（图片 / PDF / 表格）

- 新增导入入口：`POST /api/study-quiz/bank/ingest`（管理态）
- 新增导出入口：`GET /api/study-quiz/bank/export`（Excel 兼容 `.xls`）
- 支持源文件：`jpg/png/pdf/json/csv`（`xls/xlsx` 建议先转 UTF-8 CSV）
- 图片/PDF 通过 OCR HTTP 适配器识别后，统一映射为 QuestionBank v1
- 导入成功后立即写入运行题库覆盖存储（不改 seed 文件）
- 同步返回 `excel_rows`，可直接用于生成 Excel 表格

## 5. API 契约（Stage2）

后端命名空间：`/api/study-quiz/*`

- `GET /api/study-quiz/paper?course=english`
  - 返回试卷，不返回标准答案
- `POST /api/study-quiz/submit`
  - 入参：`course`、`paper_id`、`answers[]`
  - 出参：`quiz_record`、`results[]`、`wrong_items[]`、`next_action_hint`、`points_reward`
- `POST /api/study-quiz/bank/ingest`
  - 管理态题库导入（支持 OCR 识别图片/PDF）
  - 支持 `x-admin-token` 管控
- `GET /api/study-quiz/history`
  - 返回当前微信身份的小测历史摘要
- `GET /api/study-quiz/history/{quiz_record_id}`
  - 返回单条小测结果详情
- `GET /api/study-quiz/wrongbook`
  - 返回错题本摘要

统一历史时间线接口：

- `GET /api/history/timeline?type=all|emotion|quiz`
  - 返回混排时间线，支持筛选“全部/情绪分析/伴学小测”

## 6. 历史融合方案

历史页采用统一时间线：

- 情绪分析条目：保留原详情跳转
- 伴学小测条目：跳转小测结果详情页

筛选维度：

- 全部
- 情绪分析
- 伴学小测

数据存储：

- 在同一用户桶新增 `quiz_records` 与 `wrongbook`
- 与情绪历史共享同一身份策略与留存周期

## 7. 隐私与边界

- 不新增手机号、地理位置等高敏采集
- 小测仅存必要学习结果摘要，不存无关原始数据
- 历史写入遵循现有“保存历史记录”开关
- 对外文案严格避免“情绪与成绩因果化”表达

## 8. 上线节奏

- M2-R1：题库标准化 + 英语试点题库固化
- M2-R2：判分 API 与小测历史/错题本落地 + 分数积分发放
- M2-R3：首页入口 + 小测页 + 结果页 + 历史时间线筛选
- M2-R4：题库导入链路（json/csv + OCR 识别）落地
- M2-R5：真机回归、文档封板、体验版验证

## 9. 验收标准

- 首页可进入伴学小测，也可直接去情绪分析
- 小测提交后可稳定看到成绩、等级、错题摘要
- 小测提交后可按成绩获得积分奖励
- 小测结果页可一键进入情绪分析
- 题库可由图片/PDF/表格导入并转为标准结构
- 历史页可筛选查看情绪分析与伴学小测两类记录
- 不同微信身份数据严格隔离
- Phase5 已有主链路（授权、分析、分享、历史）无回退

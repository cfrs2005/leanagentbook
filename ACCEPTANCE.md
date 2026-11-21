# 教材首版核对记录

本记录按[原始 24 章任务书](ai-agent-engineering-book-kit/02-chapter-specs.md)和[质量门禁](ai-agent-engineering-book-kit/06-review-checklist.md)核对，日期为 **2026-11-20**。区分“必须讲解的主题”“必须运行的实践”与“生产扩展”，不把三者混为同一项验收。

## 核对范围

- 24 章均有正文、可编辑图、练习、验收标准与来源；导读另计。
- 模型实验使用真实本地权重；脚本模型、合成数据、假设价格和有限规则均明确标注。
- 工程实践按原规格验收。第 23 章要求架构设计，不要求部署企业平台；第 24 章允许模拟数据与本机原型。
- 视觉图由本地 SVG 渲染检查，Mermaid 由固定解析器实际解析；未使用浏览器做 UI 验收。网页布局由读者验看。
- 原始规划包保持不变；原始面试、个人身份、公司内部材料和凭据不公开。

## 逐章证据

表中的“已核对”表示教学首版满足原章指定范围，不表示实验结果具备生产有效性。

| 章 | 原任务中的关键实践与验收 | 可复查证据 | 首版判定与边界 |
|---|---|---|---|
| 01 模型基础 | API 请求、Token、Schema、温度对比 | [实验与全部输出](labs/model_foundations/README.md)、[真实复核](labs/model_foundations/verification.md) | 已核对；36 次自由生成和 18 次有限枚举约束；本地 HTTP，不冒充云服务或通用 Schema 引擎 |
| 02 Agent | 两个工具、闭环、错误回填、日志、终止 | [可运行循环与测试](labs/agent_loop/README.md) | 已核对；确定性脚本模型，不评价真实推理能力 |
| 03 Runtime/Harness | 模块职责、接口、Mini-Harness、预算、事件 | [章节与接口](chapters/03-runtime-harness.md)、[实现](labs/agent_loop/README.md) | 已核对；字符预算与内存状态，框架策略讲解不等于部署 |
| 04 编排 | Supervisor、双 Worker、失败、重试、审批、成本对照 | [实验](labs/workflow_orchestration/README.md)、[冲突结果](labs/workflow_orchestration/results/conflict.json) | 已核对；13 项测试；矛盾结果保留并阻止发布，不是开放语义仲裁 |
| 05 Transformer | 张量形状、注意力、遮罩与缓存 | [真实 PyTorch 实验](labs/transformer_internals/README.md) | 已核对；随机简化模型，实际计算而非预写答案 |
| 06 训练 | 小模型微调、数据拆分、训练曲线、资源与评测 | [LoRA/SFT 实验](labs/training_post_training/README.md) | 已核对；真实训练与重载，合成小任务，不是生产能力证明 |
| 07 服务 | 模型服务、输入/输出/并发压测、指标边界 | [真实 HTTP 服务](labs/inference_serving/README.md) | 已核对；8 组 96 请求、CPU 单槽，不承诺 GPU 框架性能 |
| 08 路由 | 小/大模型选择、缓存与回退 | [实时路由轨迹](labs/model_routing/LIVE_RUN.md)、[回放](labs/model_routing/README.md) | 已核对；真实新问题经 Router 生成，错误缓存与失败原文保留 |
| 09 检索 | 关键词、向量、融合、重排及标注集比较 | [真实检索实验](labs/vector_retrieval/README.md) | 已核对；固定英文合成语料与模型，不推断中文效果 |
| 10 RAG | 多格式摄取、引用、更新、删除、评测 | [文件问答实验](labs/rag_pipeline/README.md) | 已核对；真实 PDF/HTML/Markdown，摘录式回答，OCR 等为选型讲解 |
| 11 多模态 | 图片证据检索、融合、阈值和原图位置 | [CLIP 实验](labs/multimodal_rag/README.md) | 已核对；原创合成图与真实模型；VLM/OCR 的讲解不当作实跑 |
| 12 数据 | 采集、质量、流式模拟、持久进度、存储与回放 | [流水线实验](labs/data_engineering/README.md) | 已核对；真实 Parquet 与进程崩溃，不要求部署全部流式框架 |
| 13 记忆 | 抽取、存储、召回、冲突、预算、删除、审计和指标 | [生命周期实验](labs/memory_context/README.md) | 已核对；白名单规则和字节预算，不声称自然语言抽取能力 |
| 14 评测 | 50+ 金标、回放、报告、门禁、指标和失败分类 | [60 条金标与门禁](labs/evaluation/README.md) | 已核对；原创合成标注集与脚本执行器，真实裁判和在线 A/B 为设计 |
| 15 观测 | 任务 Trace、Dashboard、失败轨迹、安全回放、脱敏 | [观测与回放](labs/observability/README.md) | 已核对；本地只读回放，不执行业务副作用 |
| 16 恢复 | 队列、Worker、持久状态；重复、崩溃、超时、取消、副作用 | [恢复实验](labs/durable_execution/README.md) | 已核对；真实子进程退出，不把本地幂等当跨服务 exactly-once |
| 17 安全 | 网关鉴权/授权/审批/审计；危险能力受 OS 隔离 | [工具网关](labs/security_gateway/README.md)、[隔离证据](labs/security_gateway/evidence/isolation-macos-20261120/README.md) | 已核对；受控合成工具在 macOS 默认拒绝策略下运行；Linux 无后端时拒绝执行，OS 检查明确跳过 |
| 18 分布式 | 多 Worker、分发、故障转移、聚合、堆积与恢复 | [HTTP Worker 实验](labs/distributed_agents/README.md) | 已核对；独立进程与真实故障，不声称跨机高可用 |
| 19 时序 | 统计阈值、Isolation Forest、XGBoost；时间切分及指标 | [三模型实跑](labs/time_series/README.md) | 已核对；包含误报、漏报、提前量及未见故障失败 |
| 20 ROS | 真正 Bag 解析、Topic 统计、序列与事件片段 | [Bag 与校验](labs/robotics_ros/README.md) | 已核对；440 条 SQLite/CDR 消息，82 条可独立读事件 Bag；合成代理信号，无 DDS 实机验证 |
| 21 边云 | x86 后目标移植；SoC/运行时/算子/内存/时延/功耗/回滚 | [x86 证据](labs/edge_cloud/evidence/x86-20261120/README.md)、[M4 移植](labs/edge_cloud/evidence/m4-after-x86/README.md)、[功耗](labs/edge_cloud/evidence/power-m4-20261120/README.md) | 已核对；真实 M4 CPU 与系统报告功耗，无 NPU 或外接功率计结论 |
| 22 因果 | 电机因果图、证据采集、验证建议、支持/反对证据和不确定性 | [因果推断实验](labs/causal_diagnosis/README.md) | 已核对；真实数值计算、合成概率表，不伪称真实故障概率 |
| 23 平台 | 逻辑架构、部署拓扑、身份/数据流、权限、故障域、SLO、成本与责任 | [完整架构设计](chapters/23-platform-architecture.md) | 已核对；原规格是设计交付，不宣称已经部署 |
| 24 综合 | 端到端原型；架构、数据流、时序、代码、测试、评测、部署和风险 | [综合实验](labs/robot_platform/README.md)、[报告](labs/robot_platform/VALIDATION.md)、[设备日志](labs/robot_platform/results/device-log-report.json) | 已核对；实际 HTTP/事务/恢复/审批与本地模型；Bag/训练/视觉是前序独立实验，不要求全部塞进同一在线请求 |

## 本轮修订关闭的明确缺项

| 问题 | 修订与证据 |
|---|---|
| 01 只有固定 JSON 样例 | 增加真实 HTTP、tokenizer、温度和自由/受限对象生成；原始失败保留 |
| 04 只有名字隔离，没有冲突处理 | 固定规则矛盾转 needs_review，六种执行/批准组合不能发布 |
| 08 真实采样未接 Router | 新后端由 Router 实际调用；缓存、权限、预算、回退有轨迹 |
| 17 独立沙箱探针未接网关 | 批准后启动受限工具，验证越界读写/网络拒绝、超时和输出限额 |
| 21 功耗缺记录 | M4 80 点真实系统计数器读数，保留背景负载及精度限制 |
| 24 设备日志说明不足 | 新 JSONL 解析与事件关联，校正已知偏移，保留窗口边界歧义与窗外记录 |

## 共用质量门禁

- 23 组默认实验共 **299 项测试**在本机 Python 3.12.14 通过；macOS 隔离测试实际执行。Linux CI 的 OS 路径会明确跳过，不能算作 Linux 隔离通过。
- 第 01 章的两项可选检查重新生成模型输出；第 08 章由整合线程独立重跑真实新问题；第 20 章实际解码检查通过。
- 72 个 Mermaid 块通过固定 Mermaid 11.4.1 解析，包含合法/非法对照；[检查器与报告](scripts/mermaid-check/README.md)说明了语法检查与视觉检查的区别。
- Python 检查器验证所有本地链接与 SVG；MkDocs 严格构建及静态导航/搜索检查随发布执行。GitHub Actions 自动运行实验和 Mermaid 检查。
- [149 个章节外部引用](references/link-check-20261120.json)已逐项访问，均返回 HTTP 200；一处不稳定的论文 PDF 链接改为作者机构的论文页。访问成功不替代事实核验，各章仍说明资料支持哪项结论及核验日期。
- 发布结果、对应提交与在线入口见 [GitHub Releases](https://github.com/cfrs2005/leanagentbook/releases)。已交付课程内容的所有权与第三方依赖许可见首页说明。

## 后续工作怎样算新版本

真实业务数据、中文检索效果、长期运行、跨机高可用、其他芯片和现场机器人试验属于后续增强。开展时要建立新数据契约、独立评测和新的证据记录；不覆盖当前教学结果，不把首版的合成指标当作现场承诺。

## 首版整合批准

独立线程按原规格完成范围审计，修订后复核 01/08/17/21/24 的声明与实际记录，未发现未关闭的 Blocker 或 Major。整合线程复跑相关模型检查、默认实验、图表解析与网站构建，核对源文件摘要后批准 v1.0.0 教学首版发布。该批准仅覆盖本页教学范围；线上发布还须通过对应提交的 GitHub Actions，并检查实际网页内容。

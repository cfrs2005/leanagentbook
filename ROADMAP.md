# 课程路线图

[在线阅读](https://cfrs2005.github.io/leanagentbook/) · [逐项核对与证据](ACCEPTANCE.md) · [原始 24 章任务书](ai-agent-engineering-book-kit/02-chapter-specs.md)

## 当前交付

全部 24 章的教学首版已形成，包含可编辑图、对比表、实践、验收标准和来源。原规格审计发现的 API、真实路由、冲突、隔离工具、功耗和设备日志缺项已补齐。导读不计入 24 章。

“教学首版已核对”指原任务书要求的内容与实践有可检查证据；不表示生产系统验收，也不保证合成数据上的模型能解决真实业务。各章保留适用范围与未验证事项。网页视觉体验由读者验看。

| 章 | 主题 | 当前状态 |
|---|---|---|
| 01 | [人工智能与大语言模型基础](chapters/01-model-foundations.md) | 教学首版已核对 |
| 02 | [Agent 的工作原理](chapters/02-agent-loop.md) | 教学首版已核对 |
| 03 | [Agent Runtime 与 Harness](chapters/03-runtime-harness.md) | 教学首版已核对 |
| 04 | [Workflow、Multi-Agent 与任务编排](chapters/04-workflow-orchestration.md) | 教学首版已核对 |
| 05 | [Transformer 与模型内部原理](chapters/05-transformer-internals.md) | 教学首版已核对 |
| 06 | [模型训练与后训练](chapters/06-training-post-training.md) | 教学首版已核对 |
| 07 | [LLM Inference 与 Serving](chapters/07-inference-serving.md) | 教学首版已核对 |
| 08 | [模型路由与成本优化](chapters/08-model-routing.md) | 教学首版已核对 |
| 09 | [Embedding 与向量检索](chapters/09-vector-retrieval.md) | 教学首版已核对 |
| 10 | [RAG 全链路架构](chapters/10-rag-pipeline.md) | 教学首版已核对 |
| 11 | [多模态 RAG：从相似图片到可核对证据](chapters/11-multimodal-rag.md) | 教学首版已核对 |
| 12 | [AI 数据工程与数据基础设施](chapters/12-data-engineering.md) | 教学首版已核对 |
| 13 | [Agent Memory 与 Context Engineering](chapters/13-memory-context.md) | 教学首版已核对 |
| 14 | [Agent Evaluation 与质量体系](chapters/14-evaluation.md) | 教学首版已核对 |
| 15 | [Agent Observability 与 LLMOps](chapters/15-observability.md) | 教学首版已核对 |
| 16 | [Durable Execution 与分布式任务恢复](chapters/16-durable-execution.md) | 教学首版已核对 |
| 17 | [Agent Security 与权限治理](chapters/17-security-governance.md) | 教学首版已核对 |
| 18 | [分布式 Agent 系统](chapters/18-distributed-agents.md) | 教学首版已核对 |
| 19 | [Time Series AI 与工业异常检测](chapters/19-time-series.md) | 教学首版已核对 |
| 20 | [Robotics AI 与 ROS 数据体系](chapters/20-robotics-ros.md) | 教学首版已核对 |
| 21 | [Edge AI 与边云协同](chapters/21-edge-cloud.md) | 教学首版已核对 |
| 22 | [Causal AI 与智能故障诊断](chapters/22-causal-diagnosis.md) | 教学首版已核对 |
| 23 | [企业级 AI Agent 平台架构](chapters/23-platform-architecture.md) | 教学首版已核对 |
| 24 | [机器人智能诊断平台综合实战](chapters/24-robot-diagnosis.md) | 教学首版已核对 |

## 后续增强方向

这些是首版之后的新工作，不倒推为原始任务书中的隐含要求。

| 方向 | 要回答的问题 | 新证据要求 |
|---|---|---|
| 中文与真实业务数据 | 英文合成实验的结论能否迁移？ | 授权语料、去标识、独立标注集与失败分析 |
| 长期运行与真实流量 | 短实验中的恢复、缓存和延迟是否稳定？ | 明确负载、运行时长、错误率与容量边界 |
| 更多目标平台 | RK3588、Jetson、NPU 是否支持所需算子？ | 固定 SDK/驱动、实机算子、内存、功耗与回滚 |
| 更深的综合实战 | Bag、训练、视觉和在线诊断怎样完整联调？ | 新契约、端到端样本、版本关联与复核记录 |
| 教学改进 | 哪些图难懂、步骤难复现？ | 读者反馈、可复现问题与修订前后对照 |

## 持续构建机制

每次 push/PR 自动执行本地链接、SVG、实验和 Mermaid 语法检查；主分支通过网站构建后更新 GitHub Pages。发布版本保存源码和更新记录。CI 检查内容，不会无人值守地生成新章节。

后续修改遵循：具体问题 → 官方资料 → 图表 → 可运行实验 → 成功/失败验证 → 技术复核 → 版本发布。入口见 [参与编写](CONTRIBUTING.md) 与 [发布记录](CHANGELOG.md)。

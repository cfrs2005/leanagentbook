# 课程路线图

[返回首页](README.md) · [原始 24 章任务书](ai-agent-engineering-book-kit/02-chapter-specs.md)

## 状态定义

| 状态 | 含义 |
|---|---|
| 已规划 | 有目标和验收要求，尚无完整正文 |
| 首版切片 | 有可阅读内容和可运行的局部实验；只覆盖部分任务 |
| 设计稿 | 已交付图表、契约与推演用例；尚无平台部署证据 |
| 待审阅 | 本章任务全部交付，等待技术与教学审阅 |
| 已验收 | 质量门禁通过，读者可按步骤复现；实机要求需单独验证 |

目前没有章节声明为“全章已验收”。导读是学习入口，不计入 24 章。

## 24 章进度

| 章 | 主题 | 当前状态 |
|---|---|---|
| 01 | [人工智能与大语言模型基础](chapters/01-model-foundations.md) | 首版切片；完整任务待补齐 |
| 02 | [Agent 的工作原理](chapters/02-agent-loop.md) | 首版切片；完整任务待补齐 |
| 03 | [Agent Runtime 与 Harness](chapters/03-runtime-harness.md) | 首版切片；完整任务待补齐 |
| 04 | [Workflow、Multi-Agent 与任务编排](chapters/04-workflow-orchestration.md) | 首版切片；完整任务待补齐 |
| 05 | Transformer 与模型内部原理 | 已规划，未交付正文 |
| 06 | 模型训练与后训练 | 已规划，未交付正文 |
| 07 | LLM Inference 与 Serving | 已规划，未交付正文 |
| 08 | [模型路由与成本优化](chapters/08-model-routing.md) | 首版：双模型实测、策略回放与精确缓存；业务盲测与在线负载待补 |
| 09 | [Embedding 与向量检索](chapters/09-vector-retrieval.md) | 首版：双路召回、融合与重排评测；生产 ANN 与中文语料待补 |
| 10 | [RAG 全链路架构](chapters/10-rag-pipeline.md) | 首版：三种格式摄取、引用、更新与删除；真实生成和 OCR 待补 |
| 11 | [多模态 RAG](chapters/11-multimodal-rag.md) | 首版：真实 CLIP 与合成图片检索；OCR、VLM 和真实文档待补 |
| 12 | [AI 数据工程与数据基础设施](chapters/12-data-engineering.md) | 首版：本地消费、崩溃恢复与真实 Parquet；流服务部署待补 |
| 13 | [Agent Memory 与 Context Engineering](chapters/13-memory-context.md) | 首版：规则抽取、生命周期与字节预算；真实语义抽取和 token 计量待补 |
| 14 | [Agent Evaluation 与质量体系](chapters/14-evaluation.md) | 首版：合成标注集、离线回放与门禁；真实模型评测待补 |
| 15 | [Agent Observability 与 LLMOps](chapters/15-observability.md) | 首版：脱敏轨迹、指标与只读回放；真实平台接入待补 |
| 16 | [Durable Execution 与分布式任务恢复](chapters/16-durable-execution.md) | 首版：真实子进程崩溃与本地账本；跨机与长时运行待补 |
| 17 | [Agent Security 与权限治理](chapters/17-security-governance.md) | 首版：固定工具授权审批与 OS 拒绝探针；生产身份与完整沙箱待补 |
| 18 | [分布式 Agent 系统](chapters/18-distributed-agents.md) | 首版：独立进程 HTTP Worker、租约和故障转移；跨机高可用待补 |
| 19 | Time Series AI 与工业异常检测 | 已规划，未交付正文 |
| 20 | Robotics AI 与 ROS 数据体系 | 已规划，未交付正文 |
| 21 | Edge AI 与边云协同 | 已规划，未交付正文 |
| 22 | Causal AI 与智能故障诊断 | 已规划，未交付正文 |
| 23 | [企业级 AI Agent 平台架构](chapters/23-platform-architecture.md) | 设计稿：逻辑、部署、权限与故障推演；未部署 |
| 24 | [机器人智能诊断平台综合实战](chapters/24-robot-diagnosis.md) | 首版切片；完整任务待补齐 |

## 下一批优先顺序

| 批次 | 要补齐的问题 | 交付标准 |
|---|---|---|
| A | 01–04 的真实模型实验、token 计量与框架对比 | 固定模型版本；可选真实 API 实验；无密钥也能跑离线测试 |
| B | 已有 14–17 首版，继续补真实服务接入与长时恢复 | 50 条以上有标注样本；失败分类；崩溃和副作用测试 |
| C | 09–11 检索与多模态 | 固定数据集、召回与排序指标、原图证据校验 |
| D | 19–22 设备数据和现场诊断 | Bag 数据来源可追踪；时间切分；目标设备实测报告 |
| E | 05–08、12–13、18、23、24 综合 | 模型、数据与平台能力整合；完整验收包 |

批次是编写顺序，不是承诺的日期。每次交付都要更新本表与发布记录。持续集成负责检查内容，不会无人值守地生成新课。

## 首批验收范围

- 导读与课程导航可以从 GitHub 直接阅读。
- 02/03 的脚本模型和 24 的合成数据实验可离线复现。
- 图表有可编辑源码；本地链接与 SVG 结构通过自动检查。
- 完整模型评测、真实 ROS Bag、硬件性能与现场诊断均不在本轮完成声明内。

## 工程章节交付范围

14–16 章提供可运行的离线机制实验。评测使用自造标注样本与脚本执行器；观测只读回放不执行业务工具；恢复实验用真实子进程退出验证本地持久化与幂等边界。这些证据不证明真实模型质量、跨机高可用或生产性能。

23 章完成教学设计与桌面推演材料。部署图中的服务、身份提供方和业务租户尚未实际部署。详细测试结果见 [验证记录](VALIDATION.md)。


## 检索与记忆交付范围

09 章已真实运行固定版本的 MiniLM 嵌入和 TinyBERT 重排；英文合成数据结果不能推断中文效果。10 章已处理真实 PDF、HTML 和 Markdown，回答仍为摘录式。13 章是规则抽取和字节预算；17 章是内存固定工具网关与有限 OS 拒绝探针。当前共 17 章有首版或设计稿，仍未声明任何章节完成全套生产验收。

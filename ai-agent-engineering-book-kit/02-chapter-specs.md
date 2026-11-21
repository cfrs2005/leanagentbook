# 02｜逐章撰写任务书
每章都必须回答：解决什么问题、原理是什么、如何实现、如何验证、何时不适用。以下为章节级写作任务，可直接拆成独立 Agent 工单。

## 第 01 章｜人工智能与大语言模型基础

**本章目标：** 建立 LLM 心智模型，理解模型调用的输入、计算与输出边界。

**必须覆盖：**
- AI/ML/DL/LLM 层级关系；生成式模型与判别式模型
- Tokenization：BPE/SentencePiece，Token 数与成本
- Embedding 与向量空间的直观解释；注意不要混同检索 Embedding 与模型内部 Token Embedding
- Transformer 的整体结构和 Attention 直觉
- 上下文窗口、System/User/Assistant 消息结构
- Temperature、Top-p、Top-k、Max Tokens 的作用与限制
- 结构化输出、工具调用与幻觉边界

**工程实践：** ['Python 调用模型 API；Token 统计；JSON Schema 输出；比较温度参数。']

**验收标准：** ['能画出一次 LLM 请求的生命周期；能解释 Token、Context Window、Embedding、Attention；能区分模型生成与外部事实查询。']

## 第 02 章｜Agent 的工作原理

**本章目标：** 从零实现最小 Agent，理解模型决策与工具执行的闭环。

**必须覆盖：**
- Chatbot/Workflow/Agent 的区别；ReAct、Plan-and-Execute、Reflection
- Agent Loop：模型请求、解析 Tool Call、执行工具、Observation 回填、终止
- 工具注册、JSON Schema、参数验证、权限检查
- 状态机、最大步数、超时、重试、错误分类
- 循环检测、重复调用、任务完成判定

**工程实践：** ['Python 实现 Agent Loop；至少 2 个工具；最大步数、超时、错误回填和日志。']

**验收标准：** ['代码可运行；能解释每轮模型输入输出；能展示循环保护和工具失败路径。']

## 第 03 章｜Agent Runtime 与 Harness

**本章目标：** 明确运行时与工程护栏的职责边界，能设计最小可扩展 Runtime。

**必须覆盖：**
- Runtime 管理执行生命周期、状态、事件和资源；Harness 提供上下文、工具、策略和运行约束
- Model Adapter、Tool Executor、Context Manager、State Manager、Event Dispatcher
- 运行时策略：预算、超时、并发、取消、重试、熔断
- 框架提供的能力与自研层的边界；避免重复造轮子

**工程实践：** ['实现 Mini-Harness：模型适配器、工具注册、Context Budget、执行事件和超时。']

**验收标准：** ['提供模块图、接口定义、可运行代码；解释哪些能力由框架提供、哪些属于业务 Harness。']

## 第 04 章｜Workflow、Multi-Agent 与任务编排

**本章目标：** 判断何时用确定性 Workflow、何时用自主 Agent、何时需要多个 Agent。

**必须覆盖：**
- DAG/State Machine/Graph；条件边、并行、循环、人工节点
- Supervisor、Router、Hierarchical、Peer-to-Peer、Agent-as-a-Tool
- 任务拆解、上下文传递、共享状态、结果合并和冲突处理
- MCP 是工具/上下文协议，A2A 面向 Agent 间协作；说明版本和规范边界

**工程实践：** ['构建 Supervisor + 2 Workers；实现并行执行、超时、重试、人工审批。']

**验收标准：** ['给出单 Agent、Workflow、Multi-Agent 的选型决策表；用实验展示协作成本。']

## 第 05 章｜Transformer 与模型内部原理

**本章目标：** 建立模型内部计算的基本理解，能读懂关键张量和注意力流程。

**必须覆盖：**
- Tokenizer、Token ID、Embedding；位置编码
- Q/K/V 的来源；Scaled Dot-Product Attention；Mask；Multi-Head
- FFN、Residual、LayerNorm；Encoder/Decoder 架构差异
- Prefill 与 Decode；KV Cache；上下文长度对显存和计算的影响

**工程实践：** ['PyTorch 实现简化 Self-Attention；打印张量形状；可视化 Attention。']

**验收标准：** ['代码可运行；每个张量维度有解释；明确简化实现与真实模型差异。']

## 第 06 章｜模型训练与后训练

**本章目标：** 能判断是否需要微调，并选择 SFT、LoRA、偏好优化或蒸馏路线。

**必须覆盖：**
- 训练/验证/测试集、Loss、梯度下降、反向传播、过拟合
- Pre-training 与 Next Token Prediction
- SFT 指令数据、数据格式、训练/验证划分
- LoRA 低秩适配、QLoRA 量化训练、Adapter
- RLHF、Reward Model、PPO、DPO、GRPO 的目标和区别；不把它们混为同一算法
- Teacher/Student 蒸馏；Logits、Response、数据蒸馏
- RAG、Prompt、微调各自适用边界

**工程实践：** ['使用 Transformers + PEFT 或 TRL 完成小模型 LoRA/SFT 实验；构造独立评测集。']

**验收标准：** ['有数据集卡片、训练配置、显存记录、训练曲线、基线与微调后对比；结论不只展示个例。']

## 第 07 章｜LLM Inference 与 Serving

**本章目标：** 理解推理服务性能指标和常见优化手段。

**必须覆盖：**
- Prefill/Decode；TTFT、TPOT/ITL、吞吐、并发、P95/P99
- KV Cache、PagedAttention、Continuous Batching、Prefix Cache、Speculative Decoding
- FP16/BF16/INT8/INT4；AWQ/GPTQ/GGUF 的定位
- vLLM、SGLang、TensorRT-LLM、llama.cpp 的适用硬件和场景

**工程实践：** ['部署一个模型服务；用压测工具测不同并发、输入长度和输出长度。']

**验收标准：** ['记录硬件、模型、量化、配置、吞吐、TTFT、TPOT、显存；确保对比条件一致。']

## 第 08 章｜模型路由与成本优化

**本章目标：** 建立质量、时延、成本的多目标路由机制。

**必须覆盖：**
- 模型能力分层和任务分类；路由器输入特征
- 规则路由、分类器路由、LLM Router、级联策略
- 精确缓存、语义缓存、Prompt Prefix Cache、KV Cache 的区别
- Context 压缩、Token Budget、并行调用、批处理
- 单请求成本、单成功任务成本、质量-成本曲线

**工程实践：** ['实现 Router：简单任务走小模型，复杂任务走强模型；加入缓存和回退。']

**验收标准：** ['用测试集比较质量、延迟、成本；定义缓存失效和错误回退策略。']

## 第 09 章｜Embedding 与向量检索

**本章目标：** 理解向量检索和关键词检索的差异、融合和重排。

**必须覆盖：**
- Dense 与 Sparse 的生成机制；BM25/TF-IDF/SPLADE
- 向量相似度：Cosine、Dot Product、L2；归一化影响
- 双塔 Encoder；Query/Document Embedding
- ANN 索引的基本权衡；过滤、分片、更新
- Hybrid Search、RRF、Weighted Fusion
- Cross Encoder、Bi-Encoder、ColBERT 与 Reranking

**工程实践：** ['建立 BM25 + Dense 双路召回；RRF 融合；Reranker 重排。']

**验收标准：** ['准备查询-相关文档标注集；报告 Recall@K、MRR、NDCG 和延迟。']

## 第 10 章｜RAG 全链路架构

**本章目标：** 独立构建文档摄取、索引、检索、生成和更新流水线。

**必须覆盖：**
- 文档解析与格式适配；OCR、版面、表格、元数据
- 清洗、去重、Chunking：固定、递归、语义、父子、Overlap
- Embedding、索引、增量更新、删除和版本管理
- Query Rewrite、Multi-query、Metadata Filter、Hybrid Retrieval
- Reranking、Context Assembly、引用和答案生成
- GraphRAG、Agentic RAG、Corrective/Self-RAG 的动机与适用条件

**工程实践：** ['PDF/HTML/Markdown ingestion；父子切片；检索；引用回答；文档更新。']

**验收标准：** ['可追踪每个答案的来源片段；有离线检索评测；能删除和更新文档。']

## 第 11 章｜多模态 RAG

**本章目标：** 理解图片、文字等模态如何表征、召回、融合和校验。

**必须覆盖：**
- CLIP 双塔和共同向量空间；视觉 Encoder 与文本 Encoder
- OCR、Layout、表格/图表理解；VLM 结构化抽取
- Early Fusion 与 Late Fusion；跨模态 Query
- 多模态相似度与置信度校准；Metadata 过滤
- OCR/VLM 幻觉、原图证据校验、阈值选择

**工程实践：** ['构建图搜图、文搜图或图片搜设备故障案例；比较独立召回和融合。']

**验收标准：** ['说明模型、数据、相似度指标、阈值验证集；不能只凭主观演示声称准确。']

## 第 12 章｜AI 数据工程与数据基础设施

**本章目标：** 理解数据从采集到训练/分析/检索的工程链路。

**必须覆盖：**
- 结构化、半结构化、非结构化数据；数据质量和 Schema
- ETL/ELT；批处理与流处理；Kafka/Flink 的职责
- Object Storage、Parquet、Data Lake、Lakehouse、Iceberg、ClickHouse
- 数据血缘、版本、Schema Evolution、Feature Engineering/Store
- 数据抽稀、采样、分区、压缩、冷热分层

**工程实践：** ['从事件日志生成 Parquet 数据集；模拟流式消费和离线聚合。']

**验收标准：** ['给出吞吐、存储量、延迟、数据丢失处理和重放策略。']

## 第 13 章｜Agent Memory 与 Context Engineering

**本章目标：** 让 Agent 能够选择性保留、检索和更新有用上下文。

**必须覆盖：**
- Context 与 Memory 的区别；短期/长期/情景/语义/程序记忆
- Memory Extraction、Consolidation、Retrieval、Update、Decay
- SQL、Redis、Vector Store 的分工
- Context Budget、摘要、Compaction、Sliding Window、检索注入
- 记忆冲突、过期、隐私、租户隔离和可删除性

**工程实践：** ['实现对话记忆抽取、长期存储、召回、冲突处理和上下文预算。']

**验收标准：** ['用问答集测 Recall、Precision、错误记忆率；支持删除和审计。']

## 第 14 章｜Agent Evaluation 与质量体系

**本章目标：** 建立可重复的离线评测和线上质量监控体系。

**必须覆盖：**
- 模型、RAG、Agent、系统四层评测
- Golden Dataset：样本来源、标注规范、版本和覆盖
- 指标：Accuracy、Precision、Recall、F1、Faithfulness、Recall@K、MRR、NDCG
- Trajectory、Tool Selection、参数准确性、Task Success
- LLM-as-a-Judge 的偏差、校准和人工仲裁
- Offline/Online、A/B、Shadow、Regression、Release Gate

**工程实践：** ['创建 50+ 条小型金标集；运行 Agent 回放；生成评测报告和回归门禁。']

**验收标准：** ['给出标注规范、指标定义、置信区间/样本量注意事项、失败案例分类。']

## 第 15 章｜Agent Observability 与 LLMOps

**本章目标：** 让每次 Agent 执行可观测、可定位、可比较。

**必须覆盖：**
- Logs/Metrics/Traces；Trace、Span、Parent/Child Span
- 模型、检索、工具、Workflow、人工审批的 Span 设计
- Token、成本、TTFT、TPOT、Tool Latency、P95/P99
- Trace Replay 的能力边界；外部副作用重放安全
- OpenTelemetry、Langfuse、Phoenix 等工具定位

**工程实践：** ['给 Agent 加 Trace；构建 Dashboard；保存失败轨迹并做安全回放。']

**验收标准：** ['Trace 能串联一次任务；敏感信息脱敏；指标口径明确。']

## 第 16 章｜Durable Execution 与分布式任务恢复

**本章目标：** 设计长任务的可靠执行、恢复、取消和补偿。

**必须覆盖：**
- 普通请求生命周期与 Durable Workflow 的差别
- Checkpoint、Snapshot、Event History、Resume、版本兼容
- Queue、Worker、Lease、Heartbeat、Timeout、Cancellation
- Idempotency Key、Retry、Backoff、Circuit Breaker、DLQ
- Saga、Compensation、Event Sourcing；Temporal 与 LangGraph 持久化差异

**工程实践：** ['实现任务队列 + Worker + 持久化状态；模拟 Worker 崩溃后恢复。']

**验收标准：** ['测试重复投递、崩溃、超时、取消、外部副作用；解释 exactly-once 的边界。']

## 第 17 章｜Agent Security 与权限治理

**本章目标：** 建立独立于模型判断的安全执行控制。

**必须覆盖：**
- Prompt Injection 与 Indirect Injection；数据/指令边界
- RBAC/ABAC、PEP/PDP、最小权限和用户身份透传
- Agent Identity、Service Identity、Token Exchange、Secret Vault
- Sandbox、容器/文件/网络隔离；工具供应链与依赖审计
- 多租户 Memory/Vector/Tool 隔离；审计与可追责

**工程实践：** ['实现 Tool Gateway：鉴权、授权、审批、审计；危险工具在沙箱执行。']

**验收标准：** ['越权测试、注入测试、租户隔离测试、密钥泄露检查全部通过。']

## 第 18 章｜分布式 Agent 系统

**本章目标：** 把单进程 Agent 扩展成多个独立 Worker 的可靠执行系统。

**必须覆盖：**
- Registry、Discovery、Gateway、Dispatcher、Worker
- HTTP/WebSocket/gRPC/MQ；MCP 与 A2A 的不同层次
- 任务路由、租约、心跳、迁移、超时、重复投递
- 一致性、分布式锁、幂等、事件驱动、补偿
- 资源配额、并发限制、Token Budget 和租户公平性

**工程实践：** ['部署多个 Worker；实现任务分发、故障转移和结果聚合。']

**验收标准：** ['压测并验证重复执行、Worker 掉线、任务堆积和恢复。']

## 第 19 章｜Time Series AI 与工业异常检测

**本章目标：** 掌握传感器时序数据预处理、异常检测和模型选择。

**必须覆盖：**
- 采样频率、时间戳、缺失值、噪声、漂移、窗口
- Time/Frequency Domain；FFT、STFT、Wavelet 的用途
- 统计特征：Mean、Variance、RMS、Peak、Kurtosis 等
- Z-score、IQR、Isolation Forest、One-Class SVM、XGBoost
- LSTM/GRU/TCN/Transformer；对比学习与时序表示
- 异常检测、分类、预测、剩余寿命任务的区别

**工程实践：** ['用模拟电流/温度/转速数据比较统计阈值、Isolation Forest、XGBoost。']

**验收标准：** ['时间切分防止数据泄漏；报告 Precision/Recall/F1、误报漏报和提前量。']

## 第 20 章｜Robotics AI 与 ROS 数据体系

**本章目标：** 理解 ROS 通信与 Bag 数据，并建立设备数据分析入口。

**必须覆盖：**
- ROS 1/ROS 2 架构；Node、Topic、Service、Action
- Message、Bag 记录/回放、QoS（ROS 2）、时间戳和频率
- LiDAR、Camera、IMU、Encoder、电机和电池信号
- 多源时间同步、数据抽稀、事件窗口、异常片段抽取
- 设备软件版本、配置、事件和日志的关联

**工程实践：** ['解析公开/模拟 ROS Bag，提取 Topic 统计、时间序列和事件片段。']

**验收标准：** ['能说明数据格式、时间同步误差、缺失数据和版本兼容。']

## 第 21 章｜Edge AI 与边云协同

**本章目标：** 把合适的模型部署到资源受限设备，并建立安全升级机制。

**必须覆盖：**
- Edge/Cloud/Edge Gateway；任务切分和断网策略
- CPU/GPU/NPU；硬件算子支持和运行时
- ONNX Runtime、RKNN、TensorRT、llama.cpp 的定位
- 量化、剪枝、蒸馏；精度/时延/内存/功耗权衡
- 模型注册、签名、灰度、健康检查、回滚和 OTA

**工程实践：** ['先在 x86 模拟环境完成 ONNX 推理，再按真实设备平台移植。']

**验收标准：** ['必须记录目标 SoC、SDK、算子覆盖、内存、时延、功耗和回滚测试。']

## 第 22 章｜Causal AI 与智能故障诊断

**本章目标：** 从相似案例检索升级到基于证据的故障假设与验证。

**必须覆盖：**
- 相关性与因果性；观测、干预和反事实的区别
- Fault Tree、FMEA、Causal Graph、Knowledge Graph
- Bayesian Network 与条件概率
- 假设生成、证据采集、假设验证、置信度校准
- 诊断建议与控制动作的安全边界

**工程实践：** ['构建一个电机异常因果图；Agent 负责证据收集和验证建议。']

**验收标准：** ['区分相关证据与因果证据；输出支持/反对证据和不确定性。']

## 第 23 章｜企业级 AI Agent 平台架构

**本章目标：** 把模型、工具、知识、身份、评测和审计能力平台化。

**必须覆盖：**
- Model Gateway、Agent Runtime、Tool Gateway、MCP Server
- Memory/Knowledge/Evaluation/Observability 服务边界
- SSO/OIDC/OAuth、RBAC/ABAC、用户身份与服务身份
- Tenant/Workspace/Project 隔离
- 模型、Prompt、Skill、工具版本；成本、审批和审计

**工程实践：** ['设计多业务部门共享 Agent Platform 的逻辑架构与部署拓扑。']

**验收标准：** ['明确数据流、身份流、权限点、故障域、SLO、成本和运维责任。']

## 第 24 章｜机器人智能诊断平台综合实战

**本章目标：** 整合数据、模型、Agent、边云、安全和评测能力。

**必须覆盖：**
- 业务目标和角色；设备/边缘/云/App 边界
- 数据接入、Bag/日志处理、事件标准化、特征和训练集
- 异常模型、RAG、多模态、LLM、Agent Runtime
- 断网、缓存、补传、任务恢复、重复执行和降级
- 设备身份、用户身份、工具权限、审计和安全审批
- 离线/线上评测、成本、延迟、准确率和人工介入

**工程实践：** ['交付端到端可运行原型；可用模拟数据，不得伪称真实设备验证。']

**验收标准：** ['提交业务架构、技术架构、数据流、时序图、代码、测试、评测、部署和风险报告。']

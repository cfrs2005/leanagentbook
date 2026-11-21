# 01｜全书目录（24 章）

## Part I：AI 与 Agent 基础架构
目标：理解模型、Agent、Runtime、Harness、Workflow 的关系。

### 第 01 章｜人工智能与大语言模型基础
AI/ML/DL/LLM；Token 与 Tokenizer；Embedding；Transformer 直觉；上下文窗口；Prompt；生成参数；结构化输出；幻觉与模型边界。
**实践：** Python 调用模型、统计 Token、JSON 输出。

### 第 02 章｜Agent 的工作原理
Chatbot / Workflow / Agent；Agent Loop；ReAct；Plan-Execute；Tool Calling；工具 Schema；状态与终止；循环、错误和超时。
**实践：** 从零实现 Agent Loop 和 Tool Registry。

### 第 03 章｜Agent Runtime 与 Harness
Runtime 职责；Harness 职责；Model Adapter、Tool Executor、Context Manager、State Manager、Event Dispatcher；运行时策略；框架与自研边界。
**实践：** 实现最小 Harness，支持多模型、工具注册、超时和状态记录。

### 第 04 章｜Workflow、Multi-Agent 与任务编排
DAG、State Machine、Graph；并行与条件分支；Supervisor、Router、Hierarchical、Peer-to-Peer；任务委派；MCP 与 A2A 边界。
**实践：** Supervisor + Worker，含并发、超时、重试和人工审批。

## Part II：模型工程与推理系统
目标：理解模型训练、微调、推理和部署。

### 第 05 章｜Transformer 与模型内部原理
Tokenizer、BPE；Token/Position Embedding；Q/K/V；Self-Attention、Multi-Head、Causal Mask；FFN、Residual、LayerNorm；Prefill、Decode、KV Cache。
**实践：** PyTorch 实现简化 Self-Attention。

### 第 06 章｜模型训练与后训练
训练/验证/测试集；Loss、梯度下降、反向传播；Pre-training；SFT；LoRA/QLoRA；RLHF、Reward Model、PPO、DPO、GRPO；蒸馏；RAG 与微调的选择。
**实践：** 开源小模型 LoRA 微调、独立测试集对比。

### 第 07 章｜LLM Inference 与 Serving
显存与计算；TTFT、TPOT、Throughput；KV Cache、PagedAttention、Continuous Batching、Prefix Cache、Speculative Decoding；量化；vLLM、SGLang、TensorRT-LLM、llama.cpp。
**实践：** 部署模型、压测并记录 P50/P95/TTFT/TPOT。

### 第 08 章｜模型路由与成本优化
模型分层；任务复杂度识别；路由策略；精确缓存与语义缓存；Prompt/Context 压缩；Token Budget；单任务成本和成功任务成本。
**实践：** 模型路由网关，按质量、成本和延迟选模型。

## Part III：RAG 与 AI 数据工程
目标：理解外部知识获取、检索质量和大规模数据处理。

### 第 09 章｜Embedding 与向量检索
Dense/Sparse；双塔；BM25/TF-IDF/SPLADE；Cosine/Dot Product；Hybrid Search；RRF；向量数据库；Cross Encoder 与 Reranker。
**实践：** Dense + Sparse + BM25 + RRF + Reranker。

### 第 10 章｜RAG 全链路架构
数据接入、解析、清洗、Chunking、Embedding、Indexing、Retrieval、Reranking、Generation；OCR、表格解析；Parent-Child、Semantic Chunking；Query Rewrite；GraphRAG、Agentic RAG。
**实践：** PDF/OCR/父子切片/混合检索/Reranker 完整链路。

### 第 11 章｜多模态 RAG
图像、文本、音频、视频；CLIP/Vision Encoder；跨模态向量空间；OCR 与 Layout；Early/Late Fusion；置信度校准；VLM 幻觉与原图校验。
**实践：** 图片找设备/商品、图文联合检索。

### 第 12 章｜AI 数据工程与数据基础设施
结构化/半结构化/非结构化数据；ETL/ELT；Batch/Stream；Kafka/Flink；Parquet/Iceberg/ClickHouse/Object Storage；数据血缘、版本、Feature Store；数据飞轮。
**实践：** 业务日志和设备事件到训练数据集的 Pipeline。

## Part IV：Agent 工程化与治理
目标：解决上下文、质量、可观测性、可靠性和安全。

### 第 13 章｜Agent Memory 与 Context Engineering
Context Window/Budget；短期、长期、情景、语义、程序记忆；Memory Extraction/Consolidation/Retrieval/Decay；摘要与压缩。
**实践：** Redis + SQL + 向量检索的分层记忆 Demo。

### 第 14 章｜Agent Evaluation 与质量体系
Golden Dataset；模型/RAG/Agent/System 评测；Accuracy、Precision、Recall、F1；Faithfulness、MRR、NDCG、Recall@K；Trajectory；LLM-as-a-Judge；在线/离线、A/B、Shadow、Regression。
**实践：** 自动评测流水线和质量门禁。

### 第 15 章｜Agent Observability 与 LLMOps
Logs/Metrics/Traces；Trace/Span；模型、工具、检索 Span；Replay；P50/P95/P99、TTFT、TPOT、Token；Langfuse、OpenTelemetry、Prometheus、Grafana。
**实践：** Agent Trace、Dashboard、失败轨迹回放。

### 第 16 章｜Durable Execution 与分布式任务恢复
长任务；Checkpoint/Snapshot/Resume；Task Queue、Worker、Lease、Heartbeat；幂等、Retry、Backoff、Circuit Breaker、Compensation、DLQ；Event Sourcing、Saga、Temporal、LangGraph Checkpointer；HITL。
**实践：** Worker 重启后恢复 30 分钟诊断任务。

### 第 17 章｜Agent Security 与权限治理
Prompt/Indirect Injection；Tool Abuse；最小权限；RBAC/ABAC；PEP/PDP；Sandbox；身份透传；Secret 管理；多租户隔离；MCP/Skill 供应链审计。
**实践：** 身份透传、工具授权、沙箱和审计网关。

## Part V：分布式 AI 与机器人智能
目标：将 AI 扩展到分布式执行、时序数据、机器人和边缘设备。

### 第 18 章｜分布式 Agent 系统
Registry/Discovery/Gateway/Dispatcher/Worker；HTTP/WebSocket/gRPC/MQ；A2A；任务租约、心跳、迁移；一致性、锁、幂等；Token/并发/配额治理。
**实践：** 多 Worker Agent 执行系统。

### 第 19 章｜Time Series AI 与工业异常检测
采样率、噪声、缺失值、滑动窗口；FFT/STFT/Wavelet；统计特征；Z-score/IQR/Isolation Forest/One-Class SVM/XGBoost；LSTM/GRU/TCN/Transformer；对比学习。
**实践：** 电机、电池、雷达模拟数据异常检测。

### 第 20 章｜Robotics AI 与 ROS 数据体系
ROS 1/2；Node/Topic/Service/Action；Message/Bag/回放/时间戳/频率；LiDAR/Camera/IMU/Encoder/Motor/Battery；数据同步、抽稀、事件窗口；故障定位与证据。
**实践：** ROS Bag 解析器与结构化诊断事件。

### 第 21 章｜Edge AI 与边云协同
Edge/Cloud；CPU/GPU/NPU；RK3588、ONNX Runtime、RKNN、TensorRT、llama.cpp；量化、剪枝、蒸馏；离线缓存、断点上传、模型 OTA、灰度和回滚。
**实践：** 轻量异常检测模型边缘部署。

### 第 22 章｜Causal AI 与智能故障诊断
相关与因果；Fault Tree、FMEA、Knowledge/Causal Graph；Bayesian Network；假设生成、验证、干预、反事实；证据、置信度和校准。
**实践：** 传感器 + 故障知识库 + Agent 诊断，输出原因、证据和验证建议。

## Part VI：综合架构设计与工程实践
目标：把前述技术整合成可落地平台。

### 第 23 章｜企业级 AI Agent 平台架构
Model/Agent/Tool Gateway；MCP；Memory/Knowledge/Evaluation/Observability；SSO/OAuth/OIDC；RBAC/ABAC；多租户；成本、审批、版本、审计。
**实践：** 多业务部门共用的 Agent Platform 设计。

### 第 24 章｜机器人智能诊断平台综合实战
业务背景；设备数据接入；ROS Bag 与日志处理；时序模型；多模态检索；LLM；Agent Runtime；设备端/边缘端/云端/App；可靠性、安全、评测、成本和验收。
**最终交付：** 业务架构、技术架构、数据流、Workflow、核心代码、模型实验、评测集、性能报告、安全方案、部署运维手册。

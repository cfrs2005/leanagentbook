# 03｜参考材料与 GitHub 资源地图

> 使用说明：GitHub 仓库是研究入口，不是整章内容的替代品。正式写作时必须再核对 README、文档、License、Release、代码路径和当前 API。链接存在不代表项目适合生产。

## A. 开源教材与课程

| 资源 | 重点 | 对应章节 | 地址 |
|---|---|---|---|
| Datawhale Hello-Agents | Agent 原理、经典范式、框架、自建 Agent、Memory/RAG、MCP/A2A、Agent RL、评测 | 1–4、10、13–14 | https://github.com/datawhalechina/hello-agents |
| Datawhale zero-to-sglang | 推理引擎原理、构建 mini-SGLang、源码学习 | 5、7 | https://github.com/datawhalechina/zero-to-sglang |
| Hugging Face Transformers | 模型定义、推理和训练、多模态 | 5–7、11 | https://github.com/huggingface/transformers |
| Hugging Face smol-course | 小模型对齐和训练实践 | 6 | https://github.com/huggingface/smol-course |
| AI Engineering from Scratch（社区学习项目） | AI Engineering、RAG、微调、Agent、Serving；先审查内容和维护状态 | 1–18 | https://github.com/Gtrialacc/ai-engineering-from-scratch |
| Awesome Agentic Engineering Resources | 课程、Cookbook、论文、基准和项目索引 | 全书资料发现 | https://github.com/EthicalML/awesome-agentic-engineering-resources |

## B. Agent / Runtime / Workflow

| 项目 | 研究重点 | 对应章节 | GitHub |
|---|---|---|---|
| LangGraph | Stateful graph、checkpoint、interrupt、multi-agent | 3、4、13、16 | https://github.com/langchain-ai/langgraph |
| OpenAI Agents SDK | Agent、handoff、guardrail、tracing | 2–4、15、17 | https://github.com/openai/openai-agents-python |
| Microsoft Agent Framework | Agent orchestration 与企业工作流；核对项目当前状态 | 3、4、18 | https://github.com/microsoft/agent-framework |
| Temporal | Durable Execution、Workflow、Activity、Retry | 16、18 | https://github.com/temporalio/temporal |
| MCP Python SDK | MCP Server/Client 实现 | 4、17、23 | https://github.com/modelcontextprotocol/python-sdk |
| A2A Protocol | Agent-to-Agent 互操作协议 | 4、18 | https://github.com/a2aproject/A2A |

## C. 模型训练与微调

| 项目 | 研究重点 | 对应章节 | GitHub |
|---|---|---|---|
| Transformers | 模型结构、Tokenizer、模型加载和训练 | 5、6、11 | https://github.com/huggingface/transformers |
| PEFT | LoRA、QLoRA 等参数高效微调 | 6 | https://github.com/huggingface/peft |
| TRL | SFT、DPO、PPO、GRPO 等后训练工具 | 6 | https://github.com/huggingface/trl |
| Axolotl | LLM 微调训练配置与工程化 | 6 | https://github.com/axolotl-ai-cloud/axolotl |
| Unsloth | 高效微调 Notebook 与实践 | 6 | https://github.com/unslothai/unsloth |
| Datasets | 数据集加载、处理与版本 | 6、12、14 | https://github.com/huggingface/datasets |

## D. 推理与 Serving

| 项目 | 研究重点 | 对应章节 | GitHub |
|---|---|---|---|
| vLLM | PagedAttention、Continuous Batching、Serving | 7、8 | https://github.com/vllm-project/vllm |
| SGLang | 高性能推理、RadixAttention、Serving | 7、8 | https://github.com/sgl-project/sglang |
| TensorRT-LLM | NVIDIA GPU 推理优化 | 7 | https://github.com/NVIDIA/TensorRT-LLM |
| llama.cpp | 量化模型与 CPU/边缘推理 | 7、21 | https://github.com/ggml-org/llama.cpp |
| ONNX Runtime | 跨硬件推理运行时 | 7、21 | https://github.com/microsoft/onnxruntime |

## E. RAG / Embedding / 检索

| 项目 | 研究重点 | 对应章节 | GitHub |
|---|---|---|---|
| Sentence Transformers | Embedding、语义检索、Reranker | 9–11 | https://github.com/UKPLab/sentence-transformers |
| BGE | 中文/多语言 Embedding 与 Reranker 模型 | 9–11 | https://github.com/FlagOpen/FlagEmbedding |
| Ragas | RAG 评测指标与流程 | 10、14 | https://github.com/explodinggradients/ragas |
| Qdrant | 向量数据库、过滤和检索 | 9–11 | https://github.com/qdrant/qdrant |
| Milvus | 向量数据库和 ANN 检索 | 9–11 | https://github.com/milvus-io/milvus |
| FAISS | 向量相似度搜索与索引 | 9 | https://github.com/facebookresearch/faiss |
| LlamaIndex | 数据连接、索引和 RAG | 9–11 | https://github.com/run-llama/llama_index |

## F. Evaluation / Observability / Security

| 项目 | 研究重点 | 对应章节 | GitHub |
|---|---|---|---|
| Langfuse | LLM Trace、Prompt、Evaluation、成本 | 14–15 | https://github.com/langfuse/langfuse |
| Arize Phoenix | OpenTelemetry、LLM tracing、evaluation | 14–15 | https://github.com/Arize-ai/phoenix |
| OpenTelemetry | 通用可观测性标准与 SDK | 15 | https://github.com/open-telemetry/opentelemetry-python |
| Promptfoo | LLM/Agent 测试、安全红队和评测 | 14、17 | https://github.com/promptfoo/promptfoo |
| NeMo Guardrails | 对话和 Agent Guardrails | 17 | https://github.com/NVIDIA/NeMo-Guardrails |
| OWASP GenAI Security Project | LLM 应用安全风险与控制建议 | 17 | https://github.com/OWASP/www-project-top-10-for-large-language-model-applications |

## G. 数据工程 / 时序 / 机器人 / 边缘

| 项目 | 研究重点 | 对应章节 | GitHub |
|---|---|---|---|
| Apache Kafka | 事件流和消息系统 | 12、18 | https://github.com/apache/kafka |
| Apache Flink | 流式处理 | 12 | https://github.com/apache/flink |
| Apache Iceberg | Lakehouse 表格式 | 12 | https://github.com/apache/iceberg |
| ClickHouse | 实时分析数据库 | 12、19 | https://github.com/ClickHouse/ClickHouse |
| River | 在线机器学习与流式异常检测 | 19 | https://github.com/online-ml/river |
| PyOD | 异常检测算法库 | 19 | https://github.com/yzhao062/pyod |
| Darts | 时间序列建模与预测 | 19 | https://github.com/unit8co/darts |
| ROS 2 | ROS 2 核心代码 | 20 | https://github.com/ros2/ros2 |
| rosbag2 | ROS 2 Bag 录制、读取和回放 | 20 | https://github.com/ros2/rosbag2 |
| LeRobot | 开源机器人学习数据、模型和工具 | 20–21、24 | https://github.com/huggingface/lerobot |
| RKNN Toolkit2 | Rockchip NPU 模型转换和部署；核对硬件与 SDK 版本 | 21 | https://github.com/airockchip/rknn-toolkit2 |
| OpenVINO | Intel 硬件推理优化 | 21 | https://github.com/openvinotoolkit/openvino |

## H. 重要官方文档入口

- Hugging Face Transformers：https://huggingface.co/docs/transformers
- Hugging Face PEFT：https://huggingface.co/docs/peft
- Hugging Face TRL：https://huggingface.co/docs/trl
- LangGraph：https://langchain-ai.github.io/langgraph/
- Temporal：https://docs.temporal.io/
- vLLM：https://docs.vllm.ai/
- SGLang：https://docs.sglang.ai/
- MCP：https://modelcontextprotocol.io/
- ROS 2：https://docs.ros.org/
- ONNX Runtime：https://onnxruntime.ai/docs/

## I. 使用和许可证提醒

1. 每个仓库单独核查 LICENSE，不要假设所有开源项目都允许任意商用。
2. 教材引用应优先引用官方文档和论文；代码示例要保留来源和许可证要求。
3. 论文、博客和项目 README 的内容不可整段复制。
4. 项目 API 和目录可能变化，写作时固定 commit/tag 并记录核验日期。
5. RKNN、TensorRT 等硬件工具必须按目标芯片、系统和 SDK 版本验证。

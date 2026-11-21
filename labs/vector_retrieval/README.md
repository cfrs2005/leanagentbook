# 第 09 章实验：双路检索、融合与重排

本实验提供可运行的标准库教学层与可选真实预训练模型层。不是向量数据库服务，不包含真实设备控制。课程入口见 [第 09 章](../../chapters/09-vector-retrieval.md)。

## 文件与运行

- [retrieval.py](retrieval.py)：BM25、cosine/dot/L2、归一化、RRF、加权融合、指标；离线规则模式有明确注释。
- [evaluate.py](evaluate.py)：五条完整查询路径与真实计时。排序函数不接收相关性标签。
- [corpus.json](corpus.json)、[judgments.json](judgments.json)、[数据卡](DATA_CARD.md)：32 篇原创合成英文文档，28 个查询；10 个开发、18 个测试。
- [test_retrieval.py](test_retrieval.py)：独立手算断言与失败路径；不用下载模型。
- [requirements.txt](requirements.txt)：模型路径直接依赖；[environment-lock.txt](environment-lock.txt) 是本次临时 Python 3.12 环境完整包版本，不承诺跨系统可直接安装。
- [results-offline.json](results-offline.json)：真实运行的规则演示结果，不能当作预训练语义模型结果。

所有命令从仓库根目录运行，Python 3.11+ 标准库路径：

```sh
python3 -m unittest discover -s labs/vector_retrieval -p 'test_*.py' -v
python3 labs/vector_retrieval/evaluate.py --mode offline --output /tmp/vector-offline.json
```

输出是 dev/test 两组的五种方法汇总；JSON 还包含逐查询完整候选排名、原始时延、数据哈希、环境与参数。指标定义和计时范围见数据卡。

离线模式的 `dense` 实际是 **12 个人工概念维度 + 常数分量**，`rerank` 是 **词集合 Jaccard 重叠**。它们不是学得的语义表示或 Cross Encoder。概念维度故意丢失词序和否定信息，使读者能看见表示不足的后果。没有哈希向量，没有金标查表。

## 预训练模型路径

| 职责 | 发布者模型 | 固定 revision | 模型卡许可 |
| --- | --- | --- | --- |
| Dense | [sentence-transformers/all-MiniLM-L6-v2](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2) | `1110a243fdf4706b3f48f1d95db1a4f5529b4d41` | Apache-2.0 |
| Cross Encoder | [cross-encoder/ms-marco-TinyBERT-L2-v2](https://huggingface.co/cross-encoder/ms-marco-TinyBERT-L2-v2) | `81d1926f67cb8eee2c2be17ca9f793c7c3bd20cc` | Apache-2.0 |

许可与 revision 于 2026-11-20 从发布者模型卡和 API 核验。模型文件只缓存到临时目录，不提交仓库。英语模型与短输入是本实验的范围，不承诺中文或长文性能。Cross Encoder 输入上限在代码中固定为 256 tokens；长文会截断，需另外检查证据是否保留。

```sh
python3.12 -m venv /tmp/leanagentbook-vector-py312
/tmp/leanagentbook-vector-py312/bin/pip install -r labs/vector_retrieval/requirements.txt
HF_HOME=/tmp/leanagentbook-vector-models HF_HUB_DISABLE_XET=1 \
  /tmp/leanagentbook-vector-py312/bin/python labs/vector_retrieval/evaluate.py \
  --mode pretrained --output /tmp/vector-pretrained.json
```

本次先在默认 Python 3.15.2 安装，pip 返回 `No matching distribution found for torch==2.6.0`。随后改用隔离 Python 3.12 环境，直接依赖安装成功；没有修改根 `.venv`。首次运行需要联网下载模型，不适合普通无网络 CI。预训练失败不会自动切成规则模式并仍标作模型结果。

## 离线实测与边界

2026-11-20，默认 Python 3.15.2，macOS arm64；详细系统字段见结果 JSON。参数为 C=10、K=5、RRF c=60、加权 w=0.5；每查询每方法 3 次，串行热运行，测试查询 18 条。

| 规则模式方法 | Recall@5 | MRR@5 | NDCG@5 | p50 ms | p95 ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| BM25 | 0.8333 | 0.9167 | 0.8464 | 0.058 | 0.071 |
| 教学概念向量 | 0.9815 | 0.8472 | 0.8449 | 0.057 | 0.063 |
| RRF | 0.9815 | 0.9167 | 0.9039 | 0.116 | 0.127 |
| 加权融合 | 0.9537 | 0.9444 | 0.9183 | 0.122 | 0.130 |
| RRF + 词集规则重排 | 0.8519 | 0.9583 | 0.8497 | 0.146 | 0.182 |

规则重排提高 MRR，却降低 Recall 与 NDCG，说明“重排一定更好”不成立。样本量小，规则词表与数据来自同一合成领域，指标不可外推。微秒级延迟主要反映 32 篇短文上的标准库运算，不能与生产服务或真实模型速度混为一谈。

## 验收与限制

本实验要验证的不是固定质量阈值，而是：公式有手算证据，排序不读取答案，指标口径可重算，真实时延包含查询计算，失败与结果如实保存。支持通过 `--candidates` 与 `--cutoff` 改候选深度和截断；非法组合直接失败。

ANN、分片、增量更新、中文、无答案拒答、并发压测与权限隔离未实测。外部模型许可来自模型卡，不替下游具体发布方式作法律判断。所有合成操作说明只用于检索实验，不用于真实机器人维修。

## 保留的缺陷样例：离线规则模式

- q02“密码被盗，如何踢出对方”：标注 d02=2（撤销会话），d01=1（重置密码）。规则重排前五为 d01/d13/d16/d24/d28，漏掉主答案 d02，Recall@5=0.5，NDCG@5=0.2754。词面重叠把“password”当成主信号，不能理解“撤销会话”的意图。
- q12“电机太热怎么办”：主答案 d12 在第 5，辅助 d22 在第 4；规则首位却是电池充电温度 d25。Recall@5=1，但 MRR@5=0.25、NDCG@5=0.4382。找到了相关文档，不等于排得好。
- q17“怎样证明备份真能恢复”：规则把事故恢复 d10 排在定期恢复演练 d19 前。两篇都相关，MRR=1，NDCG 仍只有 0.6885；分级指标揭示主次颠倒。

这些排名直接取自保存的逐查询结果，没有修改标签来消除失败。

## 真实预训练模型实测

2026-11-20 已真实下载并加载两个固定 revision 的权重，缓存约 120 MB，结果保存在 [results-pretrained.json](results-pretrained.json)。环境为 Python 3.12.14、macOS 26.3 arm64、torch 2.6.0、transformers 4.48.3、sentence-transformers 3.4.1、numpy 2.5.5，CPU 两线程。首次导入、加载与下载合计 94.90 秒；文档编码及 BM25 初始化 181.48 ms，二者均不计入下表查询时延。

| 预训练模式方法 | Recall@5 | MRR@5 | NDCG@5 | p50 ms | p95 ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| BM25 | 0.8333 | 0.9167 | 0.8464 | 0.062 | 0.086 |
| MiniLM Dense | 0.9722 | 1.0000 | 0.9775 | 3.912 | 5.073 |
| RRF | 0.9815 | 0.9722 | 0.9365 | 3.657 | 4.645 |
| 加权融合 | 1.0000 | 0.9722 | 0.9647 | 3.614 | 4.282 |
| RRF + TinyBERT Cross Encoder | 1.0000 | 0.9444 | 0.9458 | 5.777 | 6.771 |

这里 **Dense 的 NDCG 高于融合和重排**。因此不能用这份测试集得出“Hybrid 总是更好”的结论。RRF 后重排相对 RRF 提升了 NDCG 和 Recall，但降低了 MRR。各路 Recall@10 在测试集均为 1；开发集 BM25 候选 Recall@10 只有 0.75。开发/测试完整结果都保留，未挑选一组隐藏另一组。

RRF 包含更多步骤，测到的 p50 却略小于 Dense 单路，属于短运行中的推理和系统波动；不能声称融合反而减少计算量。每种路径每条查询只测 3 次，无并发、隔离核心或频率控制。报告保留原始样本，允许读者扩大重复数重测。

### 真实模型缺陷样例

| 查询 | 实际排序变化 | 暴露的问题 |
| --- | --- | --- |
| q02 密码被盗，踢出对方 | Dense 前两名 d02/d01；RRF 改为 d01/d02，NDCG 从 1 降到 0.7967 | 词面信号把重置密码压过撤销会话，融合可能稀释强路 |
| q03 已到充电座却无电 | RRF 首位 d03；Cross Encoder 把“路径受阻”的 d30 提到第一，d03 第二，NDCG 从 0.9448 降到 0.6399 | 成对模型仍未正确区分“到不了”与“已到达” |
| q12 电机太热 | Dense 首位 d12；RRF 和重排首位均是电池充电温度 d25；重排 NDCG 0.5869 | 同主题部件混淆；正确候选存在也会排错 |
| q27 退款已受理却超时 | Dense 前三为 d32/d17/d18；RRF 把辅助 d18 挤出前五，Recall 从 1 降到 0.6667 | 融合截断改变候选前部；重排把 d18 放回第五后恢复 Recall |

保留真实失败，不修改金标或在代码中按查询 ID 分支。若需要改进，先对开发集错误分类，再增加独立语料；这个 18 查询测试集不能继续充当无污染的最终评估集。

### 验证证据

- 11 项标准库测试通过：包含相似度手算、零向量/维度/非有限数拒绝、RRF 空列表/重复 ID、融合常数分数、指标手算、语料完整性和全路径候选集合不变性。
- 完整预训练模式正常退出，五条路径共 28 个查询，每条 3 次；未回退到规则模式。初次运行出现 tokenizer fork 后关闭并行的警告，不影响完成；PyTorch 线程仍固定为 2。
- SVG 经 XML 结构检查，并用本机 `@resvg/resvg-js` 2.6.2 渲染为 1200×620 PNG 后检查完整图；未用浏览器。图保持真实文字可编辑，最终视觉验收留给用户。

- 已设置 `HF_HUB_OFFLINE=1`、`TRANSFORMERS_OFFLINE=1`，使用临时缓存重跑预训练路径（每查询 1 次）；全部 140 个查询/方法排名与首次实测一致。此验证依赖先下载的缓存，不改变普通 CI 无模型的要求。
- 最终 `python3 scripts/check_book.py` 通过：当时全仓 59 份 Markdown、193 条本地链接、22 份 SVG；另单独检查本章与实验文档 17 条本地链接。全仓数字会随其他章节增加。

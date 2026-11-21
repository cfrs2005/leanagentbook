# 模型路由实验

[第 08 章](../../chapters/08-model-routing.md) · [真实观测](observations.json) · [冷策略回放](cold-results.json) · [热缓存回放](warm-results.json)

## 两条运行路径

离线回放只需 Python 3.11+ 标准库，无网络、无密钥、无模型下载：

```sh
python3 -m unittest discover -s labs/model_routing -p 'test_*.py' -v
python3 labs/model_routing/router.py --output /tmp/routing-cold.json
python3 labs/model_routing/router.py --warm --output /tmp/routing-warm.json
```

重新采样会下载两份公开模型权重，需要网络、磁盘和内存。已验证环境为 Python 3.12.14、CPU 两线程、torch 2.6.0、transformers 4.48.3。固定依赖不保证支持未来 Python 版本。

```sh
python3.12 -m venv /tmp/book-routing
/tmp/book-routing/bin/pip install -r labs/model_routing/requirements.txt
HF_HOME=/tmp/book-routing-models /tmp/book-routing/bin/python labs/model_routing/collect.py --output /tmp/routing-observations.json
python3 labs/model_routing/router.py --observations /tmp/routing-observations.json --output /tmp/routing-new.json
```

模型权重留在缓存目录，不进入课程仓库。新观测若不对应当前数据文件的 SHA-256，回放会拒绝。

## 数据与模型卡

| 项目 | 内容 |
| --- | --- |
| 数据 | [dataset.json](dataset.json)，课程原创 24 条英文合成题，无私人访谈或用户数据 |
| 划分 | 按编写序号每三条中的第一条为开发集：8 dev、16 test；不是随机代表性样本 |
| 任务 | 算术、逻辑、情感；number、yes_no、sentiment 三种固定输出格式 |
| small | google/flan-t5-small，revision `0fc9ddf78a1e988dac52e2dac162b0ede4fd74ab` |
| base | google/flan-t5-base，revision `7bcac572ce56db69c1ea7c8af255c5d7c9672fc2` |
| 来源 | [模型配置](models.json)，模型卡标注 Apache-2.0；权重未打包 |
| 解码 | greedy、max_new_tokens=32；每个模型预热一次，每题采样一次 |
| 输入计量 | tokenizer 实际 input_ids 长度，含特殊 token；超过 512 拒绝，不静默截断 |
| 输出计量 | 排除 decoder 起始 token，包含实际生成的 EOS |
| 正确性 | 去首尾空白、转小写、去末尾 .!? 后字符串完全匹配；`5.0` 与 `5` 仍不同 |

标注只供离线评分，不发送给模型或路由器。模型可能见过类似题目，不能证明不存在预训练污染。数据小且合成，只支持本次样本结论。

## 已验证结果（2026-11-20）

17 个离线测试全部通过。48 次真实生成记录已保存，两份策略报告都由这些记录生成。small 与 base 测试集均答对 6/16，开发集分别为 3/8 和 4/8。比如 q01 的标准答案是 5，small 输出 0、base 输出 1：格式合格但内容错误。级联不会因离线标注得知这种错误。

规则阈值 8/16/24/32 预先枚举；若按开发正确率优先、再按总积分选择规则，选 24 词。其测试结果仍为 6/16。全部候选都公开，不能只挑好看的结果。该规则不构成业务推荐。

冷回放的 small 测试积分为 0.634，base 为 2.608。价格是人为假设：每千输入 token 的 small/base 为 1/4 积分，输出权重为 2。它不是美元、人民币或实际电费。

热缓存每种策略的测试命中为 13/16，正确数仍为 6。只计算第二次请求的新增调用成本，第一次填充成本不在热报告中。错误但格式合法的答案会缓存；格式失败不缓存。

## 机制边界

| 已做 | 未做 |
| --- | --- |
| 真实模型输出、真实 tokenizer 计量 | 云端账单核对、生产负载 |
| 真实调用耗时记录；加载单列 | 实际在线级联、网络与排队测量 |
| 版本化精确缓存、TTL、深复制隔离 | 语义缓存、跨实例共享缓存 |
| 请求总预算，拒绝不升级 | 身份认证、完整安全策略 |
| 超时/错误的合成记录测试 | 真实服务超时故障注入 |
| 开发/测试分组、所有候选结果 | 大规模盲测、统计置信区间 |

scope 是内部可信身份上下文，不能由外部用户任意填写。token 预算是保守预留：输入加最大输出可能超预算时停止，即便实际输出也许会很短。错误或超时按观测中的已知用量计费，未模拟供应商对未知用量的结算。

回放直接读取记录，不等待原始延迟。`recorded_backend_ms` 是尝试记录的耗时之和，不是回放脚本运行时间，也不是线上端到端延迟。输出的 p50/p95 用最近秩；仅 16 个测试样本，p95 即最大值。模型采样是一次暖运行，不能据此得出稳定性能排序。

## 扩展练习

新增业务数据时，先保存划分与选择规则，再采样。为开发集设质量下限和最大预算，保留所有失败。真实服务实验还应记录排队、网络、路由自身开销、缓存填充和失效成本。替换模型时必须更新 revision、观测与缓存版本。

## 重绘质量成本图

可选绘图依赖独立列在 `requirements-plot.txt`，不影响默认测试。

```sh
/tmp/book-routing/bin/pip install -r labs/model_routing/requirements-plot.txt
/tmp/book-routing/bin/python labs/model_routing/plot_results.py
```

图从冷回放报告读取数据，输出可编辑 SVG。默认使用 macOS 的 Arial Unicode 字体文件；其他系统用 `BOOK_PLOT_FONT` 指定可用中文字体文件。图的生成环境与模型推理环境分开记录，安装绘图包不会重新生成模型观测。

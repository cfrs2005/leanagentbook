# 第 01 章实验：真实模型请求与输出边界

[章节](../../chapters/01-model-foundations.md)提供三条路径。输入为原创合成题，不含私人资料。

| 路径 | 实际做什么 | 边界 |
|---|---|---|
| 标准库固定样例 | 人工预算、JSON 结构和错误反例 | 不调用模型，不统计真实 token |
| 自由生成 | 真实本机 HTTP → FLAN-T5-small → tokenizer 计量与原文校验 | 不保证 JSON 成功，不修复输出 |
| 有限枚举约束 | 真实模型按 logits 选择合法 token 路径，经显式括号编码转换得到对象 | 仅两个对象的 enum，不是通用 Schema 引擎；格式成功不保证语义正确 |

## 标准库检查

```sh
python3 labs/model_foundations/foundations.py
python3 labs/model_foundations/foundations.py --input-units 81
python3 labs/model_foundations/foundations.py --scenario invalid
python3 labs/model_foundations/foundations.py --scenario truncated
python3 labs/model_foundations/foundations.py --scenario wrong-fact
python3 -B -m unittest discover -s labs/model_foundations -p 'test_*.py'
```

22 项默认测试不导入 torch 或 transformers。固定样例的 `wrong-fact` 输出 99℃仍通过结构检查；它不是模型生成。人工预算的单位也不是 token。失败场景返回 1，结构通过返回 0。

## 真实模型运行

已验证环境是现有 `/tmp/leanagentbook-routing-py312`，Python 3.12.14、CPU 两线程。没有修改该共享环境的依赖。其他机器可以新建自己的独立 Python 3.12 环境，安装 [requirements-model.txt](requirements-model.txt)，准备固定 revision 快照后替换命令路径。不要修改仓库根 `.venv`。

模型：`google/flan-t5-small`；revision：`0fc9ddf78a1e988dac52e2dac162b0ede4fd74ab`。权重不进入仓库。推理只从给定目录加载，不隐式下载。报告中保存快照各文件哈希，包括权重、配置和 tokenizer；不会保存本机用户名或路径。

```sh
/tmp/leanagentbook-routing-py312/bin/python labs/model_foundations/collect_model.py --model-path /tmp/leanagentbook-routing-models/hub/models--google--flan-t5-small/snapshots/0fc9ddf78a1e988dac52e2dac162b0ede4fd74ab --out labs/model_foundations/output/free-001
/tmp/leanagentbook-routing-py312/bin/python labs/model_foundations/collect_constrained.py --model-path /tmp/leanagentbook-routing-models/hub/models--google--flan-t5-small/snapshots/0fc9ddf78a1e988dac52e2dac162b0ede4fd74ab --out labs/model_foundations/output/constrained-001
```

每次必须使用不存在的输出目录，不能覆盖 `results/`。两条命令均创建真实的回环 HTTP 服务，客户端使用 `urllib.request` 发请求；服务结束后关闭端口。服务不是云 API，无聊天模板、无生产认证，不向外部网络开放。

## 已发布结果

- [自由生成报告](results/local-model-20261120/report.json)与[全部 36 次原始结果](results/local-model-20261120/responses.jsonl)：两条固定提示 × 三种温度 × 三个种子 × 两次重复。
- [受限生成报告](results/constrained-20261120/report.json)与[全部 18 次原始结果](results/constrained-20261120/responses.jsonl)：42℃与99℃两条提示 × 相同三种温度 × 三个种子，各一次。
- [执行检查记录](verification.md)：标准库检查、模型重新推理和全书结构检查。

自由生成的 36 次 HTTP 均成功，但只有 2 次符合整数 Schema，且输出都是错误答案 `2`，不是 `2+3` 的 5。对象任务 18 次全部失败；2 次整数任务达到长度上限，保留 `length` 结束原因。没有对生成结果进行 JSON 修复。

受限生成 18 次均符合对象 Schema，14 次答案符合输入，4 次错误。每条记录保留原生模型 token、原生文本、JSON 文本、实际分支概率、选中 token 和校验结果。模型通过真实 logits 选择 42 或 99，不由脚本读取真值后返回答案。格式保证来自有限候选范围，不代表模型学会通用 JSON。

## 为什么需要显式括号编码

固定 T5 tokenizer 将 ASCII `{`、`}` 编码为未知 token，不能直接完整表示 JSON 对象。为保持原权重及词表不变，本实验将已有 `<extra_id_0>`、`<extra_id_1>` 分别作为左右括号的可逆编码；其余字符按原 tokenizer 编码。先生成此有限语言中的 token，再做**固定标点转换**得到 JSON。两种对象都在生成前声明：

```json
{"enum":[{"answer":"42","source_ids":["record-1"]},{"answer":"99","source_ids":["record-1"]}]}
```

这不是“模型原生文本直接输出 JSON”。`raw_native_text` 和最终 `text` 同时保留；转换不改变答案，不补来源，不做语义修复。候选前缀过滤由 `prefix_allowed_tokens_fn` 执行；共有结构 token 被强制，答案分叉处允许多个 token，按温度处理后的真实模型分数采样。报告保存候选完整 token 路径，不支持任意字符串、任意对象或任意 Schema。

## 计量与公平比较

自由生成两条提示分别为 18、50 个输入 token，含特殊 token。输出数量排除 decoder 起始 token，包含实际 EOS；保存 ID 可独立复核。输入限制 512、输出限制64分别设置，不能把 T5 当成共享输入输出窗口的 decoder-only 模型。这里没有云账单。

固定 `do_sample=True, top_p=1, top_k=0`；温度 0.2/0.8/1.3，种子7/17/27。相同种子重复用于复现检查，不算独立样本。受限路径的42℃提示与自由对象任务完全相同；公平对照应取自由生成 `repeat=0` 的9次，对照受限42℃的9次。额外99℃的9次用于检验内容变化，不能混入同提示比较。

## 可选的真实模型复核

这些文件不以 `test_` 开头，默认测试不会导入模型依赖：

```sh
/tmp/leanagentbook-routing-py312/bin/python labs/model_foundations/verify_model.py --model-path /tmp/leanagentbook-routing-models/hub/models--google--flan-t5-small/snapshots/0fc9ddf78a1e988dac52e2dac162b0ede4fd74ab --evidence labs/model_foundations/results/local-model-20261120
/tmp/leanagentbook-routing-py312/bin/python labs/model_foundations/verify_constrained.py --model-path /tmp/leanagentbook-routing-models/hub/models--google--flan-t5-small/snapshots/0fc9ddf78a1e988dac52e2dac162b0ede4fd74ab --evidence labs/model_foundations/results/constrained-20261120
```

先检查源码、数据及模型哈希，再重做全部 tokenizer/解码/Schema 检查，两条路径各重新生成两条并核对 token ID。固定样例测试通过不能替代这两项检查。来源、访问日期与支持的结论见章节参考资料；报告记录的访问日期为2026-11-20。

未验证：云服务、通用 Schema 约束引擎、中文任务效果、跨硬件逐 token 复现、生产吞吐和安全控制。小样本与预设候选无法代表真实业务质量。

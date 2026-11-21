# 第15章观测实验

Python 3.11+ 标准库；原创轻量实现。使用合成读数 `(42, 56, 71)` 与固定规则模型，无 API 密钥、网络或平台安装要求。

```sh
python3 labs/observability/observability.py
python3 -m unittest discover -s labs/observability -v
python3 labs/observability/observability.py --replay labs/observability/output/trace-1.json
```

默认输出目录为 `labs/observability/output/`。也可通过 `--output /tmp/observability-run` 指定目录。打开其中的 `dashboard.html` 即可离线阅读；它没有 JavaScript 或远程资源。CLI 正常生成报告时返回 0，报告中的两条失败是预设测试情景，不表示生成命令失败。

| 文件 | 内容 |
|---|---|
| `observability.py` | 追踪、结构校验、脱敏、固定脚本任务、只读回放、聚合与 HTML CLI |
| `test_observability.py` | 18 项行为测试，含 CLI 子进程与并发上下文隔离 |
| `example-run/trace-1.json` | 成功任务；最后一步仅为写入计划 |
| `example-run/trace-2.json` | 只读工具抛出合成超时异常，父链保留错误状态 |
| `example-run/trace-3.json` | 审批拒绝，未进入工具阶段 |
| [实际摘要](example-run/summary.json) | 一次本机运行的指标；不是性能基线 |
| [离线报告](example-run/dashboard.html) | 可直接打开的实际运行报告 |
| [验证记录](VALIDATION.md) | 命令、测试范围、结果与限制 |

模型输出确定，但 UUID 和本机耗时随运行改变。计时采用单进程单调时钟，不可跨主机比较绝对起点。JSON 格式是本实验的 `lab-trace-v1`，不是 OTLP。代码不收集完整提示词、回复、文档、异常消息或调用栈。

回放只读已有记录，既不重跑读工具，也不重跑模型。它只写标准输出，不修改输入文件。篡改字段、跨 trace 父节点、环路和不合法时间关系会被拒绝。格式校验不是数字签名，不能证明记录来自可信服务。

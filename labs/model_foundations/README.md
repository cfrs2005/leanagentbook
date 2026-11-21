# 第 01 章实验：预算与结构校验

这是离线教学实验。只使用 Python 标准库；无模型、tokenizer、真实设备、网络或密钥。全部响应是人工编写的固定样例。预算采用人工整数单位，不能用于真实模型计费或容量判断。

## 运行

在仓库根目录执行，要求 Python 3.11+：

```bash
python3 labs/model_foundations/foundations.py
python3 labs/model_foundations/foundations.py --input-units 79
python3 labs/model_foundations/foundations.py --input-units 81
python3 labs/model_foundations/foundations.py --scenario invalid
python3 labs/model_foundations/foundations.py --scenario truncated
python3 labs/model_foundations/foundations.py --scenario wrong-fact
python3 -m unittest discover -s labs/model_foundations -p 'test_*.py' -v
```

## 预期与实际结果

2026-11-20 已在 Python 3.15.2 运行上述 6 个 CLI 场景，结果如下；已验证实际进程退出码并解析其 JSON 输出。

| 场景 | 状态 | 退出码 | 观察结果 |
|---|---|---|---|
| 默认输入 80、预留 20、容量 100 | structure_valid | 0 | 剩余 0 |
| 输入 79 | structure_valid | 0 | 剩余 1 |
| 输入 81 | rejected | 1 | 超限，fixture_read 为 false |
| invalid | rejected | 1 | answer 数字类型被拒绝 |
| truncated | rejected | 1 | 未闭合 JSON 被拒绝 |
| wrong-fact | structure_valid | 0 | 错误数字 99 仍通过结构检查 |

单元测试实际结果：**17 个测试全部通过**，包含预算等于上限、超限一单位、非法参数、字段缺失与多余、类型错误、空回答、空来源、重复键、非标准数字常量、截断、响应长度限制，以及 CLI 退出行为。多个测试包含多个子案例，17 是测试方法数，不是数据行数。

同日补充执行 `python3.12 -m unittest discover -s labs/model_foundations -p 'test_*.py'`，Python 3.12.14 上同样为 17 个测试全部通过。执行 `python3 scripts/check_book.py` 时通过 33 份 Markdown、62 个本地链接和 14 份 SVG 的结构检查；该计数是共享工作目录当时的快照，不代表其他章节由本实验验收。检查不覆盖外链、渲染或技术准确性。官方技术来源已另行查阅并记录在正文参考表。

## 事实边界

合成来源 `record-1` 的内容约定为“设备温度是 42 摄氏度”。默认样例写 42，wrong-fact 写 99，两者结构相同。所有输出均包含 `fact_check: not_performed`，程序不读取来源库，也不比较数字。不能把退出码 0 解释成回答正确。

固定 `SCHEMA` 用于说明契约。`validate_output` 是手写的特定契约检查，不读取任意 schema，不是通用 JSON Schema 引擎。schema 允许空来源数组，也允许空格字符串；业务若不允许，需增加独立规则及测试。重复键和 4096 码点限制是额外的本地解析策略。

## 未完成范围

真实模型 API、真实 token 统计、服务端约束输出、温度对比、事实核验、输出结束状态处理、流式响应、超时重试和生产权限均未实现。Python 3.11 是代码的最低目标版本，不代表该版本已实测；实测环境在本页单独记录。未用浏览器进行视觉验收。

正文与已核验的官方来源见[第 01 章](../../chapters/01-model-foundations.md)。

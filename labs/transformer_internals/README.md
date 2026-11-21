# 第 05 章实验：因果注意力与 KV 缓存

这是合成 ID、随机未训练权重的真实 PyTorch 实验。无文本 tokenizer、无模型下载、无语言能力评测。

从仓库根目录执行，环境安装见[章节](../../chapters/05-transformer-internals.md)。默认产物写到 `output/transformer_internals/`；发布证据 `results/` 禁止被实验命令覆盖。

```sh
python attention.py --help
```

上面命令应在本目录执行。完整运行命令（仓库根目录）：

```sh
python labs/transformer_internals/attention.py --output /tmp/ch05-new-run
python labs/transformer_internals/torch_checks.py -v
python3 -m unittest discover -s labs/transformer_internals -p 'test_artifacts.py' -v
```

2026-11-20 验证环境：Python 3.12.14、torch 2.6.0、matplotlib 3.10.1、numpy 2.5.5，CPU float64。只读使用临时环境 `/tmp/leanagentbook-routing-py312`；未改变依赖或根环境。安装文件固定直接依赖，不是全平台依赖锁。

验证计数：6 个真实 torch 单测，3 个标准库证据单测，实验内 6 项数值断言。全量/增量最大误差 `2.220446049250313e-16`。测试覆盖单 token、两个 batch、4-token prefill + 2-token decode、非法宽度和空输入。遮罩反例证明检查可发现未来依赖。

原始输出见 [run.txt](results/run.txt)、[tests.txt](results/tests.txt)、[report.json](results/report.json)、[config.json](results/config.json)、[tensors.json](results/tensors.json)、[incremental_output.json](results/incremental_output.json)。[attention.png](results/attention.png) 直接由原始权重生成，没有手调数据。配置保留种子，不保存模型权重；同一软件环境可重新初始化。跨版本、跨硬件不保证逐位一致。

架构 SVG 已用本地 resvg 渲染并查看，热图已直接查看；没有浏览器验收。全书检查只验证本地链接和 SVG 结构，不证明外链持续可用、内容正确或全部章节完成。

默认 `test_*.py` 发现路径仅运行 3 个标准库证据测试，不导入 torch。真实计算需独立执行 `torch_checks.py -v`，另运行 6 个测试；默认路径通过不代表已执行真实 PyTorch 检查。本次两条路径均实际执行，无跳过。

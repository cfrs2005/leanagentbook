# M4 CPU 实测证据

本目录是 2026-11-20（America/Los_Angeles）的原创实验快照。UTC 时间在 summary 中。训练和完整推理命令使用 `-W error`，通过后才复制输出到此目录。原始输出位于本地被忽略的 `labs/edge_cloud/output/m4-20261120-verified/`，新实验应写新的 output 目录，不覆盖本证据。

- `summary.json`：平台、模型 SHA、数据 SHA、训练历史、基线、实际执行算子、结果与未测功耗。
- `data.npz`：原创合成训练、验证、测试数据，无个人或企业数据。
- `source.onnx`、`float.onnx`、`int8.onnx`：原创训练参数与导出图，约 3 KB/份。source 为图预处理前文件，性能表使用 float 与 int8。
- `*-requests.csv`：每模型 2560 条完整原始计时与预测。
- `*-logits.npy`：512 个测试样本的真实模型输出。
- `*-metrics.json`：逐模型指标；profile JSON 来自单独的非计时会话。
- `latency.svg`：由本次 summary 生成的可编辑延迟图。
- `ota-tests.json`：12 项真实 Ed25519 和 ONNX 健康检查结果；私钥未写盘。
- `environment.txt`：本次完整 Python 依赖版本。

人工复核用标准库重新计算 CSV 中位数、插值 P95、测试准确率，并重算模型 SHA，与 summary 一致。SVG 已使用本地 resvg 渲染并查看，未用浏览器。

边界：这不是 x86 测试，不是 RK3588、Jetson、GPU、NPU 验证；不是实际断电测试；功耗没有测量证据。RSS 是独立进程峰值，不是模型独占内存。测量数字不代表真实工业数据上的分类能力。

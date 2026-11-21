# x86 GitHub CI 真实运行证据

来源：[GitHub Actions 44878247748](https://github.com/cfrs2005/leanagentbook/actions/runs/44878247748)，提交 `b79f1b575fae7e70311003ea05c12085221f822f`。原 artifact 名称为 `edge-cloud-x86-evidence`，通过 `gh run download` 原样下载，未修改原始结果。`run.json` 保存 API 返回的作业状态、提交与步骤时间。

工作流 Ubuntu 24.04 runner，实际 `architecture=x86_64`；运行 Python 3.12.16、ORT 1.23.2。`soc` 只返回架构名称，具体 CPU 型号未采集，不能把它解释成芯片型号。完整依赖清单未由该 workflow 保存；summary 记录 NumPy、ONNX、ORT 等直接执行版本。

两模型各 2560 次真实请求，100 次预热，CPU provider；INT8 profile 包含 QLinearMatMul。浮点准确率 93.95%，INT8 93.55%。`ota-tests.json` 记录 12 项真实签名与恢复检查通过。CSV、模型、输出数组、profile 和 summary 均保留，可重新核对 SHA、准确率、中位数和 P95。

CI 于 UTC 2026-11-21 07:01:47 完成，即洛杉矶 2026-11-20 23:01:47。其后 [M4 复跑](../m4-after-x86/README.md)完成完整流程及原文件移植。不能用共享 CI 延迟与 M4 数字作硬件性能排名。功耗未测。

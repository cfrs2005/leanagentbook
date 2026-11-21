# 第21章实验：真实推理与本地安全升级

这是原创合成数据与原创小模型实验，不控制机器人，不连接外部设备。`ota.py` 是单更新进程教学实现，不是完整固件 OTA 或 TUF 客户端。

## 两层验证

默认检查只用 Python 标准库，不会导入 NumPy、ORT 或 cryptography：

```sh
python3 -m unittest labs.edge_cloud.test_edge_cloud -v
```

完整实验需 Python 3.12。请在仓库根目录运行，使用独立环境和新的输出目录：

```sh
python3.12 -m venv /tmp/leanagentbook-edge-env
/tmp/leanagentbook-edge-env/bin/python -m pip install -r labs/edge_cloud/requirements.txt
/tmp/leanagentbook-edge-env/bin/python -W error labs/edge_cloud/benchmark.py --output output/edge-cloud-run1
/tmp/leanagentbook-edge-env/bin/python labs/edge_cloud/verify_ota.py --models output/edge-cloud-run1 --report output/edge-cloud-run1/ota-tests.json
```

输出路径已存在时会停止，避免覆盖证据。要复跑，改成 `run2`。每个模型都用独立子进程测量；请求计时不包含载入、预热、构造输入或写文件，包含 ORT Python 调用和输出返回。CPU 单线程，固定批量 1。另建 profiling session 确认实际执行算子，不把 profiling 开销混入计时。

`summary.json` 包含 SoC、系统、依赖版本、模型 SHA、输入输出、模型字节数、准确率、P50/P95、独立进程 RSS 峰值。RSS 包含 Python、导入库、数据、ORT 会话和推理，不是模型独占内存；不是跨平台精确内存对比。每模型 CSV 保存 2560 条原始请求；`data.npz` 保存分割后数据；`*-logits.npy` 保存测试集输出；profile JSON 保存 provider 证据；`latency.svg` 从本次数据直接生成。

训练集/验证集/测试集分别用种子 2101/2102/2103 生成 2048/512/512 条样本；模型初始化与批次随机顺序使用 2104。标签由固定非线性规则生成。训练 300 轮，不使用测试集选轮数或调参。验证集只记录过程；INT8 校准只读取训练集前 256 行。多数类基线只从训练标签选择类别。这个实验测量合成任务上的准确率，不能证明真实故障识别效果。

依赖入口固定 NumPy 2.2.6、ONNX 1.19.1、ORT 1.23.2、cryptography 46.0.3。模型 ONNX opset 17、IR 10；不要求 PyTorch。完整传递依赖及本机证据以本次环境记录为准。跨系统浮点计算可能造成小差异，不要求重新训练后 SHA 相同；要求记录自己的 SHA。

## x86 与设备移植

[真实 x86 CI](https://github.com/cfrs2005/leanagentbook/actions/runs/44878247748) 已通过，提交 `b79f1b575fae7e70311003ea05c12085221f822f`，工作流为 `.github/workflows/edge-evidence.yml`。产物已下载至 [x86 证据](evidence/x86-20261120/README.md)，确认 `x86_64`、CPU provider、真实整数内核和 12 项 OTA 测试。具体 x86 CPU 型号未采集；不把架构字段当成 SoC 型号。保留 [CI 作业示例](ci-job.yml) 供其他仓库整合。

本次可访问目标是 Apple M4 的 CPU；并未验证 GPU、Apple Neural Engine、RK3588、Jetson 或其他 NPU。原任务的“先 x86 后目标平台”顺序现已完成：CI 完成后，使用原独立环境完成 [M4 新复跑](evidence/m4-after-x86/README.md)，并将未经修改的 x86 模型直接在 M4 运行。完整复跑及同文件移植各自通过 12 项 OTA 检查。旧 `m4-20261120` 目录保留历史，不覆盖原证据。

RK3588 移植应固定 RKNN Toolkit2 / Runtime / 驱动版本，重新转换并查询算子支持；Jetson 应固定 JetPack / TensorRT / CUDA，重建 engine。逐算子比对、回退比例、峰值内存、散热稳定后延迟与整机能耗都要在目标实机上记录。初始推理批次的功耗字段为 `null`，不是 0 W；后续独立采样已使用 macmon 0.12.0 获取 M4 系统报告功耗，见 [功耗证据](evidence/power-m4-20261120/README.md)。没有使用 TDP 代替实测，也不把不同批次拼成单次推理能耗。

## 安全升级边界

`verify_ota.py` 使用真正的 Ed25519，每次生成临时教学密钥，仅驻留内存。公钥是预置的信任根，不从下载包读取。签名覆盖版本、hash、长度、灰度比例、输入输出契约和运行时标识。校验后用内容 hash 命名模型；同一文件系统内 `os.replace` 原子切换状态文件，配合 fsync 与 pending 恢复记录。启动服务前必须调用 `recover()`。

健康检查实际载入 ONNX 并对 32 个验证样本推理，检查输出有限、形状和准确率。更新失败恢复旧模型，但保留已经接受的最高版本，禁止远端重新下发旧版本。内部恢复已有旧模型与接受网络旧包是两件事。

12 个依赖型检查覆盖真实 INT8 激活、坏签名、元数据篡改、文件篡改、契约不兼容、运行时不兼容、断网保留推理、下载中断、激活后重启恢复、真实模型载入失败回滚、版本重放、灰度排除。中断是可控异常注入，不是实机断电实验。

尚未实现：多进程更新锁、密钥轮换与撤销、可信时间/过期检查、角色和门限签名、远程安全存储、网络下载限额和超时、完整日志上报、文件系统损坏恢复、系统固件 A/B 分区。生产系统应使用成熟更新框架，并按威胁模型补齐这些能力。

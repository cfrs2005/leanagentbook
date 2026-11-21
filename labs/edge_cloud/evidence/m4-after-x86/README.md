# x86 完成之后的 M4 复跑

前置证据为 [x86 CI](../x86-20261120/README.md)。CI 于 UTC 2026-11-21 07:01:47 完成；本次完整复跑 summary 时间为 UTC 07:03:47，两者均为洛杉矶 2026-11-20。使用原独立 Python 3.12.14 环境，Apple M4、macOS 26.3、arm64、ORT 1.23.2 CPU provider。

完整复跑命令：

```sh
/tmp/leanagentbook-ch21-env/bin/python -W error labs/edge_cloud/benchmark.py --output labs/edge_cloud/output/m4-after-x86 --expect-arch arm64
/tmp/leanagentbook-ch21-env/bin/python labs/edge_cloud/verify_ota.py --models labs/edge_cloud/output/m4-after-x86 --report labs/edge_cloud/output/m4-after-x86/ota-tests.json
```

本目录根部保存完整重新训练、导出、量化与实测结果。`environment.txt` 是原环境完整依赖版本。两模型各 2560 次真实请求；`ota-tests.json` 为 12 项通过。`latency.svg` 从新结果生成，章节已改用新图和数值，旧记录不覆盖。

## 同一模型文件的实际移植

`x86-artifacts-on-m4/` 内的 `float.onnx`、`int8.onnx`、`data.npz` 原样复制自 x86 CI artifact，没有重训或修改。对两模型分别执行：

```sh
/tmp/leanagentbook-ch21-env/bin/python labs/edge_cloud/benchmark.py --worker labs/edge_cloud/output/m4-after-x86/x86-artifacts-on-m4/float.onnx --output labs/edge_cloud/output/m4-after-x86/x86-artifacts-on-m4 --expect-arch arm64
/tmp/leanagentbook-ch21-env/bin/python labs/edge_cloud/benchmark.py --worker labs/edge_cloud/output/m4-after-x86/x86-artifacts-on-m4/int8.onnx --output labs/edge_cloud/output/m4-after-x86/x86-artifacts-on-m4 --expect-arch arm64
/tmp/leanagentbook-ch21-env/bin/python labs/edge_cloud/verify_ota.py --models labs/edge_cloud/output/m4-after-x86/x86-artifacts-on-m4 --report labs/edge_cloud/output/m4-after-x86/x86-artifacts-on-m4/ota-tests.json
```

该子目录 summary 汇总真实 worker 指标与目标平台，记录完成时间。模型 SHA 与 x86 summary 一致。两模型各 2560 次推理，12 项 OTA 检查通过，INT8 profile 确认 CPU QLinearMatMul。完整复跑与同文件移植是两组不同实验，不能混用计时。

这些结果补齐“先 x86、后目标设备”的实际执行顺序。没有测量功耗；没有验证 RK3588、Jetson、GPU、NPU；故障注入仍是异常模拟，不是物理断电测试。

整合时尝试系统功耗采样：`sudo -n powermetrics -n 1 -i 1000 --samplers cpu_power` 返回 `sudo: a password is required`。未获得采样数据，因此保留功耗未测；没有用估算值代替。

后续已独立补充 [M4 系统报告功耗采样](../power-m4-20261120/README.md)。本文保留原批次未测记录；后续采样不反写本批次延迟数据。

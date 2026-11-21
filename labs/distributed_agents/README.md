# 独立 Worker 调度实验

目标：观察多个真实子进程通过 loopback HTTP 领取任务、续租、回传和故障接管。Python 3.11+，仅标准库，无模型、无真实用户数据、无外网依赖。协调器在测试主进程的 HTTP 服务线程中；Worker 是独立 Python 进程。状态只存在内存，不能用于生产。

```sh
python3 -m venv /tmp/leanagentbook-distributed-agents-venv
/tmp/leanagentbook-distributed-agents-venv/bin/python labs/distributed_agents/test_runtime.py
```

新运行证据写入忽略目录 `output/`，不会覆盖书中已发布的 `results/`。可用环境变量 `DISTRIBUTED_RESULTS_DIR` 指定另一输出目录。

`requirements.txt` 明确没有第三方依赖。不改根目录虚拟环境。运行约十余秒（机器负载会影响时间），使用系统分配的空闲端口。测试结束或断言失败时，`finally` 会终止、等待并按需杀死子进程，关闭 HTTP 服务。强制杀死整个测试进程或断电不保证执行清理。

| 文件 | 用途 |
| --- | --- |
| [runtime.py](runtime.py) | 完整协调器、HTTP 客户端、独立 Worker 与进程清理 |
| [test_runtime.py](test_runtime.py) | 真实 HTTP 消息、掉线、负载、公平性与输入失败测试 |
| [results/tests.txt](results/tests.txt) | 本次测试原始输出 |
| [results/load-1.json](results/load-1.json) | 单 Worker 基线：48 项积压与分租户汇总 |
| [results/load-3.json](results/load-3.json) | 三 Worker：PID、分配顺序、耗时和事件 |
| [results/crash.json](results/crash.json) | 杀死 Worker 后接管、旧代次拒绝、重复结果 |
| [results/heartbeat.json](results/heartbeat.json) | 任务时长超过租期，通过续租完成 |
| [results/validation.json](results/validation.json) | 输入、预算与幂等检查后的状态 |

输入是 `sum(i*i for i in range(n))`。`delay` 是人为等待，用来控制占用时间；`cost` 是合成 Token 额度，不是模型计费。单 Worker 与三 Worker 执行相同任务集合，不能将其加速比解释为 CPU 扩展能力。第一次 48 项任务预先全部排队，然后启动 Worker；没有实时到达流量。任务完成一次才进入聚合。进程重试可再次执行计算，但结果不会重复计数。

本实验限定可信本机。Worker 名称不是可验证身份；未实现 TLS、鉴权、多机发现、持久化、协调器高可用、实际模型调用、外部副作用补偿、预算重试计费、取消或死信队列。不要把监听地址改成公网地址。

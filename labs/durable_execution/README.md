# Durable Execution 实验

Python 3.11+，仅使用标准库。输入、积分记账和独立接收端扣款都是合成数据。没有模型、真实支付、网络服务或设备动作。

完整解释见[第 16 章](../../chapters/16-durable-execution.md)，实测范围见[验证记录](VALIDATION.md)。所有命令在仓库根目录执行。数据库放在临时目录，不纳入源码。`mktemp -d` 每次生成新目录，避免已有终态影响复现。

## 正常、重复投递与真实崩溃

```sh
LAB_DIR=$(mktemp -d)
python3 labs/durable_execution/queue.py --db "$LAB_DIR/tasks.db" enqueue report-001
python3 labs/durable_execution/queue.py --db "$LAB_DIR/tasks.db" enqueue report-001
python3 labs/durable_execution/queue.py --db "$LAB_DIR/tasks.db" worker --lease 0.3 --crash after-effect
# The preceding command deliberately exits with status 73.
python3 labs/durable_execution/queue.py --db "$LAB_DIR/tasks.db" inspect report-001
python3 labs/durable_execution/queue.py --db "$LAB_DIR/tasks.db" worker --lease 0.3 --run-for 1
python3 labs/durable_execution/queue.py --db "$LAB_DIR/tasks.db" inspect report-001
```

第二次入队输出 `inserted: false`。崩溃后状态为 `running`，检查点 0，已有一条 amount=10 的副作用。恢复后为 `succeeded`，检查点 3，尝试数 2，三条副作用合计 30，事件包含 `effect_deduplicated`。如果命令包在 `set -e` 脚本中，需捕获 73 并断言退出码，不要直接忽略所有错误。

| 故障注入 | 实际退出位置 | 崩溃时副作用条数 | 检查点 |
|---|---|---|---|
| after-claim | 领取事务提交后 | 0 | 0 |
| inside-effect | 账本写入后、事务提交前 | 0（回滚） | 0 |
| after-effect | 账本提交后、检查点提交前 | 1 | 0 |
| after-checkpoint | 第一次检查点提交后 | 1 | 1 |

将上面的参数换成表中任一值，用新数据库重跑。故障参数在该 Worker 每次执行时生效，因此恢复 Worker 不得继续携带 `--crash`。

## 有限重试、超时、取消与补偿

```sh
python3 labs/durable_execution/queue.py --db "$LAB_DIR/tasks.db" enqueue retry-001 --max-attempts 2
python3 labs/durable_execution/queue.py --db "$LAB_DIR/tasks.db" worker --failure transient --run-for 1
python3 labs/durable_execution/queue.py --db "$LAB_DIR/tasks.db" inspect retry-001
python3 labs/durable_execution/queue.py --db "$LAB_DIR/tasks.db" enqueue timeout-001 --steps 1 --delay 1 --attempt-timeout 0.15 --max-attempts 1
python3 labs/durable_execution/queue.py --db "$LAB_DIR/tasks.db" worker --lease 0.3 --run-for 1
python3 labs/durable_execution/queue.py --db "$LAB_DIR/tasks.db" inspect timeout-001
python3 labs/durable_execution/queue.py --db "$LAB_DIR/tasks.db" enqueue cancel-001
python3 labs/durable_execution/queue.py --db "$LAB_DIR/tasks.db" worker --lease 0.3 --crash after-effect
# Expected exit: 73. The committed effect remains after cancellation.
python3 labs/durable_execution/queue.py --db "$LAB_DIR/tasks.db" cancel cancel-001
python3 labs/durable_execution/queue.py --db "$LAB_DIR/tasks.db" compensate cancel-001
python3 labs/durable_execution/queue.py --db "$LAB_DIR/tasks.db" compensate cancel-001
python3 labs/durable_execution/queue.py --db "$LAB_DIR/tasks.db" inspect cancel-001
```

前两项进入 `dlq`，取消项保持 `cancelled`；其原记录 +10，反向记录 -10。重复补偿不会多写反向记录，但会增加一次补偿事件。取消不能删除原始事实。

## 长任务配置

```sh
python3 labs/durable_execution/queue.py --db "$LAB_DIR/long.db" enqueue long-report --steps 120 --delay 30 --total-timeout 7200 --attempt-timeout 4000
python3 labs/durable_execution/queue.py --db "$LAB_DIR/long.db" worker --lease 10 --run-for 7200
```

这是约一小时的配置示例，**本次没有等待一小时验证**。长时间等待每隔租期的三分之一尝试续租；在另一终端使用同一数据库执行 `cancel long-report` 即可请求停止。`--run-for` 是两次任务之间的轮询预算，不会抢占正在运行的任务；结束工作靠任务总期限、单次期限或取消。默认 worker 只做一次领取尝试，处于退避中的任务不会立即完成，演示恢复时要使用 `--run-for`。

## 独立接收端的确认丢失窗口

```sh
python3 labs/durable_execution/remote_gap.py --client "$LAB_DIR/client.db" --receiver "$LAB_DIR/receiver.db" --crash
# Expected exit: 74, after receiver commit but before client receipt.
python3 labs/durable_execution/remote_gap.py --client "$LAB_DIR/client.db" --receiver "$LAB_DIR/receiver.db"
python3 labs/durable_execution/remote_gap.py --client "$LAB_DIR/unsafe-client.db" --receiver "$LAB_DIR/unsafe-receiver.db" --unkeyed --crash
# Expected exit: 74.
python3 labs/durable_execution/remote_gap.py --client "$LAB_DIR/unsafe-client.db" --receiver "$LAB_DIR/unsafe-receiver.db" --unkeyed
```

有稳定操作键时输出 `charges=1,total=10`；无键时 `charges=2,total=20`。两个独立数据库之间没有共同事务。这是远端协议边界的本地模拟，未测试 HTTP 丢包、远端故障或真实支付接口；也未把此脚本接入主队列。真实接收端还需拒绝同键不同金额、定义键保存期限并提供查询接口。本脚本金额固定为 10。

## 测试

```sh
python3 -m unittest discover -s labs/durable_execution -p 'test_*.py' -v
python3 scripts/check_book.py
```

29 项测试包含虚拟时钟的真实 SQLite 状态变更及真实子进程退出、重启、心跳、取消、超时、并发领取和接收端确认窗口。没有依赖下载。任务失败由 `inspect` 的业务状态判断：worker 的退出码 0 表示本次调度执行正常，不代表每个任务成功。73/74 仅用于故障注入；配置错误或非预期异常为非零退出。

# 工作流编排实验

这是第 04 章的可运行切片：Supervisor 调用两个固定脚本 Worker，输入为合成数据，无 LLM、网络或外部写入。需要 Python 3.11+，仅用标准库，无需安装依赖。

```bash
python3 labs/workflow_orchestration/workflow.py
python3 labs/workflow_orchestration/workflow.py --approval approve
python3 labs/workflow_orchestration/workflow.py --approval reject
python3 labs/workflow_orchestration/workflow.py --scenario retry --approval approve
python3 labs/workflow_orchestration/workflow.py --scenario exhausted --approval approve
python3 labs/workflow_orchestration/workflow.py --scenario failure --approval approve
python3 labs/workflow_orchestration/workflow.py --scenario timeout --approval approve
python3 labs/workflow_orchestration/workflow.py --run-timeout 0.01
python3 labs/workflow_orchestration/workflow.py --mode serial --approval approve
python3 -m unittest discover -s labs/workflow_orchestration -p 'test_*.py'
```

输出 JSON 包含 state、results、summary、events、attempts、elapsed_seconds。正常报告最大值 71、样本数 3、建议 inspect。退出码：completed=0；failed/timed_out=1；参数错误=2；awaiting_approval=3；rejected=4；needs_review=5。测试通过时退出码为 0。

默认等待审批不发布，拒绝也不发布；approve 只追加模拟报告事件。参数不是安全审批：没有身份验证和持久化。程序退出后再次执行会重新计算。

每个 Worker 默认最多尝试 2 次，单次 0.1 秒，总时限 1 秒。仅临时错误与单次超时重试。失败保留局部结果，但 summary 为空。已知失败汇总成状态；未预期异常和外部取消传播给调用者。超时依赖可取消的异步等待，不是进程隔离。

对照实验在相同输入下运行串行和并行，各重复 5 次，使用 JSON 耗时计算中位数。两种方式都完成两个任务；脚本注入的等待不是模型或网络性能。实际结果见 [VALIDATION.md](VALIDATION.md)，课程解释见 [第 04 章](../../chapters/04-workflow-orchestration.md)。

## 冲突案例

运行 `python3 labs/workflow_orchestration/workflow.py --scenario conflict --approval approve`，应返回 5。最大值 71 与 observe 建议矛盾，Supervisor 保留双方结果，状态 needs_review，不请求批准或发布。依据是本例固定阈值规则，不是自然语言语义理解。查看 [实际结果](results/conflict.json)。13 项测试包括六种串/并行及审批参数组合的阻断检查。

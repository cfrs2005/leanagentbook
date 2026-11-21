# 离线 Agent Loop 与 Mini-Harness 实验

对应第 02、03 章。Python 3.11+，仅标准库，无网络、密钥或安装步骤。模型是固定任务的脚本模拟器，不是 LLM；用户文本不会改变其商品与数量。目录价格是虚构数据。

从仓库根目录运行：

```bash
python3 labs/agent_loop/mini_agent.py --scenario success
python3 labs/agent_loop/mini_agent.py --scenario failure
python3 labs/agent_loop/mini_agent.py --scenario denied
python3 labs/agent_loop/mini_agent.py --scenario loop
python3 labs/agent_loop/mini_agent.py --scenario timeout
python3 -m unittest discover -s labs/agent_loop -p 'test_*.py'
```

| 场景 | 要检查的行为 |
|---|---|
| success | 查询 12，再乘 3，答案 Total: 36 CNY；三轮模型请求 |
| failure | lookup 不存在商品，观察含 tool_failed |
| denied | 权限检查在执行前拒绝，观察含 permission_denied |
| loop | 相同调用仅执行两次，第三次终止 repeat_limit |
| timeout | 协作式等待被取消，观察含 tool_timeout |

CLI 输出 JSON，包含 status、answer、messages、events。`completed` 仅指收到合法 final；失败说明也可正常结束协议。CLI 是轨迹演示器，各场景正常打印后退出 0；自动验收请运行 unittest，不要仅依靠演示命令退出码。

实现文件 `mini_agent.py` 包含模型协议、两个脚本模型、Runtime、Harness、Policy 和两个工具。测试文件 `test_mini_agent.py` 覆盖：数据流成功、工具异常、授权阻断、参数校验、未知工具、重复限制、不同参数步数限制、工具超时与取消清理、模型超时、总时限、上下文预算、非法模型输出、模型异常、外部取消、非法策略。

默认策略：8 轮模型请求、同一调用最多 2 次、消息 JSON 12000 字符、单次调用 0.1 秒、总运行 2 秒。字符预算不是 token 预算，也不含工具描述。最终回复占一轮。事件仅保存在本次运行内存，无时间戳、跨任务 ID 或持久化。

参数验证仅实现本实验使用的 JSON Schema 子集。没有自动重试、熔断器、并发调度、持久化、独立进程沙箱、真实身份系统或工具返回大小限制。权限是可信调用方配置的本地集合。异步超时不能强制中止阻塞代码，也不撤销外部副作用。测试通过只证明这些模拟条件下的宿主行为，不证明真实模型质量或生产安全性。

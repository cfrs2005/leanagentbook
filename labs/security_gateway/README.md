# 固定工具网关实验

Python 3.11+ 标准库；无真实模型、无外部服务、仅合成身份和内存账本。完整教学见[第 17 章](../../chapters/17-security-governance.md)。

```sh
python3 labs/security_gateway/gateway.py
python3 -m unittest discover -s labs/security_gateway -v
python3 labs/security_gateway/probe_sandbox.py
```

2026-11-20 实测：12 个单元测试通过；demo 输出 amount=30、status=paid，另有审批和执行审计。威胁矩阵见章节第 9 节，覆盖身份伪造、越权、跨租户、直接/间接注入式请求、篡改审批、到期、自批、重放与秘密输出。

macOS 平台探针实测通过：无策略时临时 canary 文件可读、loopback 临时端口可绑定；OS 策略下均 PermissionError。仅使用临时目录，未改变系统配置，未连接外部网络。其他平台或 OS 拒绝初始化时输出 SKIP 与原因，不能算作隔离通过。若环境本身不允许无策略基线运行，脚本会报错而不会错误报告隔离通过。

固定网关单元测试不访问网络，也不创建外部账本。平台探针是单独运行的可选诊断，包含本地 socket bind，不发送数据包。其策略默认允许，仅禁止指定文件及网络操作，绝不能用于不可信任代码。固定网关不提供任意代码执行。

身份注册是受信任启动接口，不是客户端接口。会话、审批、审计与账本均在内存；无过期会话撤销、持久化、生产身份服务或真实 Vault。测试中的秘密只是随机 canary。内部对象不抵御同进程恶意代码，网关应与不可信执行进程分离。没有证明系统无漏洞。

验证环境：macOS，实际解释器 Python 3.15.2；代码仅使用 Python 3.11 已有标准库与语法，但本次没有另起 Python 3.11 解释器测试。`python3 scripts/check_book.py` 通过（当时扫描 51 份 Markdown、134 个本地链接、20 份 SVG；共享工作区计数会变化）。SVG 已用本机 `@resvg/resvg-js` 渲染为 1200 × 640 PNG 并查看完整图，无文字截断；未使用浏览器。官方外链在写作时经网络工具打开核验，检查脚本本身只验证本地链接。

整合复核：在 Python 3.13 上通过 12 项测试。新增审批后金额变更测试，并将关键账本字段绑定到审批摘要；修改金额后旧审批无效。原始平台探针记录未改变。


## 新增：审批绑定的独立隔离工具链

原 `gateway.py` 内存发票演示与 `probe_sandbox.py` 定点探针保留。新增 `IsolatedGateway` 复用会话和审计，提供独立的 `approve_tool()` / `execute_tool()`；工具为固定合成求和任务，不接受任意代码、路径或 URL。

```sh
python3 -m unittest discover -s labs/security_gateway -v
python3 labs/security_gateway/verify_isolation.py --output output/security-isolation-run1
```

第二条命令要求新目录。已发布证据见 [真实运行报告](evidence/isolation-macos-20261120/report.json)和[测试输出](evidence/isolation-macos-20261120/tests.txt)。macOS 共 23 项通过：原 12 项、5 项新增授权检查、6 项真实隔离检查。正常工具可读输入并写结果；越界读、越界写与网络 bind 被 OS 拒绝；超时和合计输出限额会终止并回收进程。

策略为默认拒绝，允许固定输入、worker、解释器与系统库只读访问，以及唯一结果文件写入；允许根目录本身只读、元数据与 sysctl 查询。只启动固定解释器，没有网络允许规则。子进程不继承网关环境变量或令牌。墙钟期限 2 秒，stdout+stderr 合计上限 4096 字节；worker 的 CPU 和文件大小另有限制。审计只写已定义的错误原因，不转录子进程错误和输出。审批绑定参数，变更须重新审批，失败后也不能重用已消费审批。

本实现仅提供 macOS 后端。Linux CI 明确跳过 6 项真实 OS 检查，继续验证标准库授权路径和无后端时拒绝启动；不能把 CI 总体成功解释为 Linux 隔离通过。独立验证命令在不支持的平台退出 2，不静默退回普通子进程。初始化失败则真实检查失败。

这是受控可信 worker 的隔离练习，不是通用不可信代码沙箱。没有完整内存、侧信道、所有 IPC 与逃逸测试；系统和解释器只读目录及全局元数据访问是例外。测试不连接外网或真实设备，不使用真实支付、个人数据或用户密钥。

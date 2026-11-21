# 实际验证记录

执行日期：2026-11-20。所有命令从仓库根目录运行。

环境：Python 3.15.2；Darwin 25.3.0；arm64。

## 自动测试

命令：`python3 -m unittest discover -s labs/workflow_orchestration -p 'test_*.py'`。

```text
............
----------------------------------------------------------------------
Ran 12 tests in 0.450s

OK
```

## CLI 场景

命令前缀：`python3 labs/workflow_orchestration/workflow.py`。

| 参数 | 实际状态 | 退出码 | 尝试数 |
|---|---|---|---|
| `(无参数)` | awaiting_approval | 3 | 2 |
| `--approval approve` | completed | 0 | 2 |
| `--approval reject` | rejected | 4 | 2 |
| `--scenario retry --approval approve` | completed | 0 | 3 |
| `--scenario exhausted --approval approve` | failed | 1 | 3 |
| `--scenario failure --approval approve` | failed | 1 | 2 |
| `--scenario timeout --approval approve` | failed | 1 | 3 |
| `--run-timeout 0.01` | timed_out | 1 | 2 |

另运行 `--max-attempts 0`，退出码为 2，拒绝无效配置。

## 等待重叠对照

每种方式连续运行 5 次，CLI 参数为 `--mode MODE --approval approve`。计时为程序内部 perf_counter 的执行阶段，不含 Python 启动时间。

| 方式 | 5 次耗时（秒） | 中位数（秒） | 每次尝试数 |
|---|---|---|---|
| serial | 0.062221, 0.062213, 0.06223, 0.062184, 0.062171 | 0.062213 | 2 |
| parallel | 0.031183, 0.031191, 0.031185, 0.030696, 0.031185 | 0.031185 | 2 |

输入是合成数据，每个正常 Worker 注入 0.03 秒异步等待。两种模式输出一致。此结果仅展示等待重叠，不能证明真实模型加速、吞吐或质量改进。没有单独测量协调开销、网络流量和 token 成本。

## 验证边界

12 项测试覆盖正常结果、默认待审批、拒绝、临时重试、重试耗尽、永久失败、单次超时、总超时清理、外部取消、并行重叠、串行结果一致和无效参数。未测试真实模型、远端协议、资源耗尽、非协作阻塞、持久化恢复或生产身份验证。

SVG 按仓库检查器验证结构与本地链接；未使用浏览器，最终视觉验收留给读者。

补充兼容检查：`python3.12 -m unittest discover -s labs/workflow_orchestration -p 'test_*.py'`，12 项通过，耗时 0.441 秒。未在 Python 3.11 解释器上实测。

全书检查：已运行 `python3 scripts/check_book.py`，当前失败项为其他并行章节的 `chapters/01-model-foundations.md` 指向尚未生成的 `labs/model_foundations/README.md`。未修改该章节。第 04 章及实验文档的本地链接和 SVG 结构单独检查通过。协调方合并时需重跑全书检查。

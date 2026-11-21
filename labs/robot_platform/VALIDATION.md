# 综合原型验证记录

验证日期：2026-11-20。本机 macOS ARM64；模板运行 Python 3.15.2，真实模型运行 Python 3.12.14。默认教学接口适用 Python 3.11+，其他版本由全书 CI 验证。

| 检查 | 结果 | 范围 |
|---|---|---|
| 默认标准库测试 | 9 项通过 | 实际 HTTP、并发、子进程崩溃、审批、隔离、降级 |
| 模板端到端 | 三种预期状态，三个唯一任务 | 0.578 秒，不含模型载入 |
| 真实模型端到端 | 三种预期状态，三个唯一任务 | 1.147 秒，不含模型载入；模型只写草稿 |
| 权限与重复 | 查看者批准 403；重复审批无新增 | 公开教学身份，不是生产认证 |

[模板完整结果](results/template-report.json) · [模型完整结果](results/model-report.json) · [模型文件摘要](results/model-files.json) · [可阅读报告](results/model-report.html)。结果记录了源代码 hash、环境、版本、审计和逐项模型 token/时间。原始数据库位于本次输出目录，不作为公开附件；公开报告只含合成数据。

真实模型为 google/flan-t5-small，revision `0fc9ddf78a1e988dac52e2dac162b0ede4fd74ab`，torch 2.6.0、transformers 4.48.3、sentencepiece 0.2.0，CPU 单线程，贪心生成。模型输出明确 `verified=false`。异常样例只得到泛泛建议，缺失样例出现无依据文本，正常样例只输出句点。运行成功不代表具备可用的诊断语言能力。

无模型测试包括脚本故障注入；真实模型在单独运行中加载真实权重，两者不能混淆。当前三个固定合成样例只验证状态分支，不足以估计准确率、误报率或稳定延迟。自动 demo 代替人员提交审批，不证明有人实际复核。未做浏览器视觉验收、真实云部署、TLS/SSO、设备连接、实机断电或机器人控制。

复现命令与独立环境见 [README](README.md)。输出必须写新目录；保留结果不会被默认测试重写。

## 设备日志补充 · 2026-11-20

Python 3.15.2 实际执行 device_logs.py，输出 5 条关联：matched、boundary_ambiguous、matched、boundary_ambiguous、outside_observed_windows。新增 5 项测试通过，覆盖时间误差、半开窗口、身份/版本、重复序号/类型/限额及原传感器 hash。输入全部合成，时钟偏移为预设参数，程序只做时间关联，不估计故障概率。结果及源文件摘要在 results/device-log-report.json、device-log-manifest.json。

# v0.1 首批课程整合验证

日期：2026-11-20。主整合环境：macOS，本地 Python 3.15.2。

| 检查 | 结果 | 能证明什么 |
|---|---|---|
| Agent 实验 | 15 项测试通过；五个命令行场景均实际运行 | 宿主循环、参数、权限、预算和可协作超时符合断言 |
| 诊断实验 | 10 项测试通过；三个 CSV 均实际生成 JSON | 教学规则的正常、异常、缺失和输入错误行为 |
| 图表 | 12 个 SVG 通过 XML 检查；封面、地图、专题图通过非浏览器渲染查看 | SVG 可解析；本机字体下主要内容可读 |
| 文档 | 本地链接与章节基本结构检查通过 | 链接目标存在；不证明所有外链和教学结论正确 |
| 发布资料 | 原始 ZIP 被忽略；未加入面试逐字稿 | 发布范围为课程资料与自造实验 |

## 命令行结果

| 场景 | 结果 |
|---|---|
| agent success | completed；Total: 36 CNY |
| agent failure | completed；回答说明缺少目录证据 |
| agent denied | completed；回答说明 permission_denied |
| agent loop | repeat_limit；不继续调用工具 |
| agent timeout | completed；回答说明 tool_timeout |
| robot normal | normal, normal |
| robot abnormal | normal, abnormal |
| robot missing | insufficient_data, normal |

`completed` 是执行协议结束，不能单独作为业务成功率。当前实验没有真实模型服务、生产负载或机器人连接。

## 复现

```bash
python3 scripts/check_book.py
python3 -m unittest discover -s labs/agent_loop -p 'test_*.py'
python3 -m unittest discover -s labs/robot_diagnosis -p 'test_*.py'
```

GitHub Actions 另配置 Python 3.11 和 3.13 的检查矩阵；以对应提交的 Actions 实际结果为准。图表未使用浏览器检查。完整 24 章与实机评测未完成，下一批见路线图。

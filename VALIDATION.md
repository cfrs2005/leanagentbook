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


## v0.2 网站与新增基础课程

2026-11-20：新增 01/04 章；四个实验共 54 项测试在整合环境 Python 3.13 上通过。新增 `scripts/test_labs.py`，后续实验会自动纳入检查。网站使用严格构建及生成后链接检查，搜索索引必须包含所有已发布章节。

GitHub Pages 已部署。Chrome 中已实际完成首页打开、中文“循环”搜索、搜索结果进入第 02 章，并查看 SVG 和 Mermaid 流程图。此记录不表示真实模型或完整 24 章已验收。


## v0.3 工程与平台设计章节

2026-11-20：新增第 14、15、16 章及第 23 章设计稿。整合环境 Python 3.13，七个实验套件共 119 项测试通过：Agent 循环 15、模型基础 17、工作流 12、评测 18、观测 18、持久恢复 29、诊断 10。

| 证据 | 实际结果 | 边界 |
|---|---|---|
| 评测 CLI 与冻结样本 | 60 条基线全部通过；故障版 32 条通过，门禁拒绝发布 | 脚本执行器与合成金标，不代表真实模型质量 |
| 观测与只读回放 | 三条轨迹保留父链；回放工具执行数为 0 | 没有真实模型用量、外部写入或生产遥测平台 |
| 持久恢复 | 子进程真实退出并重启；四个崩溃窗口恢复；接收端幂等与无幂等对照 | 本机 SQLite 与合成账本，不代表跨机或断电可靠性 |
| 平台架构 | 逻辑图、部署图、身份时序、故障表及 12 个推演用例 | 设计材料；未部署身份服务、业务系统或多租户平台 |
| 四张新增 SVG | XML 检查与本机 PNG 渲染查看通过 | 本机字体可读，不代表所有客户端的视觉验收 |

逐项运行记录：[评测](labs/evaluation/VALIDATION.md)、[观测](labs/observability/VALIDATION.md)、[恢复](labs/durable_execution/VALIDATION.md)。各次计时保留在原始报告中；微秒级教学函数耗时不用于性能排名。


## v0.4 检索、RAG、记忆与权限

2026-11-20：新增 09、10、13、17 章。整合运行使用隔离 PDF 环境 Python 3.15.2，11 个套件共 **179 项测试通过，无跳过**。标准库 Python 3.13 环境另通过 177 项，2 项 PDF 测试因缺少可选依赖跳过；已把固定 PDF 依赖加入 GitHub Actions，使发布检查运行全部测试。

| 证据 | 实际结果 | 不能推出什么 |
|---|---|---|
| 09 预训练检索 | 固定 MiniLM / TinyBERT revision，32 文档、28 查询；140 组逐查询路径结果；断网缓存重跑排名一致 | 中文、生产 ANN、并发吞吐与领域外泛化 |
| 10 RAG | 17 项测试；PDF/HTML/Markdown 经真实 CLI 处理；更新和删除使旧上下文失效 | OCR、复杂版面、真实模型生成或高级 RAG 变体已实现 |
| 13 记忆 | 20 项测试；24 个生命周期查询完全匹配，TP=16、FP=0、FN=0 | 自然语言抽取、真实 token 预算和备份擦除 |
| 17 权限 | 12 项测试；批准后把金额 30 改成 300 会拒绝；固定输出不泄露 canary | 生产认证、持久审批或完整任意代码沙箱 |
| macOS OS 探针 | 指定临时文件读取和 loopback 绑定在策略下拒绝 | 整个文件系统、所有网络路径或容器逃逸已测试 |
| 网站 | 严格构建、生成后本地路径和章节搜索覆盖检查通过 | 所有浏览器的视觉验收 |

各章证据：[检索](labs/vector_retrieval/README.md)、[RAG](labs/rag_pipeline/results/verification.md)、[记忆](labs/memory_context/VALIDATION.md)、[权限](labs/security_gateway/README.md)。真实预训练模型结果与规则教学结果分开保存。没有通过修改标签来隐藏效果变差的情况。

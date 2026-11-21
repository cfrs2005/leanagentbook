# 一起把课程写成可验证的工程教材

[返回首页](README.md)

## 一次贡献只解决一个问题

先在 [路线图](ROADMAP.md) 选择章节，阅读 [章节任务书](ai-agent-engineering-book-kit/02-chapter-specs.md)。在 Issue 中说明问题、计划交付的图、实验与验收方法，再提交 PR。作者自己的首批内容同样需要后续读者审阅。

| 交付物 | 最小要求 |
|---|---|
| 正文 | 目标、前置知识、适用边界、失败案例、练习与验收 |
| 图解 | 至少一张有中文标注的原创 SVG，或可编辑 Mermaid；正文解释箭头含义 |
| 对比表 | 比较成本与限制，不能只列优点 |
| 实验 | 明确环境、输入、命令、预期结果；不能把模拟描述为实测 |
| 来源 | 优先官方文档、代码和论文；写明支持的结论与核验日期 |
| 状态 | 已覆盖内容与未覆盖任务分别列出 |

## 本地检查

```bash
python3 scripts/check_book.py
python3 -m unittest discover -s labs/agent_loop -p 'test_*.py'
python3 -m unittest discover -s labs/robot_diagnosis -p 'test_*.py'
```

检查器验证本地文件链接、SVG 格式与基本安全性、章节结构；不验证外部网站可用性、教学准确性或视觉布局。实验测试也不能代替真实模型与实机测试。

## 并行编写

| 工作线 | 可以修改 | 交付时说明 |
|---|---|---|
| 章节作者 | 分配的章节、实验与配图 | 已覆盖任务、未覆盖任务、运行结果 |
| 图解作者 | 分配的 SVG 与视觉说明 | 源文件、尺寸、渲染检查情况 |
| 整合者 | 首页、进度、检查脚本、发布 | 合并结果、版本与验证范围 |

共享目录时，不要同时修改同一文件。不要擅自提交或覆盖其他工作线的修改。每批整合后更新 `CHANGELOG.md`；完整章节必须按 [质量门禁](ai-agent-engineering-book-kit/06-review-checklist.md) 复核。

## 图解规范

遵循 [视觉说明](diagrams/STYLE.md)。重要结论不能只靠颜色区分。SVG 保留文字，包含 `title` 与 `desc`，不嵌入脚本、外部图片或字体。图旁边保留文字说明，方便无障碍阅读。

## 公开资料规则

不提交原始面试、个人身份、密钥、公司内部数据或未授权的材料。案例使用自造数据。不能核实的结论写明“待验证”，不能补造来源。贡献本项目自有内容即同意使用仓库 MIT 许可；引用第三方项目时保持其原许可边界。

## 在线书籍构建与发布

在线阅读入口：[AI Agent 工程图解](https://cfrs2005.github.io/leanagentbook/)。正文仍只在仓库原路径维护；构建脚本把公开资料复制到临时目录，不需要维护第二份正文。

```bash
python3.13 -m venv .venv
.venv/bin/python -m pip install -r requirements-book.txt
python3 scripts/prepare_site.py
.venv/bin/mkdocs build --strict
.venv/bin/mkdocs serve
```

本地启动后访问终端显示的地址。`build/` 是可重新生成的输出，不提交。`main` 分支每次推送会运行 Publish book：检查课程、测试实验、构建网页，再部署 GitHub Pages。PR 只构建，不部署。发布成功以 GitHub Actions 的实际结果和在线地址为准。

配置依据：[Material 发布文档](https://squidfunk.github.io/mkdocs-material/publishing-your-site/)、[图表支持](https://squidfunk.github.io/mkdocs-material/reference/diagrams/)、[GitHub Pages 工作流文档](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)，查阅日期 2026-11-20。

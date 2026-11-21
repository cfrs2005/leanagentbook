# AI Agent 系统架构与工程实践：教材编写项目包

**版本：** 1.0  
**规划日期：** 2026-11-20  
**用途：** 将全书编写任务分配给多个 AI Agent，逐章研究、撰写、实现和审查。

## 这是什么

这不是已经写完的教材，而是一套可执行的教材生产工程，包含：
- 24 章全书目录与章节目标；
- 每章撰写范围、知识点、工程实践与验收要求；
- 按章节组织的 GitHub / 官方文档 / 论文入口；
- Research、Writing、Engineering、Review Agent 的任务提示词；
- 统一章节模板、质量门禁和学习路线。

## 快速开始

1. 阅读 `00-book-charter.md`，确认全书定位与边界。
2. 阅读 `01-book-outline.md`，了解 24 章结构。
3. 阅读 `02-chapter-specs.md`，按章拆分写作任务。
4. 阅读 `03-reference-map.md`，按章节查找开源材料。
5. 将 `04-agent-work-orders.md` 中对应角色的任务发给其他 Agent。
6. 每章按 `05-chapter-template.md` 交付。
7. 使用 `06-review-checklist.md` 验收，不合格章节退回修改。

## 推荐仓库结构

```text
ai-agent-engineering-book/
├── README.md
├── 00-book-charter.md
├── 01-book-outline.md
├── 02-chapter-specs.md
├── 03-reference-map.md
├── 04-agent-work-orders.md
├── 05-chapter-template.md
├── 06-review-checklist.md
├── 07-learning-roadmap.md
├── 08-glossary-seed.md
├── parts/
│   ├── part-01-agent-foundation/
│   ├── part-02-model-engineering/
│   ├── part-03-rag-data-engineering/
│   ├── part-04-agent-production/
│   ├── part-05-robotics-intelligence/
│   └── part-06-system-design/
├── labs/
├── diagrams/
├── datasets/
├── references/
└── changelog.md
```

## 资料使用规则

- 优先使用项目官方 GitHub、官方文档和原始论文。
- GitHub 项目用于学习实现，不等于其所有设计都适合生产。
- 不复制第三方教材正文；只提取概念、实验思路和可引用事实，并遵守其许可证。
- 每次写作必须核对项目当前版本、许可证、维护状态和 API 变化。
- 对无法核实的性能数据、内部架构和厂商实践，明确标注“待验证”，不得编造。
- 书中自己的文字、图表和代码应保持原创；引用资料必须标注来源。

## 本项目不做什么

- 不把 24 章写成术语百科。
- 不把框架 API 罗列当成原理教学。
- 不声称所有 Demo 都是生产级系统。
- 不默认把 LLM 用于确定性控制、安全联锁或实时闭环控制。

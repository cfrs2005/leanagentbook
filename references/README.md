# 来源与核验记录

[返回首页](../README.md)

原始 [资源地图](../ai-agent-engineering-book-kit/03-reference-map.md) 是候选书目，不表示全部经过本轮核验。各章末尾记录实际使用的来源；只引用概念不等于依赖该项目的代码。

| 来源 | 本轮用途 | 核验日期 | 状态 |
|---|---|---|---|
| [Anthropic · Building effective agents](https://www.anthropic.com/research/building-effective-agents) | Workflow / Agent 的控制路径区别 | 2026-11-20 | 正文可读；是概念材料，不当作最新 API 手册 |
| [MCP · Architecture](https://modelcontextprotocol.io/docs/learn/architecture) | 上下文交换协议的职责边界 | 2026-11-20 | 正文可读；当前入口可能随规范版本更新 |
| [LangGraph · Persistence](https://docs.langchain.com/oss/python/langgraph/persistence) | Checkpointer 与跨线程 Store 的作用域 | 2026-11-20 | 正文可读；本轮实验未引入 LangGraph SDK |
| [ROS 2 Jazzy · Recording and playback](https://docs.ros.org/en/jazzy/Tutorials/Beginner-CLI-Tools/Recording-And-Playing-Back-Data/Recording-And-Playing-Back-Data.html) | 后续 Bag 实验候选资料 | 2026-11-20 | 此次访问被站点拦截，不能视为已核验正文 |

## 引用卡模板

| 字段 | 要记录的内容 |
|---|---|
| 支持的结论 | 具体到一个术语边界、算法或 API 行为 |
| 原始链接 | 官方文档、原始论文或代码位置 |
| 版本 | SDK 固定版本、tag 或 commit；纯概念引用写明无需 SDK |
| 核验日期 | 实际查阅日期 |
| 许可证 | 复制或改编代码时核实；普通链接不等于转载授权 |
| 实验限制 | 是否访问真实模型、真实数据或目标硬件 |

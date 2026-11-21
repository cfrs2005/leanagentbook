# 第 14 章：离线评估与回归门禁

Python 3.11+，仅标准库，无密钥、无网络、无真实 LLM、无外部副作用。先阅读[数据集卡](DATASET_CARD.md)，再阅读[章节](../../chapters/14-evaluation.md)。

从仓库根目录执行：

```sh
python3 labs/evaluation/evaluate.py --output labs/evaluation/reports/baseline
python3 labs/evaluation/evaluate.py --profile regressed --baseline labs/evaluation/reports/baseline/report.json --output labs/evaluation/reports/regressed
python3 -m unittest discover -s labs/evaluation -p 'test_*.py' -v
python3 scripts/check_book.py
```

第二条命令应返回 **1**，这是成功检出故障；不要在发布脚本中用 `|| true` 吞掉它。退出码 0 表示本次固定门禁通过，1 表示质量门禁失败，2 表示输入或配置错误。所有报告必须归档在独立目录；重用输出目录会覆盖之前的报告。

[完整实现](evaluate.py) 中 `execute` 只收输入与语料，不收金标；它实际运行计算、检索、条件分支和有上限的重试。`summarize` 才读取金标。每次调用的工具、参数和观察保存在 `traces.json`；逐例检查、分类汇总、切片和门禁在 `report.json`。这属于对冻结输入重新执行脚本的离线回放，不是复读保存的正确答案。

`regressed` 固定注入：算术错工具、换算值偏移、拒绝路径调用工具、取消恢复重试、检索偏向 d6、附加无支持事实。它不用于模拟任何真实模型。模型层的 intent 是直接输入，因此分类指标只是评估接口示范；即使故障版本分类满分，任务成功率仍下降。

门禁采用教学阈值：不少于 50 条；任务、工具序列、参数、四个 RAG 指标均至少 0.95；每类成功率至少 0.8；安全违规为零；与同金标、同语料基线相比，任务成功率降幅不大于 0.02。阈值不是统计显著性检验或行业标准。系统时延仅记录本机函数耗时，不设置可移植性能门禁。

成果：[实际运行摘要](VALIDATION.md)、[基线报告](reports/baseline/report.json)、[故障报告](reports/regressed/report.json)、[基线轨迹](reports/baseline/traces.json)、[故障轨迹](reports/regressed/traces.json)。后续重跑的时延会不同。

# 电机因果诊断实验

这是教学用的完整可运行切片：真实计算贝叶斯后验、模拟干预和结构反事实；数据、CPT、图方向、Agent 都是人为设定。无真实设备接口，无网络调用，无 LLM 服务。

在仓库根目录运行，Python 3.11+，只用标准库：

```sh
python3 -m unittest discover -s labs/causal_diagnosis -v
python3 labs/causal_diagnosis/diagnosis.py --output /tmp/causal-diagnosis-run-1
python3 scripts/check_book.py
```

输出目录必须不存在。重复实验用新目录，不能覆盖保留结果。程序只打印目录名，不打印用户名或绝对路径。

- [完整代码](diagnosis.py)：SCM、枚举推断、反事实、只读脚本 Agent、校准评测。
- [测试](test_diagnosis.py)：解析解、混杂反转、反事实一致性、冲突、缺失、越权、未知字段、校准拆分。
- [数据卡](DATA_CARD.md)：全部建模假设和数据使用限制。
- [完整基准报告](results/reference-v1/report.json)：种子、证据、审计、反事实、后验与可靠性分箱。
- [校准数据](results/reference-v1/calibration.json)、[独立测试数据](results/reference-v1/test.json)：各 1000 行。
- [验证记录](VALIDATION.md)：执行环境、结果与未验证边界。

`ReadOnlyTools.call` 只有一个无参数读取工具。控制工具名、额外工具参数、未知证据字段或非二进制值均拒绝。实际部署时仍需独立进程和权限隔离；Python 对象不是敌对代码沙箱。

# 时间序列异常检测实验

[第 19 章](../../chapters/19-time-series.md) · [完整机器可读结果](results/report.json) · [合成原始数据](results/telemetry.csv)

## 数据卡

| 项目 | 定义 |
| --- | --- |
| 来源与许可 | 课程自造，MIT；不是设备采集或用户数据 |
| 采样 | 12,000 个连续秒，1 Hz，单条合成轨迹 |
| 通道 | 电流 A、温度 °C、转速 rpm；噪声、缺失、缓慢漂移与正常负载变化 |
| 标签 | 10 个故障事件，各持续 120 秒；预兆从故障起点前 40 秒线性增加 |
| 划分 | train [0,5400)、dev [5400,8400)、test [8400,12000)，先划分再开窗 |
| 窗口 | 60 秒历史，15 秒步长；标签为结束时是否处于故障 |
| 数据质量 | 每个窗口内最多连续向前填补 3 点；初始值缺失或更长缺口跳过并记录 |
| 特征 | 每通道 mean/variance/RMS/absolute peak/kurtosis/slope/missing fraction，共 21 维 |
| 模型拟合 | Z-score 与 IF 用训练期已知干净正常段；XGBoost 用全部训练标签 |
| 阈值 | 只枚举开发集分数，以 F1 优先、FP 少其次、阈值高最后来选择 |
| 新模式 | 测试期包含训练和开发均未出现的 speed_loss 故障 |

预兆属于正常标签时刻；因此它的告警在窗口指标中可能是 FP，在事件指标中却可以是提前命中。两个口径都保留，不能混成一个准确率。数据构造器和标注来自同一规则，不是独立人工诊断真值。训练使用精确正常区间是一种理想条件，现场通常无法直接得到。

## 默认离线检查

```sh
python3 -m unittest discover -s labs/time_series -p 'test_*.py' -v
```

仅用 Python 3.11+ 标准库，无模型依赖、无网络。14 项测试覆盖时间与数值契约、原始区间不重叠、未来数据改变不影响过去特征、短缺口政策、指标、开发集约束、有符号提前量及已发布分数回放。它不重新训练模型。特征比较允许小量浮点差异，避免不同 Python 版本的求和实现差异被当成数据错误。

## 真实训练比较

```sh
python3.12 -m venv /tmp/book-timeseries
/tmp/book-timeseries/bin/pip install -r labs/time_series/requirements.txt
/tmp/book-timeseries/bin/python labs/time_series/run.py --output /tmp/time-series-run-01
```

输出目录必须是新目录。默认不覆盖已发布 `results/`。scikit-learn 1.6.1 与 XGBoost 2.1.4 会真正训练，不能用默认离线检查代替这一步。固定模型参数和随机种子在 [run.py](run.py)，完整依赖快照见 [pip-freeze.txt](results/pip-freeze.txt)。

macOS 的 XGBoost 2.1.4 wheel 还需要可加载的 `libomp.dylib`。本次初跑实际遇到缺少此库，随后用已安装 torch 2.6.0 随包的 OpenMP 库解决，只在该进程设置 `DYLD_LIBRARY_PATH`，没有改系统文件。无需为了本实验安装 torch；已有 Homebrew 的机器可安装 libomp 并显式提供路径：

```sh
brew install libomp
DYLD_LIBRARY_PATH="$(brew --prefix libomp)/lib" /tmp/book-timeseries/bin/python labs/time_series/run.py --output /tmp/time-series-run-02
```

上述 Homebrew 安装路径没有在本次重复安装验证。本机实际运行环境为 Python 3.12.14、macOS arm64、单工作线程；实际加载的 OpenMP 文件散列记录在 [runtime.json](results/runtime.json)。Linux 不使用这个 macOS 环境变量，按平台安装库即可。遇到库加载失败时应修复依赖，不能写入假模型分数。

## 实测与复核

2026-11-20：353 个训练、195 个开发、229 个测试窗口，14 个窗口被质量规则跳过。正常拟合 297 窗口。三个模型在同一测试窗口上的结果：

| 方法 | TP | FP | FN | TN | Precision | Recall | F1 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Z-score | 24 | 20 | 0 | 185 | 0.545 | 1.000 | 0.706 |
| Isolation Forest | 24 | 114 | 0 | 91 | 0.174 | 1.000 | 0.296 |
| XGBoost | 10 | 42 | 14 | 163 | 0.192 | 0.417 | 0.263 |

事件检出分别为 3/3、3/3、2/3；每小时不匹配故障的告警段分别为 4、19、5。XGBoost 未检出新的掉速模式。Isolation Forest 的早告警部分早于生成器预兆，同时误报较多，不能称为预测能力更强。全部分数与逐窗口特征都在 report.json，保留失败结果，没有对测试集反调参数。

事件匹配允许从 onset−60 到 end；首告警的提前量是 onset−first_alert，负数表示迟报，未检出是 null。连续的非匹配告警按 15 秒间隔合并为告警段。缺失造成决策间隙时会分段。分母使用整个测试观测区间 1 小时，不表示每秒都经过模型评价。实验没有持续报警状态机、抑制窗口或人工确认逻辑。

## 可视化

```sh
/tmp/book-timeseries/bin/python labs/time_series/plot.py
```

脚本读取已发布结果，画出完整测试时段的三条信号和三种分数，不只截取故障附近。Z-score 图在 1 以上用对数刻度，避免大峰值掩盖阈值附近的变化；另两种分数是线性刻度。输出可编辑 `diagrams/time-series-results.svg`。macOS 默认用 Arial Unicode；其他系统用 `BOOK_PLOT_FONT` 指定中文字体文件。曲线的浅红区域来自合成故障标签，淡黄区域来自生成器预兆，不是模型发现的范围。

## 局限与后续练习

只有一条合成轨迹与 3 个测试事件。相邻窗口重叠，不能当作独立样本估计置信区间。跳过窗口不计入窗口指标，必须额外监控覆盖率。没有真实设备、多设备分组、在线漂移适应、深度时序模型、FFT/STFT/小波特征或剩余寿命训练。

扩展时先固定新数据版本与切分，增加长缺口、其他工况和不同设备；保持原始时间区间与预测标签范围隔离。比较新模型前先定义误报预算和检测时限，再冻结开发策略。不要因本次统计基线更好就宣称它对所有工业任务更好。

# 机器人诊断：本地合成数据实验

这是第 24 章的首个可运行切片。仅使用人工构造的 CSV，不读取 rosbag，不连接实机，不调用模型或网络，不自动控制机器人。源码与注释使用英文；报告中的说明使用中文。

## 运行

需要 Python 3.9+，不需要安装包。在仓库根目录执行：

```sh
python3 labs/robot_diagnosis/detector.py labs/robot_diagnosis/data/normal.csv --output /tmp/robot-normal.json
python3 labs/robot_diagnosis/detector.py labs/robot_diagnosis/data/abnormal.csv --output /tmp/robot-abnormal.json
python3 labs/robot_diagnosis/detector.py labs/robot_diagnosis/data/missing.csv --output /tmp/robot-missing.json
python3 -m json.tool /tmp/robot-abnormal.json
python3 -m unittest discover -s labs/robot_diagnosis -p 'test_*.py'
```

输出目录必须已存在。成功退出码为 0；输入或写文件错误为 2。输入校验失败时不会更新已有输出，请同时检查退出码，避免误读旧报告。不要把输入文件用作输出文件。

## 人工验收表

| 文件 | 第 0–5 秒 | 第 5–10 秒 | 需要检查的证据 |
|---|---|---|---|
| normal.csv | normal | normal | 每个窗口每个信号各有 5 个值 |
| abnormal.csv | normal | abnormal | 第 6/7 秒电流 9/10 A、振动 7/8 mm/s |
| missing.csv | insufficient_data | normal | 第 1 秒电流为空，第 2 秒整行缺失 |

JSON 顶层必须含 `source.sha256`、`rule_version`、`root_cause_confirmed: false` 和 `automatic_control: false`。异常窗口有 `evidence`、未确认的 `hypotheses` 和 `uncertainty`。缺失不生成故障假设。

## 数据与规则约定

- 所有数据均为合成教学数据，没有设备编号、人员信息或原始访谈。
- 固定三列：`time_s,motor_current_a,vibration_mm_s`。相对时间为整数秒，0–3599，严格递增，预期每秒一行。
- 空单元格或缺失行表示没有观测。非数值、非有限值、负值、重复与乱序时间会报错。表头和列数必须准确。
- 5 秒固定窗口；电流 ≥ 8 A 或振动 ≥ 6 mm/s，同一信号至少两次达到阈值才异常。阈值不是厂商规范。
- 有异常优先报告异常，同时保留缺失；没有异常但存在缺失时报告数据不足。尾部窗口不足 5 秒也报告缺失。
- 文件最大 1 MiB。当前实现将小文件和结果保存在内存，不是海量数据处理引擎。
- `synthetic: true` 是实验约定，并非程序检测到数据一定是合成的。不要用真实数据生成带此标签的报告。

## 下一步实验

复制异常样例到临时文件，将第 7 秒两个信号改为 3 和 1。第二个窗口应不再触发。再删除第 8 秒：第二个窗口应为数据不足。解释为什么这两个输出都不能证明设备健康。

实际检查结果与限制见 [VALIDATION.md](VALIDATION.md)。完整业务和技术说明见 [第 24 章](../../chapters/24-robot-diagnosis.md)。

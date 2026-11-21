# ROS Bag 离线实验

原创合成数据，不连接设备。Python 3.12 + 固定依赖生成真正的 ROS2 SQLite3/CDR Bag。数据使用 Humble 消息类型库、metadata v8，无压缩。不是 JSON 改扩展名。

从仓库根目录运行：

```sh
python3 -m unittest discover -s labs/robotics_ros -p 'test_*.py'
uv venv --python 3.12 /tmp/leanagentbook-robotics-ros-venv
uv pip install --python /tmp/leanagentbook-robotics-ros-venv/bin/python -r labs/robotics_ros/requirements.txt
/tmp/leanagentbook-robotics-ros-venv/bin/python labs/robotics_ros/verify_bag.py
/tmp/leanagentbook-robotics-ros-venv/bin/python labs/robotics_ros/bag_lab.py --out labs/robotics_ros/output/run-001
```

目标目录必须不存在，避免覆盖已有证据。更换 run 编号即可重跑。不要将新输出写到 `results/`。标准库测试不导入 rosbags，默认全书测试不需要安装本实验依赖。`verify_bag.py` 为单独执行的依赖型检查，用临时目录生成数据并自动清理。

## 文件与字段

- `source_bag/`：440 条消息，`metadata.yaml` 和真正的 `.db3`。
- `event_bag/`：记录时间相对基准 `[1.8, 2.6)` 秒的 80 条信号、1 条事件，以及窗口外补入的 1 条配置上下文；共 82 条。片段总时长包含 0 秒的上下文，不能用 metadata 总时长代表事件窗。
- `manifest.json`：合成输入、软件版本、配置哈希、频率和偏移。
- `truth.json`：独立的 `(topic, seq) → true_ns` 真值，不从 header 反推。
- `timeseries.csv`：全部 438 条信号的 topic、序号、记录/采样/真值时间和值。
- `context.json`：版本、配置和事件日志；`report.json`：全部 Topic 统计、匹配与缺失结果。
- `thinned_motor.json`：每 100 ms 桶保留首值和极值后的电机序列。
- `checksums.json`：此次产物的 SHA-256 清单。Bag 内可能存在写入端环境元数据，跨机器不要求二进制完全一致；要求解码结果一致。

六种信号都使用 `geometry_msgs/msg/PointStamped` 作为**教学代理**：`point.x` 为合成值，`point.y` 为整数序号，`point.z=0`，`header.frame_id` 为信号名。此字段约定不是实际几何点语义，不应接入真实 ROS 算法。两个上下文 Topic 使用 `std_msgs/msg/String`，其 data 字段内放 JSON；容器与消息序列化本身仍为 SQLite/CDR。

## 已发布证据

[报告](results/report.json)、[时间序列](results/timeseries.csv)、[配置](results/manifest.json)、[真值](results/truth.json)、[原始 Bag 元数据](results/source_bag/metadata.yaml)、[事件 Bag 元数据](results/event_bag/metadata.yaml)、[校验清单](results/checksums.json)。首次生成使用 Python 3.12.14、rosbags 0.10.11。验证日期：2026-11-20。

完整命令与通过记录见 [核查记录](verification.md)。标准库 4 项测试、真实格式 1 项集成测试通过。集成测试覆盖 SQLite 文件头、数据库消息数、CDR 逐条解码、偏移前后真值、缺失序号、异常序号、独立事件读取，以及未来 metadata 版本被拒绝。离线读取成功不表示 DDS QoS 可用，不表示已运行 `ros2 bag play`，也不表示真实传感器同步成功。

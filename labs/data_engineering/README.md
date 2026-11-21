# 数据工程实验

本实验使用确定性合成数据，不调用模型，不连接生产系统。完整正文见 [第 12 章](../../chapters/12-data-engineering.md)。

## 复现

从仓库根目录运行。标准库路径只验证本地消费与恢复，缺依赖时会明确跳过 Parquet 测试。

```sh
python3 -m unittest discover -s labs/data_engineering -p 'test_*.py' -v
python3.12 -m venv /tmp/leanagentbook-data-engineering-venv
/tmp/leanagentbook-data-engineering-venv/bin/pip install -r labs/data_engineering/requirements.txt
/tmp/leanagentbook-data-engineering-venv/bin/python -m unittest discover -s labs/data_engineering -p 'test_*.py' -v
/tmp/leanagentbook-data-engineering-venv/bin/python labs/data_engineering/pipeline.py --output /tmp/data-engineering-run-01 --count 2000 --parquet
```

输出目录必须是新目录。`requirements.txt` 固定 PyArrow 20.0.0，验证环境为 Python 3.12.14。标准库代码要求 Python 3.11+，不保证该固定 PyArrow 版本在所有更新 Python 版本上都有 wheel。不要修改根 `.venv`。

## 2026-11-20 原始结果

| 指标 | 实测值 | 口径 |
| --- | --- | --- |
| 输入 | 2,030 行 | 2,000 唯一事件 + 20 重复 + 10 坏 JSON |
| 事件输出 | 2,000 行 | 幂等去重后；value 总和 99,000 |
| 隔离 / 迟到 | 10 / 20 | 迟到仍保留，按事件时间聚合 |
| 首次消费 | 0.429881 秒 | 文件遍历、解码、每行 SQLite FULL 提交；不含源散列与数据库初始化 |
| 吞吐 | 4,722.23 行/秒 | 包含重复与坏消息的输入行 / 消费时间 |
| 处理延迟 p50 / p95 | 0.199875 / 0.260291 毫秒 | 单行解码至事务提交；不含队列等待、网络、生成与事件年龄 |
| JSONL | 196,728 字节 | 原始输入文件 |
| SQLite | 299,008 字节 | 首次消费后的数据库文件，不代表内存占用 |
| Parquet | 16,532 字节 | 真实 ZSTD 文件，2,000 行，行组大小 512 |
| Parquet 写 / 读 | 0.001243 / 0.026021 秒 | 写含 fsync、替换但不含 Arrow 表构造；读含转 Python 行 |
| 全量重放 | 2,030 行，0.375102 秒 | 保留事件表并将 offset 置零；输出逐行不变 |
| 已完成后续跑 | 0 行 | 持久 offset 已到末尾 |

硬件由本机工具读取：Apple M4、arm64、10 逻辑 CPU；Darwin 25.3.0；SQLite 3.53.1。没有读取内存容量、磁盘型号、温度、后台负载或文件系统挂载参数。单次暖缓存可能影响结果；不能据此估算生产容量，也不能把源文件与 Parquet 大小比当成纯压缩率。

原始证据：

- [metrics.json](results/run-2000/metrics.json)：未四舍五入的时间、全部分桶计数与和、来源与代码散列。
- [events.jsonl](results/run-2000/events.jsonl)：合成输入。
- [events.parquet](results/run-2000/events.parquet)：真实可读文件。
- `state.sqlite`：复现时在输出目录生成事件、进度、隔离表；数据库不随网站发布。公开证据使用源 JSONL、Parquet 和指标文件。
- [标准库测试](results/tests-stdlib.txt)：4 用例，真实 Parquet 路径跳过。
- [真实 Parquet 测试](results/tests-parquet.txt)：4 用例全部通过。
- [完整运行控制台](results/run-2000-console.json)：运行环境与各阶段数字。
- [依赖快照](results/pip-freeze.txt)：隔离环境实际安装版本。

## 故障矩阵

| 注入 | 实际验证 |
| --- | --- |
| 第 4 行事务提交前进程强制退出，退出码 71 | offset 保持 3；重启后与无故障基线逐行相同 |
| 第 4 行事务提交后进程强制退出，退出码 72 | offset 为 4；重启后与无故障基线逐行相同 |
| 全量重放 | 主键去重；事件行与基线一致，隔离表不重复增加 |
| 同 ID 不同 value | 保留首条，冲突进入隔离 |
| 布尔数字、空 ID、未知版本、超界值、非对象 | 隔离，后续行继续处理 |
| 原始文件被修改 | SHA-256 不匹配，拒绝复用进度 |
| 迟到事件 | 标记 late，同时纳入离线事件时间分桶 |

这些检查用真实子进程退出与 SQLite 恢复实现，不是只抛出可捕获异常。测试负载为 250 个唯一事件，恢复后也比较唯一行数与源日志聚合。大样本实验为 2,000 个唯一事件。所有源行是否接受、重复或隔离都计入 offset。

## 已知边界

单进程、单消费者、不可变输入。不是 Kafka/Flink 部署，也不实现持续追加源、分区协调、云对象存储、Iceberg、ClickHouse 或 Feature Store。恢复核对共享契约函数，额外固定断言用于防止循环自证，但仍未使用独立第三方实现验证全部契约。

Parquet 在消费完成后导出，重建即可恢复，不与 SQLite 跨系统原子提交。未注入 Parquet 导出中断，未验证断电、磁盘损坏或网络分区。数据量较大时全量内存和每行提交会成为限制。隔离记录在生产可能含敏感信息，本实验没有真实用户数据。

图形用本地 `@resvg/resvg-js` 2.6.2 渲染为 1200×650 PNG 并查看，没有使用浏览器；最终视觉验收由读者完成。

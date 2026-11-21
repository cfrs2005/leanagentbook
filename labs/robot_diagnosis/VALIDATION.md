# 切片验证记录

日期：2026-11-20。运行环境：本地 Python 3.15.2。输入均为仓库中的人工合成样例。没有使用浏览器，没有连接机器人或云端。

## 已执行

```sh
python3 --version
python3 -m unittest discover -s labs/robot_diagnosis -p 'test_*.py'
python3 labs/robot_diagnosis/detector.py labs/robot_diagnosis/data/normal.csv --output /tmp/robot-normal.json
python3 labs/robot_diagnosis/detector.py labs/robot_diagnosis/data/abnormal.csv --output /tmp/robot-abnormal.json
python3 labs/robot_diagnosis/detector.py labs/robot_diagnosis/data/missing.csv --output /tmp/robot-missing.json
```

结果：10 个测试全部通过；三个命令各生成 2 个窗口。另用 Python `json.loads` 读取三个实际生成文件并断言状态与控制标记，结果如下。

| 样例 | 实际窗口状态 |
|---|---|
| normal | normal, normal |
| abnormal | normal, abnormal |
| missing | insufficient_data, normal |

测试覆盖：正常结果、异常时间和数值证据、缺失行与单元格、阈值相等、至少两次触发、异常伴随缺失、整个窗口缺失、尾部窗口不足、重复和乱序时间、非法或非有限值、空文件、错误表头、输入大小限制、可重复结果与严格 JSON 编解码。

另通过临时文件运行真实命令行：非法 `nan` 输入返回退出码 2，已有输出未改变；相同输入输出路径返回退出码 2。临时文件不加入教材。

两份 SVG 通过 XML 解析检查，均含 `title`、`desc`。使用系统 Quick Look 生成图片并检查全部文字和箭头。初次缩略图裁切后调整了 SVG 固有尺寸，第二次检查完整。没有用浏览器验证。

## 限制

- 仅验证教学规则和小文件处理，不是实机、rosbag、App 或云端验收。
- 没有故障根因标签，没有测量真实准确率、误报率、延迟、内存峰值或成本。
- Python 3.9+ 是建议运行范围；本次仅实际运行 Python 3.15.2，未做多版本兼容矩阵。
- 规则阈值未经设备校准；报告不确认根因，也不自动执行控制。
- 后续大数据、断网恢复、上传去重、模型管理和身份权限仍是章节中的设计项。

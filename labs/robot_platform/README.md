# 机器人诊断端到端教学原型

Python 3.11+，默认仅标准库。输入全部为原创合成数据；使用真实 HTTP、SQLite 事务与子进程崩溃。这里的“云端”是本机回环服务；审批由脚本扮演人员提交，没有连接机器人。

## 运行与查看

从仓库根目录运行，输出目录必须是新目录：

```sh
python3 labs/robot_platform/demo.py --output /tmp/robot-platform-run-1
python3 -m unittest discover -s labs/robot_platform -p 'test_*.py' -v
python3 labs/robot_platform/platform_app.py --database /tmp/robot-platform-run-1/cloud.sqlite --serve
```

最后一个命令打印本机 URL，打开即可查看三种诊断结果。按 Ctrl-C 停止。HTML 是只读页面，展开证据即可阅读；审批通过 API 完成，不存在可控制机器人的按钮。[已运行的静态报告](results/model-report.html) 可直接查看，不需要启动 Python。

| 文件 | 职责 |
|---|---|
| [platform_app.py](platform_app.py) | 输入契约、边缘 outbox、HTTP、持久化任务、证据检索、审批与只读页面 |
| [demo.py](demo.py) | 真实连接失败、模拟丢 ACK、恢复同步、处理和审批的端到端场景 |
| [model_adapter.py](model_adapter.py) | 可选真实 FLAN-T5 草稿；不会改变诊断、权限或批准 |
| [test_platform.py](test_platform.py) | 并发重传、冲突、崩溃、租户隔离、审批与降级 |
| [验证记录](VALIDATION.md) | 模板与真实模型的结果、时间与局限 |

## 可选真实语言模型

默认方案足以跑完整流程，无密钥。真实模型使用 Python 3.12 与固定依赖；模型权重需要首次联网下载，运行阶段只读本地。模型本身不负责根因判定。

```sh
python3.12 -m venv /tmp/robot-platform-model-env
/tmp/robot-platform-model-env/bin/python -m pip install -r labs/robot_platform/requirements-model.txt
/tmp/robot-platform-model-env/bin/python -c "from huggingface_hub import snapshot_download; print(snapshot_download('google/flan-t5-small', revision='0fc9ddf78a1e988dac52e2dac162b0ede4fd74ab', allow_patterns=['*.json','*.model','model.safetensors'], cache_dir='/tmp/robot-platform-models'))"
/tmp/robot-platform-model-env/bin/python labs/robot_platform/demo.py --output /tmp/robot-platform-model-run-1 --model-dir /tmp/robot-platform-models/models--google--flan-t5-small/snapshots/0fc9ddf78a1e988dac52e2dac162b0ede4fd74ab
```

固定 revision 记录来源；目录名检查不能证明权重未被篡改。实际运行权重的 SHA-256 见验证记录中的模型清单。不要把目录名当供应链签名。本次真实输出含无意义句子，不能直接向维修人员提供未核对建议。

## 数据与接口契约

事件含租户、设备、事件 ID、合成 CSV、固件/配置/知识/策略版本和图示 ID。CSV 上限 16 KiB，HTTP JSON 上限 32 KiB。HTTP 身份由服务端固定教学映射确定；客户端填写 tenant 不产生授权。

| API | 教学身份 | 结果 |
|---|---|---|
| `POST /ingest` | `demo-device-a` | 只写 tenant-a/robot-a；相同内容重试返回原 ID，不同内容同 ID 返回 409 |
| `GET /reports` | `demo-viewer-a` | 只读本租户结果；设备身份不能读 |
| `POST /approve-inspection` | `demo-approver-a` | 只接受当前报告 hash 与 `create_inspection_record`；重复不新建记录 |
| `GET /` | 本机演示页 | 无登录，固定显示教学租户 A；不得暴露公网 |

`demo-*` 是公开教学值，不是可部署的凭据。HTTP 服务绑定 127.0.0.1，无 TLS、SSO 或可信设备证明。

## 部署与恢复

1. 使用独立可写输出目录，保留 edge.sqlite 与 cloud.sqlite；不要上传数据库到 GitHub。
2. 运行 demo 后启动 `--serve` 阅读结果。独立 worker 可运行 `platform_app.py --database ...`，每次处理一项；调度循环由调用方负责。
3. 进程崩溃后重新执行 worker。报告与审计在同一事务提交；提交前崩溃可重算，提交后不会重复写报告。多个 worker 可以重复进行只读计算，并不保证只执行一次模型推理。
4. 发送失败时 outbox 保留事件，重新调用 `sync`。本实验使用整事件重传，没有大文件断点续传、自动指数退避或磁盘清理。
5. 审批只产生检查记录，不执行设备动作。生产接入必须另做身份、密钥、TLS、配额、审计保留与真实数据验证。

## 练习与验收

修改输入副本使一个窗口同时含超限和缺失，确认异常证据仍保留缺失提示。然后使相同 ID 的内容变化，确认云端拒绝覆盖。运行测试并检查报告中的 `automatic_control=false`、`root_cause_confirmed=false`。三种演示样例的状态全部符合预期只证明分支覆盖，不能称为现场准确率 100%。

## 设备日志关联

运行 `python3 labs/robot_platform/device_logs.py --output /tmp/robot-device-log-run-1.json`，解析 5 条原创设备日志并关联传感器窗口。100 ms 偏移和 ±20 ms 误差为教学已知参数，跨窗口日志保留歧义，窗外日志不丢弃；程序不推断根因。新增入口是诊断后的本地证据补充，HTTP 仍只接受原来的 CSV 事件。

[样例日志](fixtures/device-events.jsonl) · [实际结果](results/device-log-report.json) · [摘要清单](results/device-log-manifest.json)。日志校验拒绝额外自由文本、其他租户/设备/事件、错误版本、重复序号与不匹配的传感器 hash。5 项新测试通过；原 9 项测试继续保留。

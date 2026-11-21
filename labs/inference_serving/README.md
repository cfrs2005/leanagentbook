# 真实推理服务实验

本实验运行固定 revision 的 FLAN-T5-small，逐 token 生成并通过回环 HTTP 发送事件。数据是合成的；模型是真实权重，不是脚本模型。只测 CPU FP32 单生成槽位，不复现 vLLM、SGLang、TensorRT-LLM 或 llama.cpp 的性能。

## 默认：离线回放，无模型依赖

在仓库根目录运行，Python 3.11+ 标准库即可：

```sh
python3 -m unittest discover -s labs/inference_serving -p 'test_*.py' -v
python3 labs/inference_serving/report.py --output /tmp/inference-replay
python3 scripts/check_book.py
```

测试中的少量手写时间用于核对公式，不是性能数据。`results/requests.jsonl` 的 96 条记录来自真实模型服务。回放不会再次运行模型，不会修改 `results`。

## 真实模型：独立环境

需要 Python 3.12、模型下载空间和可用 CPU 内存；本次在 16 GiB Mac 上完成。模型公开许可在固定 revision 模型卡标为 Apache-2.0。不要把权重放进仓库。

```sh
python3.12 -m venv /tmp/inference-serving-py312
/tmp/inference-serving-py312/bin/python -m pip install -r labs/inference_serving/requirements-real.txt
/tmp/inference-serving-py312/bin/python - <<'PY'
from huggingface_hub import snapshot_download
path = snapshot_download(
    'google/flan-t5-small',
    revision='0fc9ddf78a1e988dac52e2dac162b0ede4fd74ab',
    cache_dir='/tmp/inference-serving-models',
    allow_patterns=['*.json', '*.model', 'model.safetensors'],
)
print(path)
PY
/tmp/inference-serving-py312/bin/python labs/inference_serving/benchmark.py \
  --model /tmp/inference-serving-models/models--google--flan-t5-small/snapshots/0fc9ddf78a1e988dac52e2dac162b0ede4fd74ab \
  --output /tmp/inference-serving-run-01
python3 labs/inference_serving/report.py \
  --input /tmp/inference-serving-run-01 --output /tmp/inference-serving-report-01
/tmp/inference-serving-py312/bin/python labs/inference_serving/plot.py \
  --input /tmp/inference-serving-run-01 --output /tmp/inference-serving-report-01
```

模型缓存目录须以指定 revision 命名；程序会记录模型文件散列，目录名检查不替代内容验证。运行时强制离线加载，不下载或执行模型远程代码。核心依赖固定在 `requirements-real.txt`；它不是全平台通用的完整依赖锁。

本次只读复用了已存在的 `/tmp/leanagentbook-routing-py312` 和 `/tmp/leanagentbook-routing-models/hub/`；未改共享环境依赖。后续复现建议使用上述独立目录。

服务加载后会向父进程报告操作系统分配的临时端口，只绑定 `127.0.0.1`。脚本使用 `try/finally` 终止并等待子进程，超时则 kill；`shutdown.json` 应显示 `child_exited: true`。正常清理采用 SIGTERM，macOS 上返回码 `-15` 不代表压测失败。若整个父进程被外部 SIGKILL，操作系统不会执行 Python finally，需要人工清理残留子进程。

## 负载、记录与边界

- 网格：HTTP 并发 1/2，输入 32/128 token，输出 8/24 token；每格 12 请求。可用 `--requests` 增加每格样本。
- 模型计算：CPU、FP32、torch intra/inter-op 各 1 线程、单生成槽位；线程锁排队无 FIFO 保证。
- 输入：固定英文合成句子重复后 tokenize，取指定 token 前缀，末尾补 EOS；长度包含 EOS。不包含真实个人或企业数据。
- 输出：greedy，`use_cache=True`，最小与最大生成长度相等，抑制提前 EOS；排除 decoder 起始 token。固定长度输出不用于任务质量评估。
- 一个完整 HTTP 预热请求单独记录，不纳入网格。种子 7 打乱网格顺序，只执行一轮；不是稳态容量研究。
- `requests.jsonl`：每条请求的配置、开始偏移、持续时间、错误及所有 token/done 事件。客户端从发 HTTP 前计时；服务端从验证请求体后计时。
- `cells.jsonl`：各格墙钟、请求数、目标/实际 HTTP 峰值并发、生成槽位数。墙钟包含线程池建立到所有请求完成。
- `metadata.json`：硬件、软件、模型散列、精度、队列和内存口径；`warmup.json` 保留预热证据。
- `summary.json`：所有请求分位数、ITL、输入/输出吞吐、请求吞吐及 RSS。错误计入错误数，不计入成功 token 吞吐的分子，整格耗时仍包括失败时间。
- RSS 是服务进程启动以来峰值，含模型加载与预热，不能解释成每格内存增量。CPU 实验的 GPU 显存不适用。

每个事件是一枚真实生成 token ID；可读文本只在 done 中解码，首 token 不保证是可读文字。网络栈可能合并数据包，接收时间仍包含缓冲与客户端调度。逐 token JSON/flush 会增加开销，不能当作无测量开销的纯计算速度。

`report.py` 用 nearest-rank 计算分位数。每格 12 个请求，P95/P99 都是最大值；ITL 的 84/276 个样本不是独立请求。汇总只能描述短实验。闭环请求会随服务变慢而降低发送率，不能用于推断突发开放负载的生产 SLO。

## 文件与修改规则

`results/` 是教材证据，默认测试只读。新压测输出目录必须不存在，避免覆盖。离线报告和图表可写到新的 `/tmp` 或 `output`。`plot.py` 是图表编辑源，输出 PNG 与保留文字的 SVG。日志会将主目录替换为 `$HOME`，发布前仍应检查路径和敏感内容。

常见问题：下载失败先确认网络和固定 revision；端口启动后断流要检查 `server.stderr.txt` 和请求错误字段；不能把状态码 200 当成生成成功。若更换模型、精度或生成策略，应建立独立实验并重做质量验证，不要把数据追加到本次网格。

本次执行证据与限制见[验证记录](VALIDATION.md)。

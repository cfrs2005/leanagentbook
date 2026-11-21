# 第 07 章验证记录

日期：2026-11-20（America/Los_Angeles）。范围仅为本章文件，不代表全书发布完成。

## 实际完成

- 在 Apple M4 / 16 GiB / macOS 26.3 上启动真实 FLAN-T5-small 服务，torch 2.6.0、transformers 4.48.3、CPU FP32、单生成槽位。
- 使用固定 revision `0fc9ddf78a1e988dac52e2dac162b0ede4fd74ab`；模型与分词器文件 SHA-256 在 `results/metadata.json`。
- 真实压测 8 格：并发 1/2 × 输入 32/128 × 输出 8/24，每格 12 请求。共 96 成功、0 错误，预热另记。
- 每个生成 token 保存服务端生成回调时间和客户端事件到达时间，没有用 sleep、文本块或整段完成时间代替首 token。
- 离线复核原始开始/结束区间得到的实际 HTTP 峰值并发与记录相符；实际生成并发始终为 1。
- 服务进程峰值 RSS 678.5–680.6 MiB；CPU 测试，GPU 显存不适用。
- 终止子进程后检查记录端口拒绝连接；`shutdown.json` 为 `child_exited: true`。最终服务日志为空。
- 修复合成输入预处理的超长提示后，完整重跑全部网格；仓库 `results/` 只保留最终重测。

## 验证命令与结果

```sh
/tmp/leanagentbook-routing-py312/bin/python labs/inference_serving/benchmark.py \
  --model /tmp/leanagentbook-routing-models/hub/models--google--flan-t5-small/snapshots/0fc9ddf78a1e988dac52e2dac162b0ede4fd74ab \
  --output /tmp/leanagentbook-inference-final-20261120
python3 labs/inference_serving/report.py --output /tmp/leanagentbook-inference-final-report
/tmp/leanagentbook-routing-py312/bin/python labs/inference_serving/plot.py \
  --output /tmp/leanagentbook-inference-final-report
python3 -m unittest discover -s labs/inference_serving -p 'test_*.py' -v
python3 scripts/check_book.py
```

6 项测试通过：首 token 与完成时间区分、单 token TPOT、尾部分位、失败流排除、损坏计数/乱序拒绝、已录制网格回放。全书检查通过（当时 75 个 Markdown、321 个本地链接、32 个 diagrams SVG；其他线程可能继续新增文件）。该检查只验证本地链接与 SVG 结构。

用 `@resvg/resvg-js` 2.6.2 在本地渲染章节 SVG 并查看完整 PNG，发现并修复下标 n 字体缺字；重新渲染后公式清晰且无裁切。Matplotlib 3.10.1 的实测 PNG 也已查看。没有使用浏览器，最终阅读体验由用户验收。

## 限制

每格只有 12 请求，nearest-rank P95/P99 均是最大样本，不能用于生产尾延迟承诺。只有一轮短时闭环负载，共享主机可能有其他任务。没有 GPU、量化、专用引擎或缓存优化的实测对照。固定输出长度会抑制提前 EOS，不能作为质量实验。HTTP 服务仅适合受控回环教学；未实现生产鉴权、全局有界队列或取消传播。

未修改共享配置、索引、CI 或其他章节。未 git add、commit、push；未安装或修改共享 Python 环境依赖。权重未放入仓库，发布文本与记录未包含用户主目录路径。

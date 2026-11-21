# 第 06 章发布实验记录

本目录是只读发布证据，不是新实验输出位置。全部数据为合成数据，模型训练是真实训练。

- `report.json`：固定配置、版本、种子、参数计数、72 个更新步骤、9 个曲线点、基线与训练后三个划分的全部预测/指标、重载一致性、时长和内存。
- `provenance.json`：模型来源、许可元数据、固定 revision 的文件哈希、代码哈希、CPU 与总内存；没有主机名或本机用户名路径。
- `run.log`：第二次真实运行的原始标准输出与提醒，已检查本机路径。库的 cache 弃用提醒不影响当前固定版本的通过结果。
- `loss-curve.svg` / `loss-curve.png`：由 Matplotlib 按报告生成。SVG 保留文字与矢量路径；源码为上级 `plot.py`。

2026-11-20 实际执行（从仓库根目录）：

```bash
uv venv --python python3.12 /tmp/leanagentbook-ch06-venv
uv pip install --python /tmp/leanagentbook-ch06-venv/bin/python \
  torch==2.5.1 transformers==4.46.3 peft==0.13.2 sentencepiece==0.2.0 \
  numpy==2.1.3 matplotlib==3.9.2 psutil==6.1.0
OMP_NUM_THREADS=2 TOKENIZERS_PARALLELISM=false \
  /tmp/leanagentbook-ch06-venv/bin/python labs/training_post_training/train.py \
  --model-path /tmp/leanagentbook-routing-models/hub/models--google--flan-t5-small/snapshots/0fc9ddf78a1e988dac52e2dac162b0ede4fd74ab \
  --output /tmp/leanagentbook-ch06-run2
/tmp/leanagentbook-ch06-venv/bin/python labs/training_post_training/plot.py \
  --output /tmp/leanagentbook-ch06-curve
python3 -m unittest discover -s labs/training_post_training -p 'test_*.py' -v
python3 scripts/check_book.py
```

复现时使用新的空输出目录；没有共享缓存时删除 `--model-path`，脚本会按固定 revision 下载。安装可改用上级 `requirements-lock.txt`，其中记录本次环境的所有确切依赖版本。本实验使用 Apple M4、16 GiB 物理内存、CPU FP32；训练与轮次验证约 7.41 秒，全过程约 14.75 秒，RSS 峰值 945,815,552 bytes。没有 GPU 显存数据。

执行了两次相同数据/提示/训练参数的运行。第一次结果相同；第二次只改善报告：先采样结束 RSS 再取峰值，并保留基线失败列表。没有用 test 调参。第二次记录作为发布证据，未挑选多个超参数方案中的最佳 test。

最终测试基线 0/12，训练后 12/12；训练后 train 35/36、dev 10/12。验证集 logits 重载最大绝对差 0，全部测试生成一致。不能据此声称生产准确率 100%。测试错误列表为空，验证集错误仍然存在；应直接查看全量预测。

只有 SFT + LoRA 在这里实跑。QLoRA、PPO、DPO、GRPO 与蒸馏没有实跑。离线测试检查数据与发布证据一致性，并不能重新证明训练执行；本记录与训练日志才记录真实运行。适配器权重在本机 `/tmp/leanagentbook-ch06-run2/adapter`，不发布入仓库。

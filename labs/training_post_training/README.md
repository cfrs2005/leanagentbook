# 小模型 LoRA / SFT 实验

[第 06 章正文](../../chapters/06-training-post-training.md) · [数据集卡片](DATASET_CARD.md) · [真实执行记录](results/README.md) · [完整结果](results/report.json)

这是真实 FLAN-T5-small 训练，任务是合成英文工单三分类。训练 36 条、开发 12 条、测试 12 条，适配器按开发 token loss 选择。测试集基线 0/12、训练后 12/12；这主要反映本任务格式和分类适配，不能代表生产能力。

## 离线检查

```sh
python3 -m unittest discover -s labs/training_post_training -p 'test_*.py' -v
```

只检查数据契约和发布证据，不导入训练依赖，不重新训练。默认 5 项检查的覆盖范围见 [测试代码](test_contracts.py)。

## 重新训练

从仓库根目录运行。需要下载固定 revision 的公开模型，或使用执行记录中已有的本地快照。

```sh
python3.12 -m venv /tmp/book-training
/tmp/book-training/bin/pip install -r labs/training_post_training/requirements.txt
OMP_NUM_THREADS=2 TOKENIZERS_PARALLELISM=false /tmp/book-training/bin/python labs/training_post_training/train.py --output /tmp/book-training-run-01
```

输出目录必须为空；权重留在临时目录。脚本实际运行梯度更新、开发集选择、测试评估和适配器重载比较。使用完整 [requirements-lock.txt](requirements-lock.txt) 可对齐本次依赖快照。CPU 峰值 RSS 与耗时口径见执行记录；没有 GPU 显存测量。

保存的新结果不覆盖发布证据。阅读 [train.py](train.py) 与 [config.json](config.json) 可查看所有训练参数。QLoRA、偏好训练和蒸馏仅在正文解释，没有在这个实验中实跑。

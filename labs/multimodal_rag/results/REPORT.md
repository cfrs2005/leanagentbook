# 多模态文搜图实验记录

核验日期：2026-11-20。范围：真实 CLIP 的文搜图，人工标题词集合召回，后期分数融合，开发集阈值与未知查询拒答。不是 OCR、VLM 或真实设备诊断报告。

## 数据与实验协议

图库是 12 张本课程原创 SVG 渲染的 320 × 320 PNG。红、蓝、绿三种颜色，各有圆、方、三角、星四种形状。许可遵循项目 MIT；没有引用第三方图片。模型只读 PNG 像素，不读 SVG 标题。文字通道只用作者标签，字段已标 `author_annotation_not_ocr`。

36 条查询由作者按生成规则标注。开发集 12 已知 + 6 未知；测试集另有 12 已知 + 6 未知。查询 ID 与文字不重叠，图库共享。颜色和形状同时匹配才算相关，未知查询没有相关 ID。切分测的是固定图库查询泛化，不是新图片泛化。没有第二位标注者，不是代表性抽样。构造数据与模型预训练数据的关系未做审计。

开发集固定缩放参数，融合权重从 0.25、0.5、0.75 中选，各路独立选阈值。目标为 `(已知正确放行率 + 未知拒答率) / 2`。候选阈值包含每个开发查询的最高分与全拒答边界。并列规则见 [实现](../retrieval.py)。测试集不得参与拟合；离线测试会把测试分数全部替换为零，确认拟合参数不变。

## 模型选择与可追溯性

最终模型是 `laion/CLIP-ViT-B-32-laion2B-s34B-b79K`，固定 revision `1a25a446712ba5ee05982a381eed697ef9b435cf`。[官方模型卡](https://huggingface.co/laion/CLIP-ViT-B-32-laion2B-s34B-b79K/blob/1a25a446712ba5ee05982a381eed697ef9b435cf/README.md) 明确标注 MIT，说明其使用 OpenCLIP 和 LAION-2B 英文数据训练；模型卡的用途边界仍需遵守。它是约 605 MB 的基础双塔模型，不是微型移动模型。本次使用 Transformers 兼容权重，并未安装 OpenCLIP 训练库。

曾先运行 `openai/clip-vit-base-patch32`，固定 revision `3d74acf9a28c67741b2f4f2ea7635f0aaf6f0268`。后续许可核验发现官方代码仓库有 MIT，但该模型卡没有单独声明权重许可。因此改用明确许可的 LAION 模型，选择原因是许可可追溯性，**不是测试集成绩**。先前的 [原始分数](attempt-openai/raw_scores.json)、[评测](attempt-openai/evaluation.json)、[模型锁](attempt-openai/model-lock.json)、[运行日志](attempt-openai/real-run.log) 与 [当时脚本](attempt-openai/runner.txt) 均保留，不当作最终模型结果。

切换时没有改图片、查询、标签、权重候选、目标函数或阈值规则。测试数据已在先前模型上看过，因此这是一份透明的开发实验记录，不应包装成完全盲测或预注册研究。没有按最终测试结果继续调参。

最终 [模型锁](../model-lock.json) 保存配置、分词器、处理器和权重 SHA-256。权重哈希与固定 revision 官方 API 的 LFS 对象 ID 一致。模型目录在 `/tmp/leanagentbook-multimodal-laion-model`，不入仓库。首次下载通过显式联网步骤完成；推理用本地文件，设置 `HF_HUB_OFFLINE=1`、`TRANSFORMERS_OFFLINE=1`。本次只读复用 `/tmp/leanagentbook-vector-py312`，没有改根 `.venv` 或该环境的依赖。

## 结果

最终指标、冻结参数和逐条决策以 [evaluation.json](evaluation.json) 为准。全部查询 × 图片的未融合分数在 [raw_scores.json](raw_scores.json)，每条原图的哈希也在该文件中。记录的是实际模型输出，没有随机或哈希替代向量。

| 通道 | Recall@1 | Recall@3 | 已知正确放行 / 12 | 已知错误放行 | 未知拒答 / 6 | 放行正确率 |
|---|---:|---:|---:|---:|---:|---:|
| 图片余弦 | 11/12 | 12/12 | 11/12 | 0 | 6/6 | 11/11 |
| 人工标题词集合 | 12/12 | 12/12 | 0/12 | 0 | 6/6 | 不适用 |
| 后期融合 | 12/12 | 12/12 | 10/12 | 0 | 6/6 | 10/10 |

| 通道 | 开发集阈值 | 融合权重 alpha | 开发集目标 |
|---|---:|---:|---:|
| visual | 0.313845217228 | None | 1.000000 |
| text | 0.333333333333 | None | 1.000000 |
| fusion | 0.700652675921 | 0.75 | 1.000000 |

图片缩放范围是 [0.04154341295361519, 0.3723711371421814]，仅来自开发集。

文字基线的测试查询变长且包含同义词，分数降到 0.125 或 0.25，低于 1/3。它排序全部正确却没有放行。图片路将绿色方形排为绿色三角形，但分数未达阈值，因此没有错误放行。融合纠正了这次排序，却拒绝了绿色圆形和绿色方形；其正确放行 10/12，比图片路 11/12 少。**本次不能声称融合整体优于单路。**

具体未正确放行的已知查询：

| 通道 | 查询 ID | 首位图片 | 分数 | 是否放行 |
|---|---|---|---:|---|
| visual | `test_green_square` | `green_triangle` | 0.309507 | 否 |
| text | `test_red_circle` | `red_circle` | 0.125000 | 否 |
| text | `test_red_square` | `red_square` | 0.250000 | 否 |
| text | `test_red_triangle` | `red_triangle` | 0.250000 | 否 |
| text | `test_red_star` | `red_star` | 0.250000 | 否 |
| text | `test_blue_circle` | `blue_circle` | 0.125000 | 否 |
| text | `test_blue_square` | `blue_square` | 0.250000 | 否 |
| text | `test_blue_triangle` | `blue_triangle` | 0.250000 | 否 |
| text | `test_blue_star` | `blue_star` | 0.250000 | 否 |
| text | `test_green_circle` | `green_circle` | 0.125000 | 否 |
| text | `test_green_square` | `green_square` | 0.250000 | 否 |
| text | `test_green_triangle` | `green_triangle` | 0.250000 | 否 |
| text | `test_green_star` | `green_star` | 0.250000 | 否 |
| fusion | `test_green_circle` | `green_circle` | 0.698013 | 否 |
| fusion | `test_green_square` | `green_square` | 0.660386 | 否 |

运行环境：Python 3.12.14；macOS-26.3-arm64-arm-64bit；CPU FP32，两线程。包版本：torch 2.6.0, transformers 4.48.3, huggingface-hub 0.36.2, Pillow 13.0.0, numpy 2.5.5。

记录的模型加载、数据读取与批量编码阶段约 0.433 秒，来自预热文件缓存下的单次运行；不包括依赖导入、下载、模型文件哈希和最终阈值搜索，不代表端到端冷启动或每查询延迟。

Recall@1/3 只以 12 个已知查询为分母，不计未知；本数据每个已知查询只有一个相关图。已知正确放行率还要求最高分达到阈值。放行正确率的分母包括所有已知和未知的放行结果；没有放行时为 `null`。未知错误放行率是 `unknown_accepted / 6`，不能只报未知拒答而隐藏已知查询覆盖率。

未知样本只有 6 条。即便 6/6 拒答，假设独立同分布，Wilson 95% 区间也约为 `[0.61,1]`；人工选样不满足代表性保证。不要外推为真实开放集可靠性。

## 失败路径和证据

[offline-tests.log](offline-tests.log) 记录 12 项标准库测试，包括离线回放、跨划分重复、测试集进入拟合、空查询、未知标签非法、越权集合空候选、NaN、维度不符、缺图、损坏图、路径逃逸和区域越界。每个测试禁止网络 socket 连接，不加载模型。测试中的分数修改仅用于逻辑测试，不生成模型效果记录。

[missing-model.log](missing-model.log) 是真实 CLI 缺少本地模型时的预期失败，退出码非零，且没有继续生成假向量。新环境依赖全量安装没有另外验证；现有环境真实推理已运行。未测试下载中断恢复、GPU、并发吞吐或跨系统浮点一致性。

[evidence-checks.json](evidence-checks.json) 保存所有实际放行结果的原图、页码、整图区域和图片校验值。这证实文件与区域有效，**不证明语义正确**。原图检查器会拒绝损坏与越界证据。若要生成答案，还需核对图片是否支持每个断言，本实验不运行该生成阶段。

## 图与文档检查

章节 SVG 用 resvg 2.6.2 本地渲染为 1200 × 760 PNG，已查看完整渲染结果，没有使用浏览器。原始数据 SVG 是可编辑几何图，PNG 为实际模型输入。全书本地引用与 SVG 结构检查日志见 [book-check.log](book-check.log)；该检查不能证明远端链接或技术结论正确，相关结论另据章节一手来源核验。

## 未验证项

没有运行 OCR、Layout 模型、表格/图表抽取、VLM 结构化抽取、中文查询、图搜图、真实照片、设备故障识别、概率校准器或生成式回答。这里的整图框不是模型检测框。也没有生产认证、对象存储服务、向量数据库、删改同步或线上监控验收。代码展示的是可复现的检索与拒答实验，不是生产系统。

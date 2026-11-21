# 多模态检索实验

本实验真实运行固定版本 CLIP，检索 12 张原创合成图片。文字通道用**人工标签**，不冒充 OCR。默认离线测试只需 Python 3.11+；模型实验是独立步骤。实现及结果均为教学用途，没有真实设备识别或生成式回答验证。

## 文件与证据

| 文件 | 内容 |
|---|---|
| [generate_data.py](generate_data.py) | 原创 SVG、图库元数据、预先写定的查询与答案 |
| [render_data.cjs](render_data.cjs) | SVG 转 PNG，固定 resvg 2.6.2 |
| [data/manifest.json](data/manifest.json) | 图片 ID、标签、原图、页码、区域与合成标识 |
| [data/queries.json](data/queries.json) | dev/test 各 12 已知、6 未知，36 条人工标注 |
| [model-lock.json](model-lock.json) | 模型 revision、文件 SHA-256、官方权重 LFS 校验值 |
| [run_clip.py](run_clip.py) | 本地真实模型推理；缺权重或校验不符则失败 |
| [retrieval.py](retrieval.py) | 词集合检索、融合、开发集选阈值、统计及证据验证 |
| [test_retrieval.py](test_retrieval.py) | 离线回放与失败路径测试，不导入模型 |
| [results/REPORT.md](results/REPORT.md) | 实测结果、错误分析、范围限制 |
| [results/raw_scores.json](results/raw_scores.json) | 每条查询对每张图片的真实余弦和文字分数，含环境与数据哈希 |
| [results/evaluation.json](results/evaluation.json) | 冻结参数、开发集统计、测试集逐条判定 |
| [results/evidence-checks.json](results/evidence-checks.json) | 所有被放行结果的原图、页码、坐标和校验值 |

## 标注协议与许可

图片是本课程原创的白底几何图：红、蓝、绿 × 圆、方、三角、星，共 12 张。SVG 和 PNG 随项目 MIT 许可发布；没有第三方照片、个人信息或设备数据。示例：[红色圆形原图](data/images/red_circle.svg)、[模型实际读取的 PNG](data/images/red_circle.png)。图片内部没有标签文字；CLIP 只读取像素，不读取 SVG 的标题或元数据。

“相关”要求颜色和形状**同时完全匹配**。每条已知查询只有 1 个相关 ID。黄色、紫色、橙色、粉色、五边形、六边形或真实物体在图库中不存在，因此未知查询的相关 ID 列表为空。未知集包含近邻干扰和远离图库的内容。作者按生成规则标注，没有第二位独立标注者；这是构造数据，不是盲测真实图片。

开发查询与测试查询文本、ID 不重叠；两者检索同一固定图库。测试查询使用不同表述，部分保留类别词。它衡量**固定图库上的查询泛化**，不是未见图片、未见设备或跨域泛化。图片和查询都在首次推理前写定。测试结果曝光后没有改标签、提示词、权重候选或阈值目标。

## 离线复现

在仓库根目录执行，不需要安装依赖，不联网，不重新加载模型：

```sh
python3 -m unittest discover -v -s labs/multimodal_rag -p 'test_*.py'
python3 labs/multimodal_rag/retrieval.py labs/multimodal_rag/results/raw_scores.json --output /tmp/multimodal-replay.json
```

回放只重算真实分数的排序和阈值，不是再次运行 CLIP。测试会禁止 socket 连接、验证冻结参数不受测试分数影响，并校验仓库中的原图字节。

## 真实模型实验

建议 Python 3.12。独立依赖见 [requirements.txt](requirements.txt)。新环境只写 `/tmp`：

```sh
python3.12 -m venv /tmp/leanagentbook-multimodal-py312
/tmp/leanagentbook-multimodal-py312/bin/python -m pip install -r labs/multimodal_rag/requirements.txt
HF_HUB_DISABLE_XET=1 TOKENIZERS_PARALLELISM=false /tmp/leanagentbook-multimodal-py312/bin/python labs/multimodal_rag/run_clip.py --download --output /tmp/multimodal-new-run
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false /tmp/leanagentbook-multimodal-py312/bin/python labs/multimodal_rag/run_clip.py --output /tmp/multimodal-offline-run
```

首次下载约 605 MB 权重，另需依赖安装空间。模型为 `laion/CLIP-ViT-B-32-laion2B-s34B-b79K`，revision 为 `1a25a446712ba5ee05982a381eed697ef9b435cf`。它是 CLIP 架构的基础 ViT 变体，比常见大型生成式 VLM 小，但不是手机级微型模型。本次只读复用了已存在的 `/tmp/leanagentbook-vector-py312`；没有修改根 `.venv`。新建虚拟环境安装步骤未另做一轮验证；实际包版本完整记录在原始结果中。

没有 `--download` 时，脚本只接受本地模型，不请求模型服务，也不会自动退回随机向量。权重默认在 `/tmp/leanagentbook-multimodal-laion-model`，不入仓库。模型哈希必须与锁文件相同；权重哈希已与固定 revision 的官方 LFS 元数据比对。LAION 官方模型卡明确标注 MIT 许可，说明模型通过 OpenCLIP 在 LAION-2B 英文子集上训练；本仓库不重新分发权重。

如需重新生成数据（不改变参数与标注），运行：

```sh
python3 labs/multimodal_rag/generate_data.py
npm install --prefix /tmp/leanagentbook-svg-preview --no-audit --no-fund @resvg/resvg-js@2.6.2
node labs/multimodal_rag/render_data.cjs
```

生成参数一旦改变，旧结果不再证明新数据表现。先另存旧报告，再建立新开发/测试划分。不要用改过的数据解释旧分数。

## 算法约定

- 图片通道：CLIP 文本塔对查询编码、图片塔对 PNG 编码，L2 归一化后取点积。使用 FP32 CPU，两线程；不用 softmax 作为置信度。
- 文字通道：英文小写词集合的 Jaccard，`|query ∩ title| / |query ∪ title|`。它是词汇基线，不是 OCR 或文本向量模型。
- 后期融合：开发集所有图片余弦的最小/最大值确定全局缩放，裁剪到 `[0,1]` 后与文字分数加权。只在开发集比较 `alpha ∈ {0.25,0.5,0.75}`。
- 每路阈值分别选择，接受条件是 `top_score >= threshold`。候选阈值是开发集各查询最高分及其最大值的下一个浮点数，覆盖“全拒答”。
- 目标为 `(已知正确放行率 + 未知拒答率) / 2`。并列先选未知错误放行少，再选已知错误放行少，最后选较高阈值；权重仍并列则保留先遍历者。开发集缺少已知或未知类别应视为无效实验。
- 过滤租户与集合后才排候选名次；不能把这个教学过滤器当作完整身份认证。文件访问还必须检查根目录边界、文件哈希、页码和区域。
- 原图完整检查仅证实文件未变，不证明召回语义正确。即使证据包完整，错误图片也不能用来证明答案。

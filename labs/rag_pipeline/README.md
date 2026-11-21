# RAG 全链路独立实验

本实验使用合成资料，演示真实文件摄取、父子切片、SQLite 持久化、词项 BM25、权限过滤、引用、更新及删除。回答是 **extractive/scripted（摘录式脚本）**，不调用真实模型，没有 embedding 或网络检索。读者说明见[第 10 章](../../chapters/10-rag-pipeline.md)。

## 基础运行

需要 Python 3.11+。在仓库根运行；不需要第 09 章文件或项目根虚拟环境。

```sh
RAG_RUN_DIR=$(mktemp -d)
python3 labs/rag_pipeline/pipeline.py --db "$RAG_RUN_DIR/rag.sqlite" ingest labs/rag_pipeline/fixtures/battery.md --id battery
python3 labs/rag_pipeline/pipeline.py --db "$RAG_RUN_DIR/rag.sqlite" ingest labs/rag_pipeline/fixtures/network.html --id network
python3 labs/rag_pipeline/pipeline.py --db "$RAG_RUN_DIR/rag.sqlite" query '电池存储温度'
python3 labs/rag_pipeline/pipeline.py --db "$RAG_RUN_DIR/rag.sqlite" ingest labs/rag_pipeline/fixtures/private.md --id private --role technician
python3 labs/rag_pipeline/pipeline.py --db "$RAG_RUN_DIR/rag.sqlite" query Privatecanary482
python3 labs/rag_pipeline/pipeline.py --db "$RAG_RUN_DIR/rag.sqlite" query Privatecanary482 --principal technician
python3 labs/rag_pipeline/pipeline.py --db "$RAG_RUN_DIR/rag.sqlite" delete battery
python3 labs/rag_pipeline/pipeline.py --db "$RAG_RUN_DIR/rag.sqlite" query '电池存储温度'
python3 -m unittest discover -s labs/rag_pipeline -v
python3 labs/rag_pipeline/evaluate.py
```

首次问题返回摘录与引用。受限唯一标记仅 technician 能查到；删除后的电池问题拒答。`--principal` 只模拟可信服务端已解析的角色，**不是认证接口**。不要把此 CLI 包成允许任意角色输入的公共 API。

## PDF 附加运行

固定直接依赖在 [requirements-pdf.txt](requirements-pdf.txt)，隔离安装，不修改根 `.venv`。PDF 已包含在 fixtures；生成器用于复现，生成后覆盖同名原创测试文件。它是一页真实 PDF 文本对象，不是改扩展名。

```sh
RAG_PDF_ENV=$(mktemp -d)
python3 -m venv "$RAG_PDF_ENV"
"$RAG_PDF_ENV/bin/python" -m pip install -r labs/rag_pipeline/requirements-pdf.txt
"$RAG_PDF_ENV/bin/python" labs/rag_pipeline/make_pdf.py
"$RAG_PDF_ENV/bin/python" -m unittest discover -s labs/rag_pipeline -v
RAG_PDF_RUN=$(mktemp -d)
"$RAG_PDF_ENV/bin/python" labs/rag_pipeline/pipeline.py --db "$RAG_PDF_RUN/rag.sqlite" ingest labs/rag_pipeline/fixtures/calibration.pdf --id calibration
"$RAG_PDF_ENV/bin/python" labs/rag_pipeline/pipeline.py --db "$RAG_PDF_RUN/rag.sqlite" query 'calibration interval'
```

结果应包含 `14 days`、`pdf-page:1` 和 `version:1`。没有依赖的基础环境会跳过两个 PDF 测试，不能把 skip 当作成功。损坏 PDF 抛错；没有文本的页明确提示需要 OCR。本实验不自动安装或运行 OCR。

## 更新与缓存失效

以下代码在内存数据库实际演示同一文档的更新、旧句柄失效和删除：

```sh
python3 - <<'PY'
from pathlib import Path
import sys
import tempfile
sys.path.insert(0, 'labs/rag_pipeline')
from pipeline import Store
with tempfile.TemporaryDirectory() as temp:
    path = Path(temp) / 'guide.md'
    store = Store(':memory:')
    path.write_text('Replacement interval: 30 days.', encoding='utf-8')
    assert store.ingest(path, 'guide')['version'] == 1
    old = store.context('replacement')
    path.write_text('Replacement interval: 45 days.', encoding='utf-8')
    assert store.ingest(path, 'guide')['version'] == 2
    assert store.answer(old)['status'] == 'refused'
    current = store.context('replacement')
    assert '45 days' in store.answer(current)['answer']
    store.delete('guide')
    assert store.answer(current)['status'] == 'refused'
    assert not store.search('replacement')
    store.close()
print('PASS update, stale context, deletion')
PY
```

## 数据与引用约定

- SQLite 表：`documents` 保存当前来源/权限/版本；`parents` 与 `children` 保存原文；`postings` 保存倒排词频；`contexts` 只保存 ID、角色和有效代数；`versions` 保留文档 ID 的单调版本计数。
- 子段命中后返回完整父段，父段去重。父段 600 字符，子段 180 字符、重叠 40 字符；可用 Python API 参数调整。
- 偏移为 Unicode 字符半开区间。Markdown 定位到原文件行块，HTML 定位到文本节点源代码起始行，PDF 定位到页。偏移相对解析文本块，不是原文件字节或页面坐标。
- 引用记录原路径和当时版本，但不归档历史原文件；路径指向的文件后来可能变化，阅读引用时必须核对版本。
- 任意写入变更会清空全部上下文，不做细粒度缓存复用。删除完成后重新调用 `answer()` 不能读取旧缓存；已经返回到用户手中的内容无法撤回。

## 评测与验收

[queries.json](queries.json) 是手工预先标注的合成集合；评测代码不读取标注来调整检索分数。9 条正例计算 Recall、MRR、NDCG，3 条负例单独计算空结果正确率。K=3 指父段预算，再按文档去重。每次延迟会变化，只有 12 次观测，不能代表吞吐或稳定的生产 p95。

[retrieval.json](results/retrieval.json) 保存实际排名和环境；[验证记录](results/verification.md) 区分已测与未测。[test_pipeline.py](test_pipeline.py) 覆盖更新替换、删除级联、跨连接旧句柄、权限变化、空证据、恶意内容、HTML 脚本排除、中文表格、幂等、重启持久化与 PDF 失败路径。

验收时应同时看到三种格式成功、引用可定位、旧版本和缓存不可重读、权限有效、无证据拒答、实际离线指标。只验证 CLI 能启动不够。

## 限制

HTML 是文本节点提取，不计算 CSS 可见性，不执行 JavaScript，也不重建表格关系。Markdown 保留语法但不完整解析 AST，空行或长度边界可能打断复杂表格和代码块。PDF 仅文本层提取，不支持可靠的多列、扫描 OCR、复杂表格或图像理解。

BM25 是字面基线；相同词不保证语义相关。未实现 query rewrite、multi-query、Dense/hybrid、神经重排、真实 LLM、GraphRAG、CRAG 或 Self-RAG。注入测试仅证明脚本没有执行文档指令的路径，不证明真实模型安全。指纹与解析使用同一份已读取的字节；原文件后来仍可能被覆盖，生产应从不可变对象版本摄取并按版本定位。

只测试小文件及顺序操作、两个连接间的变更可见性，不测试高并发压力、跨机部署、备份擦除或恢复。直接依赖固定，传递依赖版本见验证记录，未承诺字节级环境可复现。实际测试 Python 版本以记录为准，未覆盖所有 3.11+ 解释器。

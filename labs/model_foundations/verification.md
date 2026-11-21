# 第01章真实模型核查记录

日期：2026-11-20。

```text
$ python3 -B -m unittest discover -s labs/model_foundations -p test_*.py
......................
----------------------------------------------------------------------
Ran 22 tests in 0.001s

OK
exit_code=0
```

```text
$ /tmp/leanagentbook-routing-py312/bin/python labs/model_foundations/verify_model.py --model-path /tmp/leanagentbook-routing-models/hub/models--google--flan-t5-small/snapshots/0fc9ddf78a1e988dac52e2dac162b0ede4fd74ab --evidence labs/model_foundations/results/local-model-20261120
PASS: source/model/data hashes; all 36 tokenizer, decoder and schema checks; 2 fresh generation replays
exit_code=0
```

```text
$ /tmp/leanagentbook-routing-py312/bin/python labs/model_foundations/verify_constrained.py --model-path /tmp/leanagentbook-routing-models/hub/models--google--flan-t5-small/snapshots/0fc9ddf78a1e988dac52e2dac162b0ede4fd74ab --evidence labs/model_foundations/results/constrained-20261120
PASS: hashes; 18 schema/codec/token/branch checks; 2 fresh constrained model generations
From v4.47 onwards, when a model cache is to be returned, `generate` will return a `Cache` instance instead by default (as opposed to the legacy tuple of tuples format). If you want to keep returning the legacy format, please set `return_legacy_cache=True`.
exit_code=0
```

```text
$ python3 scripts/check_book.py
PASS: 96 Markdown files, 449 local links, 36 SVGs
Scope: local paths and SVG structure; not external links, rendering, or technical accuracy.
exit_code=0
```

生成证据：自由路径36次，34次结构失败、2次结构合格但算术错误；有限enum路径18次结构合格、14次语义正确、4次语义错误。全部原文保留。固定T5的左右括号未知token由显式哨兵标点编码处理，不是模型原生JSON能力。

两项可选检查分别重新运行2次模型推理；默认22项测试仅标准库。未修改共享依赖、未上传权重、未提交Git。

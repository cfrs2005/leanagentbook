# 第 20 章核查记录

日期：2026-11-20。仅限本章与全书静态链接检查。

```text
$ python3 -m unittest discover -s labs/robotics_ros -p test_*.py
....
----------------------------------------------------------------------
Ran 4 tests in 0.000s

OK
exit_code=0
```

```text
$ /tmp/leanagentbook-robotics-ros-venv/bin/python labs/robotics_ros/verify_bag.py
.
----------------------------------------------------------------------
Ran 1 test in 0.137s

OK
exit_code=0
```

```text
$ python3 scripts/check_book.py
PASS: 87 Markdown files, 383 local links, 35 SVGs
Scope: local paths and SVG structure; not external links, rendering, or technical accuracy.
exit_code=0
```

补充核查：已发布 checksums 全部匹配；临时目录重生成的 manifest、truth、timeseries、report、context、thinned_motor 六份文件与已发布证据逐字节相同。

事件 Bag 检查在原始目录移走后执行，逐条 CDR 解码，并与预期窗口的原始字节集合比较。

SVG 使用 resvg-py 本地渲染并查看 PNG；未使用浏览器。Quick Look 预览发生裁切，最终使用完整 resvg 渲染核对。

未验证：ROS CLI/DDS 网络、QoS 实际协商、实机时间同步、传感器物理语义、实时回放和控制效果。

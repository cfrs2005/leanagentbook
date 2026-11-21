# Mermaid 实际语法检查

本检查器逐一调用 Mermaid 的 `parse()`，不是只数代码块。独立 Node 环境不改全书 Python 环境，也不在仓库根目录安装 npm 依赖。

## 固定环境与复现

- Mermaid：11.4.1。
- JSDOM：26.0.0，仅提供内存 DOM 供解析和文本处理使用。
- 实测 Node：v22.22.2；npm：10.9.7。
- 完整传递依赖由本目录 `package-lock.json` 固定。

从仓库根目录执行：

```sh
mkdir -p /tmp/leanagentbook-mermaid-11.4.1
cp scripts/mermaid-check/package.json /tmp/leanagentbook-mermaid-11.4.1/package.json
cp scripts/mermaid-check/package-lock.json /tmp/leanagentbook-mermaid-11.4.1/package-lock.json
npm ci --prefix /tmp/leanagentbook-mermaid-11.4.1 --no-audit --no-fund
node scripts/check_mermaid.mjs --env /tmp/leanagentbook-mermaid-11.4.1 --out /tmp/leanagentbook-mermaid-report.json
```

默认仓库根目录按脚本位置计算，也可用 `--root` 指定检查副本。输出父目录需已存在。例行重跑写 `/tmp`，不覆盖本目录的已发布报告。

## 本次结果

2026-11-20 最终磁盘扫描：**25 份章节，72 个 Mermaid 块，72 个解析通过，0 个失败**。包括第08、09、19章新加的时序图。逐块位置、图类型、源码 SHA-256 和章节快照见 [report.json](report.json)。扫描完成后再次核对所有章节哈希及文件清单，未发现扫描期间变动。

检查器运行前先解析一个合法图和一个故意缺右括号的非法图：合法接受、非法拒绝。另在临时目录执行集成反例：较长普通代码围栏中的 Mermaid 示例不应被误计；真正合法块通过；真正非法块在第12行报告，进程退出1。结果符合预期。未把反例写入章节。

## 检查范围

- 递归扫描 `chapters/` 中的 Markdown 文件；识别反引号及波浪号围栏，保留块起始行。
- 每块实际执行 `mermaid.parse()`；空图或未闭合 Mermaid 围栏失败。
- 失败报告保留章节、围栏行号、解析器错误及可用的解析器相对行号；相对行号不冒充精确 Markdown 错误行。
- 无图、解析失败、扫描中源文件变化均返回非零退出码。

**没有启动浏览器，没有访问读书网页，也没有执行 SVG 布局或 UI 验证。** 本结果证明固定版本解析器接受这些源码，不证明图中文字没有遮挡、网页脚本已加载或其他 Mermaid 版本完全兼容。JSDOM 不是真实浏览器渲染器。未修改章节，也未提交 Git。

官方接口说明：[Mermaid Usage](https://mermaid.js.org/config/usage.html)，访问日期2026-11-20。网页当前版本可能不同；本检查的版本以本地包和依赖锁为准。

## 跨机器安装修订

首轮 CI 发现临时目录生成的锁文件包含本机路径。已重新生成标准 registry 锁（196 个 package 条目），检查所有包均无 file: 本地依赖或 link 条目，并在全新目录执行 npm ci 与 72 块解析成功。固定顶层版本仍为 Mermaid 11.4.1 / JSDOM 26.0.0。该修订保留在 Git 历史中，不能把此前本机已有依赖上的通过当作干净安装证明。

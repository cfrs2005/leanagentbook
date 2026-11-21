# Lean Agent Book 图形规范

本目录为《AI Agent 工程图解》提供原创、可编辑的 SVG 图形。英文品牌为 **Lean Agent Book**。视觉采用纸色底、深墨文字、橙色编号和绿色辅助信息；以阅读为主，不使用照片、渐变或装饰性噪点。

## 文件与用途

| 文件 | 尺寸 | 用途 |
| --- | --- | --- |
| `cover.svg` | 1200 × 420 | 教材封面；右侧循环为概念示意，不是固定执行流程 |
| `learning-map.svg` | 1200 × 800 | 六部分、24 章课程导航，按编号从左到右、从上到下阅读 |
| `icons/foundation.svg` | 64 × 64 | Part I，基础架构，01–04 章；阶梯形基础 |
| `icons/model.svg` | 64 × 64 | Part II，模型工程，05–08 章；模型芯片 |
| `icons/retrieval.svg` | 64 × 64 | Part III，检索与数据，09–12 章；文档与放大镜 |
| `icons/production.svg` | 64 × 64 | Part IV，工程化与治理，13–17 章；盾牌与检查标记 |
| `icons/robotics.svg` | 64 × 64 | Part V，分布式 AI 与机器人，18–22 章；机器人 |
| `icons/architecture.svg` | 64 × 64 | Part VI，综合架构，23–24 章；分层节点 |

## 颜色

| 角色 | 色值 | 使用规则 |
| --- | --- | --- |
| 纸色 | `#F6F1E7` | 页面及封面底色 |
| 卡片 | `#FFFCF6` | 课程分组底色 |
| 深墨 | `#22312F` | 正文、标题、图标主线 |
| 陶橙 | `#B94F2D` | 章节编号、少量重点 |
| 森绿 | `#316653` | 品牌、辅助标签、状态概念 |
| 次级文字 | `#596963` | 说明与副标题 |
| 分隔线 | `#D9D2C4` | 非必要边框和分隔线，不承担唯一信息 |

不只用颜色传递信息。编号、文字和图形同时说明含义。图标透明底，适合放在上述浅色背景上；深色背景须另做适配。

## 字体与排版

- 字体依次回退到 `PingFang SC`、`Noto Sans CJK SC`、`Microsoft YaHei` 和系统无衬线字体。
- SVG 保留真实文字，不转曲，不嵌入字体或远程资源。修改中文不需要重新绘制路径。
- 封面主标题为 52 单位。地图主标题为 34，分组标题为 18，章节条目为 16，说明为 14。
- 地图使用三列两行；卡片为 360 × 277，列距 20，章节行距 36。
- 图标使用 64 × 64 画布、2.5 单位线宽、圆角端点。地图中直接内嵌图标几何形状，避免外部引用丢失。修改图标时同步地图。
- 宽图保持原始宽高比。小屏可提供原图打开或横向滚动，不应把 24 章地图压成无法阅读的缩略图。

## 内容边界

课程分组与章节编号依据 `../ai-agent-engineering-book-kit/01-book-outline.md`，定位依据 `00-book-charter.md`，教学层次依据 `05-chapter-template.md`；核对日期为 2026-11-20。

地图使用简短中文标题，部分英文术语译成中文；完整标题以全书目录为准。地图展示课程结构，不表示章节已完成，不表示强制依赖，也不承诺学习时间或效果。封面循环仅用于表现问题、模型、工具与证据的联系。

图形为本任务原创，无第三方图片、面试记录或个人信息。没有新增外部技术结论，因此没有外部技术引文。图形的发布许可遵循项目最终采用的许可；本文件不替项目选择许可。

## 可访问性与编辑

每份 SVG 均包含 `title`、`desc`、`role="img"` 和 `aria-labelledby`。作为 HTML 图片使用时仍应提供 `alt`；例如封面用“AI Agent 工程图解，Lean Agent Book”，地图用“六部分 24 章课程地图，完整章节见文字目录”。阅读器不会一致地朗读图片内部说明，地图应与文字目录同时提供。

每份文件的 `title` 和 `desc` ID 在各自文档内唯一。若把多个 SVG 直接粘贴进同一 HTML 文档，须给 ID 和 `aria-labelledby` 增加文件前缀。使用独立图片引用时无需更改。

## 本次验证与复现

已用 Python 标准库解析 8 份 SVG，检查标题、说明、画布、禁止脚本和外部资源，以及地图编号恰好覆盖 01–24。已用 `@resvg/resvg-js` 2.6.2 在本机加载系统字体，将全部 8 份 SVG 渲染为 PNG；封面与地图输出尺寸分别为 1200 × 420、1200 × 800，并查看了封面、地图和六个图标的完整渲染图。没有使用浏览器。

可在仓库根目录运行以下结构检查，无需额外 Python 依赖：

```sh
python3 - <<'PY'
from pathlib import Path
import xml.etree.ElementTree as ET

ns = {'s': 'http://www.w3.org/2000/svg'}
paths = [Path('diagrams/cover.svg'), Path('diagrams/learning-map.svg')]
paths += sorted(Path('diagrams/icons').glob('*.svg'))
assert len(paths) == 8
for path in paths:
    root = ET.parse(path).getroot()
    assert root.tag == '{http://www.w3.org/2000/svg}svg'
    assert root.get('role') == 'img'
    assert root.get('aria-labelledby') == 'title desc'
    for tag in ('title', 'desc'):
        element = root.find('s:' + tag, ns)
        assert element is not None and element.text and element.get('id') == tag
    assert root.get('viewBox')
    for node in root.iter():
        assert node.tag.rsplit('}', 1)[-1] not in ('script', 'foreignObject', 'image')
        assert not any(key.endswith('href') for key in node.attrib)
    print('PASS', path)
root = ET.parse('diagrams/learning-map.svg').getroot()
numbers = [node.text for node in root.findall('.//s:text', ns)
           if node.text and len(node.text) == 2 and node.text.isdigit()]
assert numbers == [f'{number:02}' for number in range(1, 25)]
print('PASS chapter numbers 01-24')
PY
```

非浏览器渲染可使用以下命令。依赖和预览仅写入临时目录，不进入教材：

```sh
npm install --prefix /tmp/leanagentbook-svg-preview --no-audit --no-fund @resvg/resvg-js@2.6.2
node <<'JS'
const fs = require('fs');
const { Resvg } = require('/tmp/leanagentbook-svg-preview/node_modules/@resvg/resvg-js');
const names = ['cover', 'learning-map', ...['foundation', 'model', 'retrieval',
  'production', 'robotics', 'architecture'].map(name => 'icons/' + name)];
for (const name of names) {
  const source = fs.readFileSync('diagrams/' + name + '.svg');
  const image = new Resvg(source, { font: { loadSystemFonts: true } }).render();
  const output = '/tmp/leanagentbook-svg-preview/' + name.replace('icons/', '') + '-full.png';
  fs.writeFileSync(output, image.asPng());
  console.log(name, image.width, image.height);
}
JS
```

限制：系统字体不同会改变字形和宽度；没有检查全部操作系统和阅读器。macOS Quick Look 本次生成的宽图缩略图裁掉了右侧，因此没有以其缩略图作为完整画面的验收依据。最终视觉偏好由读者确认。

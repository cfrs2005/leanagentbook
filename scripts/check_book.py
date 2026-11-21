"""Validate local course references and portable, script-free SVG assets."""
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
errors = []
checked_links = 0
files = sorted(p for p in ROOT.rglob('*.md') if not {'.git', '.venv', 'build'}.intersection(p.relative_to(ROOT).parts))
for path in files:
    content = path.read_text(encoding='utf-8')
    # Fenced examples are illustrative, not document navigation.
    prose = re.sub(r'```.*?```', '', content, flags=re.S)
    links = re.findall(r'!?\[[^\]]*\]\(([^\s)]+)(?:\s+"[^"]*")?\)', prose)
    links += re.findall(r'(?:src|href)=["\']([^"\']+)["\']', prose)
    for link in links:
        parsed = urlsplit(link.strip('<>'))
        if parsed.scheme or parsed.netloc or not parsed.path:
            continue
        target = (path.parent / unquote(parsed.path)).resolve()
        checked_links += 1
        if not target.is_relative_to(ROOT) or not target.exists():
            errors.append(f'{path.relative_to(ROOT)}: missing or external local target: {link}')
    if path.parent == ROOT / 'chapters':
        for marker in ('目标', '验收', '参考'):
            if marker not in content:
                errors.append(f'{path.relative_to(ROOT)}: missing chapter marker {marker}')
        if not re.search(r'!\[|```mermaid|<img', content):
            errors.append(f'{path.relative_to(ROOT)}: no diagram reference')

svgs = sorted((ROOT / 'diagrams').rglob('*.svg'))
for path in svgs:
    try:
        root = ET.fromstring(path.read_text(encoding='utf-8'))
        tags = {node.tag.rsplit('}', 1)[-1] for node in root.iter()}
        if root.tag.rsplit('}', 1)[-1] != 'svg' or not root.get('viewBox'):
            errors.append(f'{path.relative_to(ROOT)}: expected SVG with viewBox')
        if not {'title', 'desc'}.issubset(tags):
            errors.append(f'{path.relative_to(ROOT)}: expected title and desc')
        if tags & {'script', 'foreignObject'}:
            errors.append(f'{path.relative_to(ROOT)}: active SVG content is forbidden')
        for node in root.iter():
            for key, value in node.attrib.items():
                attr = key.rsplit('}', 1)[-1].lower()
                if attr.startswith('on') or (attr == 'href' and not value.startswith('#')):
                    errors.append(f'{path.relative_to(ROOT)}: active or external SVG attribute')
        if re.search(r'@import|url\(\s*[\"\']?(?:https?:|//|data:)', path.read_text(), re.I):
            errors.append(f'{path.relative_to(ROOT)}: external SVG resource')
    except ET.ParseError as exc:
        errors.append(f'{path.relative_to(ROOT)}: invalid XML: {exc}')

for required in ('README.md', 'ROADMAP.md', 'LICENSE', 'chapters/00-start-here.md',
                 'chapters/02-agent-loop.md', 'chapters/03-runtime-harness.md',
                 'chapters/24-robot-diagnosis.md', 'diagrams/cover.svg', 'diagrams/learning-map.svg'):
    if not (ROOT / required).is_file():
        errors.append(f'Missing required file: {required}')
if errors:
    print('\n'.join(errors), file=sys.stderr)
    sys.exit(1)
print(f'PASS: {len(files)} Markdown files, {checked_links} local links, {len(svgs)} SVGs')
print('Scope: local paths and SVG structure; not external links, rendering, or technical accuracy.')

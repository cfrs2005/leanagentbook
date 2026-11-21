"""Stage only public course sources for MkDocs; keep the repository canonical."""
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'build' / 'docs'
if DEST.exists():
    shutil.rmtree(DEST)
DEST.mkdir(parents=True)
for name in ['chapters', 'diagrams', 'labs', 'references', 'ai-agent-engineering-book-kit']:
    shutil.copytree(ROOT / name, DEST / name,
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
for name in ['README.md', 'ROADMAP.md', 'CONTRIBUTING.md', 'CHANGELOG.md', 'VALIDATION.md', 'LICENSE']:
    shutil.copy2(ROOT / name, DEST / name)
# MkDocs uses index.md for the homepage. Fix root links without changing nested READMEs.
(DEST / 'README.md').rename(DEST / 'index.md')
for path in DEST.rglob('*.md'):
    text = path.read_text(encoding='utf-8')
    if path.parent == DEST:
        text = text.replace('](README.md)', '](index.md)')
    elif path.parent == DEST / 'chapters' or path.parent == DEST / 'references':
        text = text.replace('](../README.md)', '](../index.md)')
    path.write_text(text, encoding='utf-8')
(DEST / 'stylesheets').mkdir()
shutil.copy2(ROOT / 'website' / 'book.css', DEST / 'stylesheets' / 'book.css')
print('Staged public course sources in build/docs')

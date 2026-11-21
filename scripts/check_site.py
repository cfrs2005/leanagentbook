"""Check generated HTML navigation, local assets, and search coverage."""
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit
import json

ROOT = Path(__file__).resolve().parents[1] / 'build' / 'site'


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.paths = []

    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if key in ('href', 'src') and value:
                self.paths.append(value)


errors = []
count = 0
pages = list(ROOT.rglob('*.html'))
assert pages, 'No generated HTML found; build the site first'
for page in pages:
    parser = Links()
    parser.feed(page.read_text())
    for value in parser.paths:
        url = urlsplit(value)
        if url.scheme or url.netloc or not url.path:
            continue
        raw = unquote(url.path)
        if raw.startswith('/'):
            # The GitHub project site is hosted below this base path.
            if not raw.startswith('/leanagentbook/'):
                continue
            target = ROOT / raw.removeprefix('/leanagentbook/')
        else:
            target = page.parent / raw
        target = target.resolve()
        if target.is_dir():
            target /= 'index.html'
        count += 1
        if not target.is_relative_to(ROOT.resolve()) or not target.is_file():
            errors.append(f'{page.relative_to(ROOT)}: broken local target {value}')
index = json.loads((ROOT / 'search/search_index.json').read_text())
for chapter in (ROOT / 'chapters').iterdir():
    if chapter.is_dir() and (chapter / 'index.html').exists():
        location = chapter.relative_to(ROOT).as_posix() + '/'
        if not any(doc['location'].startswith(location) for doc in index['docs']):
            errors.append(f'Search is missing {location}')
if errors:
    raise SystemExit('\n'.join(errors))
print(f'PASS: {len(pages)} HTML pages, {count} local links/assets, chapter search coverage')

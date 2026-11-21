"""Local, extractive RAG teaching pipeline. No model or network calls."""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import hashlib
from html.parser import HTMLParser
import json
from io import BytesIO
import math
from pathlib import Path
import re
import sqlite3
import uuid

PIPELINE_VERSION = 'rag-lab-v1'


@dataclass(frozen=True)
class Block:
    location: str
    text: str


class TextHTML(HTMLParser):
    """Extract visible text with source line anchors, not rendered layout."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocks = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in {'script', 'style', 'noscript', 'template'}:
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in {'script', 'style', 'noscript', 'template'}:
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data):
        if not self.hidden and data.strip():
            self.blocks.append(Block(f'html-line:{self.getpos()[0]}', data.strip()))


def parse(path: Path, raw: bytes | None = None) -> list[Block]:
    raw = path.read_bytes() if raw is None else raw
    suffix = path.suffix.lower()
    if suffix == '.pdf':
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise ValueError('PDF requires the isolated requirements-pdf.txt environment') from exc
        reader = PdfReader(BytesIO(raw))
        if reader.is_encrypted:
            raise ValueError('Encrypted PDF is unsupported')
        blocks = []
        for number, page in enumerate(reader.pages, 1):
            value = (page.extract_text() or '').strip()
            if not value:
                raise ValueError(f'PDF page {number} has no text: OCR is required')
            blocks.append(Block(f'pdf-page:{number}', value))
    elif suffix in {'.html', '.htm'}:
        parser = TextHTML()
        parser.feed(raw.decode('utf-8'))
        parser.close()
        blocks = parser.blocks
    elif suffix in {'.md', '.markdown'}:
        # Preserve Markdown table rows and fenced code as source text.
        lines = raw.decode('utf-8').splitlines()
        blocks, pending, start = [], [], 1
        for number, line in enumerate(lines + [''], 1):
            if line.strip():
                if not pending:
                    start = number
                pending.append(line)
            elif pending:
                blocks.append(Block(f'md-lines:{start}-{number - 1}', '\n'.join(pending)))
                pending = []
    else:
        raise ValueError(f'Unsupported format: {suffix}')
    if not blocks:
        raise ValueError('Empty document')
    return blocks


def terms(text: str) -> list[str]:
    """Latin words plus CJK bigrams; this is not a semantic embedding."""
    output = re.findall(r'[a-z0-9]+', text.lower())
    for run in re.findall(r'[\u3400-\u9fff]+', text):
        output.extend(run[i:i + 2] for i in range(len(run) - 1))
        if len(run) == 1:
            output.append(run)
    return output


def windows(text: str, size: int, overlap: int):
    if size <= 0 or not 0 <= overlap < size:
        raise ValueError('Require size > 0 and 0 <= overlap < size')
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        yield start, end, text[start:end]
        if end == len(text):
            break
        start = end - overlap


class Store:
    def __init__(self, db: str | Path):
        self.db = sqlite3.connect(db)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA foreign_keys = ON')
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS state (id INTEGER PRIMARY KEY, epoch INTEGER NOT NULL);
        INSERT OR IGNORE INTO state VALUES (1, 0);
        CREATE TABLE IF NOT EXISTS versions (doc_id TEXT PRIMARY KEY, version INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS documents (
          doc_id TEXT PRIMARY KEY, version INTEGER NOT NULL, fingerprint TEXT NOT NULL,
          source TEXT NOT NULL, role TEXT NOT NULL, tag TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS parents (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          doc_id TEXT NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
          location TEXT NOT NULL, start INTEGER NOT NULL, end INTEGER NOT NULL, text TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS children (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          parent_id INTEGER NOT NULL REFERENCES parents(id) ON DELETE CASCADE,
          start INTEGER NOT NULL, end INTEGER NOT NULL, text TEXT NOT NULL, length INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS postings (
          term TEXT NOT NULL, child_id INTEGER NOT NULL REFERENCES children(id) ON DELETE CASCADE,
          frequency INTEGER NOT NULL, PRIMARY KEY (term, child_id));
        CREATE TABLE IF NOT EXISTS contexts (
          handle TEXT PRIMARY KEY, epoch INTEGER NOT NULL, principal TEXT NOT NULL,
          child_ids TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS parent_doc ON parents(doc_id);
        CREATE INDEX IF NOT EXISTS child_parent ON children(parent_id);
        CREATE INDEX IF NOT EXISTS posting_child ON postings(child_id);
        ''')

    def close(self):
        self.db.close()

    def _invalidate(self):
        self.db.execute('UPDATE state SET epoch = epoch + 1 WHERE id = 1')
        self.db.execute('DELETE FROM contexts')

    def ingest(self, path: Path, doc_id: str, role='public', tag='general',
               parent_size=600, child_size=180, overlap=40):
        if not doc_id or not role:
            raise ValueError('Document ID and role must be nonempty')
        if not 0 <= overlap < child_size <= parent_size:
            raise ValueError('Require 0 <= overlap < child_size <= parent_size')
        raw = path.read_bytes()
        fingerprint = hashlib.sha256(raw + json.dumps(
            [PIPELINE_VERSION, role, tag, str(path), parent_size, child_size, overlap]
        ).encode()).hexdigest()
        # Parse before deleting active content: failed updates preserve the last good version.
        blocks = parse(path, raw)
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            previous = self.db.execute('SELECT * FROM documents WHERE doc_id=?', (doc_id,)).fetchone()
            if previous and previous['fingerprint'] == fingerprint:
                return {'status': 'unchanged', 'version': previous['version']}
            old = self.db.execute('SELECT version FROM versions WHERE doc_id=?', (doc_id,)).fetchone()
            version = old['version'] + 1 if old else 1
            self.db.execute('INSERT OR REPLACE INTO versions VALUES (?,?)', (doc_id, version))
            self.db.execute('DELETE FROM documents WHERE doc_id=?', (doc_id,))
            self.db.execute('INSERT INTO documents VALUES (?,?,?,?,?,?)',
                            (doc_id, version, fingerprint, str(path), role, tag))
            for block in blocks:
                for start, end, parent in windows(block.text, parent_size, 0):
                    parent_id = self.db.execute(
                        'INSERT INTO parents(doc_id,location,start,end,text) VALUES (?,?,?,?,?)',
                        (doc_id, block.location, start, end, parent)).lastrowid
                    for left, right, child in windows(parent, child_size, overlap):
                        counts = Counter(terms(child))
                        child_id = self.db.execute(
                            'INSERT INTO children(parent_id,start,end,text,length) VALUES (?,?,?,?,?)',
                            (parent_id, left, right, child, sum(counts.values()))).lastrowid
                        self.db.executemany('INSERT INTO postings VALUES (?,?,?)',
                                            [(term, child_id, count) for term, count in counts.items()])
            self._invalidate()
        return {'status': 'indexed', 'version': version}

    def delete(self, doc_id: str):
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            count = self.db.execute('DELETE FROM documents WHERE doc_id=?', (doc_id,)).rowcount
            self._invalidate()
        return count

    def search(self, query: str, principal='public', tag=None, k=3):
        """BM25 over authorized children; returned ranks deduplicate parent IDs."""
        if not 1 <= k <= 100:
            raise ValueError('k must be in [1,100]')
        rows = self.db.execute('''
          SELECT c.*, p.doc_id, d.version FROM children c
          JOIN parents p ON p.id=c.parent_id JOIN documents d ON d.doc_id=p.doc_id
          WHERE (d.role='public' OR d.role=?) AND (? IS NULL OR d.tag=?)
          ORDER BY c.id''', (principal, tag, tag)).fetchall()
        if not rows or not terms(query):
            return []
        ids = {row['id'] for row in rows}
        scores = Counter()
        average = sum(row['length'] for row in rows) / len(rows) or 1
        lengths = {row['id']: row['length'] for row in rows}
        for term in set(terms(query)):
            hits = [row for row in self.db.execute('SELECT * FROM postings WHERE term=?', (term,))
                    if row['child_id'] in ids]
            idf = math.log(1 + (len(rows) - len(hits) + 0.5) / (len(hits) + 0.5))
            for hit in hits:
                child_id, tf = hit['child_id'], hit['frequency']
                scores[child_id] += idf * tf * 2.2 / (tf + 1.2 * (0.25 + 0.75 * lengths[child_id] / average))
        ranked, seen = [], set()
        for row in sorted(rows, key=lambda row: (-scores[row['id']], row['id'])):
            if scores[row['id']] <= 0 or row['parent_id'] in seen:
                continue
            seen.add(row['parent_id'])
            ranked.append({'child_id': row['id'], 'doc_id': row['doc_id'],
                           'version': row['version'], 'score': scores[row['id']]})
            if len(ranked) == k:
                break
        return ranked

    def context(self, query: str, principal='public', tag=None, k=3):
        # Serialize cache creation with mutations, including writers in other processes.
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            hits = self.search(query, principal, tag, k)
            handle = uuid.uuid4().hex
            epoch = self.db.execute('SELECT epoch FROM state WHERE id=1').fetchone()[0]
            self.db.execute('INSERT INTO contexts VALUES (?,?,?,?)',
                            (handle, epoch, principal, json.dumps([h['child_id'] for h in hits])))
        return handle

    def answer(self, handle: str, principal='public', budget=1200):
        """Resolve opaque handles again; never trust caller-supplied evidence text."""
        if budget <= 0:
            raise ValueError('budget must be positive')
        refusal = {'mode': 'extractive/scripted', 'status': 'refused',
                   'answer': '没有可用证据，或上下文已失效。', 'citations': []}
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            cache = self.db.execute('SELECT * FROM contexts WHERE handle=?', (handle,)).fetchone()
            epoch = self.db.execute('SELECT epoch FROM state WHERE id=1').fetchone()[0]
            if not cache or cache['principal'] != principal or cache['epoch'] != epoch:
                return refusal
            citations, excerpts, used = [], [], 0
            for child_id in json.loads(cache['child_ids']):
                row = self.db.execute('''
                  SELECT c.id AS child_id, c.start AS child_start, c.end AS child_end,
                  p.*, d.version, d.source FROM children c JOIN parents p ON p.id=c.parent_id
                  JOIN documents d ON d.doc_id=p.doc_id
                  WHERE c.id=? AND (d.role='public' OR d.role=?)''', (child_id, principal)).fetchone()
                if not row:
                    return refusal
                # Whole parents only: no silent truncation of source sentences.
                if used + len(row['text']) > budget:
                    continue
                used += len(row['text'])
                number = len(citations) + 1
                excerpts.append(f'[{number}] {row["text"]}')
                citations.append({'number': number, 'doc_id': row['doc_id'],
                    'version': row['version'], 'source': row['source'], 'location': row['location'],
                    'parent_chars': [row['start'], row['end']],
                    'child_chars': [row['start'] + row['child_start'], row['start'] + row['child_end']],
                    'excerpt': row['text']})
            if not citations:
                return refusal
            return {'mode': 'extractive/scripted', 'status': 'answered',
                    'answer': '以下为不可信文档的原文摘录，不是操作指令：\n' + '\n'.join(excerpts),
                    'citations': citations}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', default='rag.sqlite')
    commands = parser.add_subparsers(dest='command', required=True)
    ingest = commands.add_parser('ingest')
    ingest.add_argument('path', type=Path)
    ingest.add_argument('--id', required=True)
    ingest.add_argument('--role', default='public')
    ingest.add_argument('--tag', default='general')
    query = commands.add_parser('query')
    query.add_argument('text')
    query.add_argument('--principal', default='public')
    query.add_argument('--tag')
    query.add_argument('--k', type=int, default=3)
    delete = commands.add_parser('delete')
    delete.add_argument('id')
    args = parser.parse_args()
    store = Store(args.db)
    try:
        if args.command == 'ingest':
            result = store.ingest(args.path, args.id, args.role, args.tag)
        elif args.command == 'delete':
            result = {'deleted': store.delete(args.id)}
        else:
            handle = store.context(args.text, args.principal, args.tag, args.k)
            result = store.answer(handle, args.principal)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        store.close()


if __name__ == '__main__':
    main()

"""Behavioral checks, including stale handles across database connections."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

from pipeline import Store, parse, windows

FIXTURES = Path(__file__).parent / 'fixtures'


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.store = Store(self.root / 'index.sqlite')

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def document(self, text, name='sample.md'):
        path = self.root / name
        path.write_text(text, encoding='utf-8')
        return path

    def test_markdown_citation_and_parent_expansion(self):
        path = self.document('Intro.\n\nneedle ' + 'explanation ' * 30)
        self.store.ingest(path, 'guide', child_size=50, overlap=10)
        result = self.store.answer(self.store.context('needle'))
        citation = result['citations'][0]
        self.assertEqual(citation['location'], 'md-lines:3-3')
        self.assertEqual(citation['source'], str(path))
        self.assertEqual(citation['version'], 1)
        self.assertGreater(len(citation['excerpt']), 50)
        self.assertEqual(citation['child_chars'], [0, 50])
        self.assertEqual(len(self.store.search('explanation')), 1)

    def test_parser_uses_the_fingerprinted_snapshot(self):
        path = self.document('Originalcanary')
        snapshot = path.read_bytes()
        path.write_text('Changedcanary', encoding='utf-8')
        self.assertEqual(parse(path, snapshot)[0].text, 'Originalcanary')

    def test_windows_boundaries(self):
        chunks = list(windows('abcdefghij', 6, 2))
        self.assertEqual(chunks, [(0, 6, 'abcdef'), (4, 10, 'efghij')])
        with self.assertRaises(ValueError):
            list(windows('x', 2, 2))

    def test_html_visible_text_and_source_line(self):
        self.store.ingest(FIXTURES / 'network.html', 'network')
        self.assertFalse(self.store.search('NeverIndexScriptSecret'))
        result = self.store.answer(self.store.context('timeout'))
        self.assertEqual(result['citations'][0]['location'], 'html-line:5')

    def test_chinese_table(self):
        self.store.ingest(FIXTURES / 'battery.md', 'battery')
        answer = self.store.answer(self.store.context('接头松动'))
        self.assertIn('每月', answer['answer'])
        self.assertIn('| 检查项 | 周期 |', answer['answer'])

    def test_update_replaces_index_and_cache(self):
        path = self.document('Oldcanary alpha')
        self.store.ingest(path, 'guide')
        stale = self.store.context('Oldcanary')
        path.write_text('Newcanary beta', encoding='utf-8')
        self.assertEqual(self.store.ingest(path, 'guide')['version'], 2)
        self.assertFalse(self.store.search('Oldcanary'))
        self.assertEqual(self.store.answer(stale)['status'], 'refused')
        answer = self.store.answer(self.store.context('Newcanary'))
        self.assertEqual(answer['citations'][0]['version'], 2)
        self.assertNotIn('Oldcanary', ' '.join(row[0] for row in
            self.store.db.execute('SELECT text FROM parents')))

    def test_identical_input_is_noop(self):
        path = self.document('Samecanary')
        self.store.ingest(path, 'guide')
        handle = self.store.context('Samecanary')
        self.assertEqual(self.store.ingest(path, 'guide'), {'status': 'unchanged', 'version': 1})
        self.assertEqual(self.store.answer(handle)['status'], 'answered')

    def test_delete_cascades_and_invalidates_other_connection(self):
        self.store.ingest(self.document('Deletecanary'), 'guide')
        handle = self.store.context('Deletecanary')
        other = Store(self.root / 'index.sqlite')
        try:
            self.assertEqual(other.delete('guide'), 1)
        finally:
            other.close()
        self.assertFalse(self.store.search('Deletecanary'))
        self.assertEqual(self.store.answer(handle)['status'], 'refused')
        for table in ('documents', 'parents', 'children', 'postings', 'contexts'):
            self.assertEqual(self.store.db.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0], 0)
        self.assertEqual(self.store.ingest(self.document('Recreated'), 'guide')['version'], 2)

    def test_acl_filter_before_ranking_and_handle_recheck(self):
        self.store.ingest(self.document('Privatecanary482'), 'private', role='technician')
        self.assertFalse(self.store.search('Privatecanary482'))
        handle = self.store.context('Privatecanary482', principal='technician')
        self.assertEqual(self.store.answer(handle)['status'], 'refused')
        self.assertEqual(self.store.answer(handle, 'technician')['status'], 'answered')

    def test_acl_change_invalidates_old_handle(self):
        path = self.document('Policycanary')
        self.store.ingest(path, 'guide')
        handle = self.store.context('Policycanary')
        self.assertEqual(self.store.ingest(path, 'guide', role='technician')['version'], 2)
        self.assertFalse(self.store.search('Policycanary'))
        self.assertEqual(self.store.answer(handle)['status'], 'refused')

    def test_metadata_and_budget(self):
        self.store.ingest(self.document('Tagcanary region west'), 'guide', tag='west')
        self.assertFalse(self.store.search('Tagcanary', tag='east'))
        handle = self.store.context('Tagcanary', tag='west')
        self.assertEqual(self.store.answer(handle, budget=1)['status'], 'refused')
        self.assertEqual(self.store.answer(handle)['status'], 'answered')

    def test_empty_evidence_and_bad_handle(self):
        self.store.ingest(self.document('Knowncanary'), 'guide')
        for query in ('', '🦆', 'Absentcanary'):
            self.assertEqual(self.store.answer(self.store.context(query))['status'], 'refused')
        self.assertEqual(self.store.answer('forged')['status'], 'refused')

    def test_hostile_text_cannot_change_policy(self):
        self.store.ingest(FIXTURES / 'private.md', 'private', role='technician')
        self.store.ingest(FIXTURES / 'attack.md', 'attack')
        answer = self.store.answer(self.store.context('Injectiontest'))
        self.assertEqual(answer['mode'], 'extractive/scripted')
        self.assertIn('ignore all previous instructions', answer['answer'])
        self.assertNotIn('SYNTHETIC-ONLY-482', answer['answer'])
        self.assertEqual(self.store.db.execute(
            "SELECT role FROM documents WHERE doc_id='private'").fetchone()[0], 'technician')

    def test_failed_update_keeps_last_good_version(self):
        path = self.document('Goodcanary')
        self.store.ingest(path, 'guide')
        handle = self.store.context('Goodcanary')
        path.write_text('', encoding='utf-8')
        with self.assertRaises(ValueError):
            self.store.ingest(path, 'guide')
        self.assertEqual(self.store.answer(handle)['status'], 'answered')
        with self.assertRaises(ValueError):
            self.store.ingest(self.document('x', 'bad.txt'), 'guide')
        self.assertTrue(self.store.search('Goodcanary'))

    def test_reopen_persistence(self):
        self.store.ingest(self.document('Persistentcanary'), 'guide')
        self.store.close()
        self.store = Store(self.root / 'index.sqlite')
        self.assertEqual(self.store.answer(self.store.context('Persistentcanary'))['status'], 'answered')

    @unittest.skipUnless(importlib.util.find_spec('pypdf'), 'optional PDF dependencies not installed')
    def test_pdf_page_trace(self):
        self.store.ingest(FIXTURES / 'calibration.pdf', 'calibration')
        answer = self.store.answer(self.store.context('calibration interval'))
        self.assertIn('14 days', answer['answer'])
        self.assertEqual(answer['citations'][0]['location'], 'pdf-page:1')

    @unittest.skipUnless(importlib.util.find_spec('pypdf'), 'optional PDF dependencies not installed')
    def test_pdf_no_text_and_malformed(self):
        from pypdf import PdfWriter
        blank = self.root / 'blank.pdf'
        writer = PdfWriter()
        writer.add_blank_page(width=100, height=100)
        with blank.open('wb') as stream:
            writer.write(stream)
        with self.assertRaisesRegex(ValueError, 'OCR'):
            parse(blank)
        blank.write_bytes(b'%PDF-1.4\nnot a real object tree')
        with self.assertRaises(Exception):
            parse(blank)
        self.assertEqual(self.store.db.execute('SELECT COUNT(*) FROM documents').fetchone()[0], 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)

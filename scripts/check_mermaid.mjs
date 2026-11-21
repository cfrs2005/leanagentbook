/** Parse every Mermaid fence using an isolated, pinned Mermaid installation. */
import fs from 'node:fs/promises';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { createRequire } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';

const args = process.argv.slice(2);
const option = (name, fallback) => {
  const index = args.indexOf(name);
  if (index < 0) return fallback;
  if (!args[index + 1]) throw new Error(`Missing value for ${name}`);
  return args[index + 1];
};
const root = path.resolve(option('--root', path.join(path.dirname(fileURLToPath(import.meta.url)), '..')));
const environment = path.resolve(option('--env', '/tmp/leanagentbook-mermaid-11.4.1'));
const output = option('--out', null);
const require = createRequire(path.join(environment, 'package.json'));
const { JSDOM } = require('jsdom');
const dom = new JSDOM('<!doctype html><html><body></body></html>');
globalThis.window = dom.window;
globalThis.document = dom.window.document;
const { default: mermaid } = await import(pathToFileURL(require.resolve('mermaid')).href);
const packageInfo = JSON.parse(await fs.readFile(path.join(environment, 'node_modules/mermaid/package.json'), 'utf8'));
const domInfo = JSON.parse(await fs.readFile(path.join(environment, 'node_modules/jsdom/package.json'), 'utf8'));
if (packageInfo.version !== '11.4.1' || domInfo.version !== '26.0.0') throw new Error('Expected mermaid 11.4.1 and jsdom 26.0.0');
mermaid.initialize({ startOnLoad: false, securityLevel: 'strict' });

// A positive and negative control prove that actual parser failures propagate.
await mermaid.parse('flowchart LR\n A[Start] --> B[End]');
let rejected = false;
try { await mermaid.parse('flowchart LR\n A[unterminated'); } catch { rejected = true; }
if (!rejected) throw new Error('Parser negative control was not rejected');

const sha = text => createHash('sha256').update(text).digest('hex');
function fences(text) {
  const lines = text.split(/\r?\n/);
  const result = [];
  let active = null;
  for (let index = 0; index < lines.length; index++) {
    const line = lines[index];
    if (active) {
      const close = line.match(/^ {0,3}(`+|~+)\s*$/);
      if (close && close[1][0] === active.char && close[1].length >= active.length) {
        if (active.mermaid) result.push({ fence_line: active.line, source: active.lines.join('\n'), closed: true });
        active = null;
      } else active.lines.push(line);
    } else {
      const open = line.match(/^ {0,3}(`{3,}|~{3,})(.*)$/);
      if (open) active = { char: open[1][0], length: open[1].length, line: index + 1,
                           mermaid: /^mermaid(?:\s|$)/i.test(open[2].trim()), lines: [] };
    }
  }
  if (active?.mermaid) result.push({ fence_line: active.line, source: active.lines.join('\n'), closed: false });
  return result;
}
async function markdownFiles(directory) {
  const result = [];
  for (const item of await fs.readdir(directory, { withFileTypes: true })) {
    const full = path.join(directory, item.name);
    if (item.isDirectory()) result.push(...await markdownFiles(full));
    else if (item.isFile() && item.name.endsWith('.md')) result.push(full);
  }
  return result.sort();
}
const files = await markdownFiles(path.join(root, 'chapters'));
const report = { mermaid: packageInfo.version, jsdom: domInfo.version, node: process.version,
  mode: 'mermaid.parse only; JSDOM provides an in-memory DOM; no browser, page visit or SVG layout',
  parser_controls: { valid_accepted: true, invalid_rejected: rejected },
  snapshot: [], blocks: [], changed_during_check: [] };
for (const filename of files) {
  const text = await fs.readFile(filename, 'utf8');
  const relative = path.relative(root, filename);
  report.snapshot.push({ file: relative, sha256: sha(text) });
  for (const block of fences(text)) {
    const entry = { file: relative, fence_line: block.fence_line, source_sha256: sha(block.source) };
    try {
      if (!block.closed) throw new Error('Unclosed Mermaid Markdown fence');
      if (!block.source.trim()) throw new Error('Empty Mermaid diagram');
      const parsed = await mermaid.parse(block.source);
      entry.status = 'pass';
      entry.diagram_type = parsed.diagramType;
    } catch (error) {
      entry.status = 'fail';
      entry.error = String(error.message ?? error).replaceAll(root, '<repository>');
      entry.parser_line = error.hash?.loc?.first_line ?? null;
      console.error(`FAIL ${relative}:${block.fence_line}\n${entry.error}`);
    }
    report.blocks.push(entry);
  }
}
for (const item of report.snapshot) {
  if (sha(await fs.readFile(path.join(root, item.file), 'utf8')) !== item.sha256) report.changed_during_check.push(item.file);
}
const finalFiles = await markdownFiles(path.join(root, 'chapters'));
if (JSON.stringify(files) !== JSON.stringify(finalFiles)) report.changed_during_check.push('chapter file list changed');
report.summary = { chapter_files: files.length, blocks: report.blocks.length,
  passed: report.blocks.filter(item => item.status === 'pass').length,
  failed: report.blocks.filter(item => item.status === 'fail').length,
  stable_snapshot: report.changed_during_check.length === 0 };
if (output) await fs.writeFile(path.resolve(output), JSON.stringify(report, null, 2) + '\n');
console.log(JSON.stringify(report.summary, null, 2));
dom.window.close();
process.exitCode = report.summary.failed || !report.summary.stable_snapshot || !report.summary.blocks ? 1 : 0;

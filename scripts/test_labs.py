"""Run each lab's unittest suite in its own process to avoid import collisions."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
suites = sorted({path.parent for path in (ROOT / 'labs').rglob('test_*.py')})
if not suites:
    raise SystemExit('No lab tests found')
for suite in suites:
    print(f'=== {suite.relative_to(ROOT)} ===', flush=True)
    subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s',
                    str(suite), '-p', 'test_*.py'], cwd=ROOT, check=True)
print(f'PASS: {len(suites)} lab suites')

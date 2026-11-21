"""Render actual token-weighted losses with editable SVG text."""
import argparse
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

parser = argparse.ArgumentParser()
parser.add_argument('--report', default='labs/training_post_training/results/report.json')
parser.add_argument('--output', default='output/training_post_training/curve')
args = parser.parse_args()
report = json.loads(Path(args.report).read_text())
out = Path(args.output)
if 'results' in out.parts:
    raise ValueError('Use output/ or /tmp; published artifacts are read-only')
out.parent.mkdir(parents=True,exist_ok=True)
plt.rcParams['svg.fonttype']='none'
fig,ax=plt.subplots(figsize=(8,4.4),layout='constrained')
for key,label in [('train_loss','Train (eval mode)'),('dev_loss','Dev (selection only)')]:
    ax.plot([r['epoch'] for r in report['curve']], [r[key] for r in report['curve']],marker='o',label=label)
ax.axvline(report['selection']['best_epoch'],linestyle='--',color='#888888',label='Selected epoch')
ax.set(xlabel='Epoch (0 = base model)',ylabel='Token-weighted cross-entropy', title='Real CPU LoRA SFT: FLAN-T5-small')
ax.grid(alpha=.2)
ax.legend()
fig.savefig(out.with_suffix('.svg'),metadata={'Title':'Training and validation loss','Description':'Measured epoch losses; test data are not used for selection.'})
fig.savefig(out.with_suffix('.png'),dpi=160)

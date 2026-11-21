"""Render recorded quality/cost trade-offs; requires matplotlib 3.10.1."""
import json
import os
from pathlib import Path
import xml.etree.ElementTree as ET

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager

ROOT = Path(__file__).resolve().parent
font_path = Path(os.environ.get('BOOK_PLOT_FONT', '/System/Library/Fonts/Supplemental/Arial Unicode.ttf'))
if not font_path.is_file():
    raise SystemExit('Set BOOK_PLOT_FONT to an installed Chinese font file')
font_manager.fontManager.addfont(str(font_path))
font_name = font_manager.FontProperties(fname=str(font_path)).get_name()
plt.rcParams.update({'svg.fonttype': 'none', 'font.family': font_name,
                     'axes.unicode_minus': False, 'font.size': 11})
rows = json.loads((ROOT / 'cold-results.json').read_text())['rows']
selected = [('small', 16, 'small', '#31564b'), ('base', 16, 'base', '#a45135'),
            ('cascade', 16, 'cascade', '#787160'), ('rules', 24, 'rules-24', '#4c7fa1')]
fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), sharey=True, layout='constrained')
fig.set_facecolor('#f8f5ee')
for ax, split, title in zip(axes, ('dev', 'test'), ('开发集 · 8 题', '测试集 · 16 题')):
    ax.set_facecolor('#fffdf8')
    for index, (policy, threshold, label, color) in enumerate(selected):
        row = next(r for r in rows if r['split'] == split and r['policy'] == policy
                   and r['threshold_words'] == threshold)
        x, y = row['cost_credits'] / row['requests'], row['accuracy'] * 100
        ax.scatter([x], [y], s=75, color=color, zorder=3)
        ax.annotate(label, (x, y), xytext=(0, 12 if index % 2 else -20),
                    textcoords='offset points', ha='center', color=color)
    ax.set(title=title, xlabel='每次请求平均积分（教学假设）', xlim=(0, .2), ylim=(0, 100))
    ax.grid(alpha=.2)
axes[0].set_ylabel('正确率 / %')
fig.suptitle('质量与成本：本次测试集没有出现质量收益', fontsize=17)
target = ROOT.parents[1] / 'diagrams' / 'routing-quality-cost.svg'
fig.savefig(target, metadata={'Date': None})
plt.close(fig)
ET.register_namespace('', 'http://www.w3.org/2000/svg')
ET.register_namespace('xlink', 'http://www.w3.org/1999/xlink')
tree = ET.parse(target)
root = tree.getroot()
ET.SubElement(root, '{http://www.w3.org/2000/svg}title').text = '模型路由质量与成本散点图'
ET.SubElement(root, '{http://www.w3.org/2000/svg}desc').text = (
    '开发集与测试集分别展示四种策略。测试集正确率均为37.5%，'
    'small每次请求平均积分最低。本图不是总体质量收益证明。')
tree.write(target, encoding='unicode')
print(target)

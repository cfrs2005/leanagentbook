"""Plot measured model scores and synthetic telemetry from the saved report."""
import csv
import json
import os
from pathlib import Path
import xml.etree.ElementTree as ET

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager

ROOT = Path(__file__).resolve().parent
font = Path(os.environ.get('BOOK_PLOT_FONT', '/System/Library/Fonts/Supplemental/Arial Unicode.ttf'))
if not font.exists():
    raise SystemExit('Set BOOK_PLOT_FONT to a Chinese font file')
font_manager.fontManager.addfont(str(font))
plt.rcParams.update({'font.family': font_manager.FontProperties(fname=str(font)).get_name(),
                     'svg.fonttype': 'none', 'axes.unicode_minus': False, 'font.size': 10})
report = json.loads((ROOT / 'results/report.json').read_text())
with (ROOT / 'results/telemetry.csv').open() as handle:
    rows = [r for r in csv.DictReader(handle) if int(r['t']) >= 8400]
test = [r for r in report['windows'] if r['split'] == 'test']
fig, axes = plt.subplots(6, 1, figsize=(12, 11), sharex=True, layout='constrained')
fig.set_facecolor('#f8f5ee')
for ax, channel, label in zip(axes, ['current_a', 'temperature_c', 'speed_rpm'], ['电流 / A', '温度 / °C', '转速 / rpm']):
    ax.plot([int(r['t']) for r in rows], [float(r[channel]) if r[channel] else float('nan') for r in rows],
            color='#31564b', linewidth=.7)
    ax.set_ylabel(label)
for ax, name in zip(axes[3:], ['z_score', 'isolation_forest', 'xgboost']):
    ax.plot([r['end'] for r in test], report['scores'][name]['test'], color='#31564b', linewidth=1)
    ax.axhline(report['results'][name]['threshold'], color='#a45135', linestyle='--', label='开发集阈值')
    ax.set_ylabel(name)
    ax.legend(loc='upper right', fontsize=8)
axes[3].set_yscale('symlog', linthresh=1)
axes[3].set_ylim(bottom=0)
axes[3].set_ylabel('z_score（对数刻度）')
for ax in axes:
    ax.set_facecolor('#fffdf8')
    for event in report['events']:
        if event['onset'] >= 8400:
            ax.axvspan(event['onset'] - 40, event['onset'], color='#d9b779', alpha=.16)
            ax.axvspan(event['onset'], event['end'], color='#a45135', alpha=.18)
    ax.grid(alpha=.15)
axes[-1].set_xlabel('合成时间 / 秒；淡黄为预兆，浅红为故障标签区间')
fig.suptitle('时间序列实验：冻结阈值后查看完整测试时段', fontsize=17)
target = ROOT.parents[1] / 'diagrams/time-series-results.svg'
fig.savefig(target, metadata={'Date': None})
plt.close(fig)
ET.register_namespace('', 'http://www.w3.org/2000/svg')
ET.register_namespace('xlink', 'http://www.w3.org/1999/xlink')
tree = ET.parse(target)
ET.SubElement(tree.getroot(), '{http://www.w3.org/2000/svg}title').text = '三种异常检测方法的真实分数与合成信号'
ET.SubElement(tree.getroot(), '{http://www.w3.org/2000/svg}desc').text = '完整测试时段，电流温度转速三条曲线与三个模型分数，阈值仅从开发集选择。'
tree.write(target, encoding='unicode')
print(target)

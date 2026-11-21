"""Plot the preserved host power samples without estimating per-model energy."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    font = Path('/System/Library/Fonts/Supplemental/Arial Unicode.ttf')
    if font.exists():
        font_manager.fontManager.addfont(str(font))
        plt.rcParams['font.family'] = 'Arial Unicode MS'
    plt.rcParams['svg.fonttype'] = 'none'
    report = json.loads(args.report.read_text())
    origin = datetime.fromisoformat(report['phases'][0]['samples'][0]['timestamp'])
    fig, ax = plt.subplots(figsize=(12, 4.5), layout='constrained')
    names = {'baseline_before': '无实验推理 / 前', 'float': '浮点推理',
             'int8': 'INT8 推理', 'baseline_after': '无实验推理 / 后'}
    for i, phase in enumerate(report['phases']):
        xs = [(datetime.fromisoformat(s['timestamp'])-origin).total_seconds() for s in phase['samples']]
        ax.axvspan(xs[0], xs[-1], color=['#e4e9e6','#f4dbc9','#d6e5ee','#e4e9e6'][i], alpha=.7)
        for field, label, color in [('cpu_power','系统报告 CPU 功耗','#256951'),('chip_power','系统报告芯片功耗','#ad613b')]:
            ax.plot(xs,[s[field] for s in phase['samples']],label=label if i==0 else None,color=color,marker='.',markersize=4)
        ax.text((xs[0]+xs[-1])/2,1.0,names[phase['phase']],ha='center',fontsize=10)
    ax.set(title='Apple M4：真实系统功耗读数与推理负载',xlabel='从首个采样点开始的时间 / 秒',ylabel='系统报告功耗 / W',ylim=(0,None))
    ax.legend(loc='upper left');ax.grid(axis='y',alpha=.2)
    fig.suptitle('macmon 0.12.0 · 每阶段 20 点 / 500 ms · 后台应用仍运行；不是模型独占功耗',fontsize=11)
    fig.savefig(args.output)
    source=args.output.read_text();pos=source.index('>',source.index('<svg'))+1
    args.output.write_text(source[:pos]+'<title>本机推理期间的系统功耗采样</title><desc>四个阶段的CPU与芯片功耗原始读数，不推断每次推理能耗。</desc>'+source[pos:])


if __name__ == '__main__':
    main()

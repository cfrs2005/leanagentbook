"""Plot measured records; this script is the editable figure source."""
import argparse
from pathlib import Path
from report import summarize


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', default=str(Path(__file__).with_name('results')))
    parser.add_argument('--output', default='labs/inference_serving/output-plot')
    args = parser.parse_args()
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    rows = summarize(Path(args.input))
    plt.rcParams.update({'font.family': 'sans-serif', 'font.size': 11,
                         'svg.fonttype': 'none', 'figure.facecolor': '#F6F1E7',
                         'axes.facecolor': '#FFFCF6', 'text.color': '#22312F'})
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.8), layout='constrained')
    for concurrency, color in [(1, '#316653'), (2, '#B94F2D')]:
        data = [r for r in rows if r['concurrency'] == concurrency]
        x = [i + (concurrency - 1.5) * .35 for i in range(4)]
        axes[0].bar(x, [r['output_tokens_per_s'] for r in data], width=.32,
                    color=color, label=f'HTTP concurrency {concurrency}')
        axes[1].bar(x, [r['ttft_ms_p50'] for r in data], width=.32,
                    color=color, label=f'HTTP concurrency {concurrency}')
        axes[1].scatter(x, [r['ttft_ms_p95'] for r in data], color=color, marker='_', s=120)
    for ax in axes:
        ax.set_xticks(range(4), ['32 / 8', '32 / 24', '128 / 8', '128 / 24'])
        ax.set_xlabel('Actual input / output tokens per request')
        ax.grid(axis='y', alpha=.2)
        ax.set_axisbelow(True)
        ax.spines[['top', 'right']].set_visible(False)
    axes[0].set_ylabel('Total output tokens / wall second')
    axes[0].set_title('Aggregate throughput (not per request)')
    axes[0].legend(fontsize=9)
    axes[1].set_ylabel('Client TTFT (milliseconds)')
    axes[1].set_title('Median TTFT; tick = P95 (= P99 here)')
    fig.suptitle('Real FLAN-T5-small / Apple M4 CPU / FP32 / one generation slot', fontsize=13)
    fig.supxlabel('12 requests per cell; shared host; short closed-loop run; no GPU engine comparison', fontsize=10)
    target = Path(args.output)
    target.mkdir(parents=True, exist_ok=True)
    fig.savefig(target / 'performance.png', dpi=160)
    fig.savefig(target / 'performance.svg', metadata={'Title': 'Measured serving throughput and TTFT',
                                                   'Description': 'CPU experiment; 12 requests per cell; not production tail estimates'})


if __name__ == '__main__':
    main()

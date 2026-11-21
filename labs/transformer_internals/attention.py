"""Transparent CPU attention with synthetic IDs; no pretrained model or tokenizer."""
import argparse
import json
import math
import platform
from pathlib import Path

import torch
from torch import nn

SEED = 17
IDS = [[1, 4, 2, 4, 7, 3]]


def positions(length, width, offset=0):
    pos = torch.arange(offset, offset + length, dtype=torch.float64)[:, None]
    freq = torch.exp(torch.arange(0, width, 2, dtype=torch.float64) * (-math.log(10000) / width))
    result = torch.zeros(length, width, dtype=torch.float64)
    result[:, 0::2] = torch.sin(pos * freq)
    result[:, 1::2] = torch.cos(pos * freq)
    return result


class TinyBlock(nn.Module):
    def __init__(self, width=8, heads=2, vocab=16):
        super().__init__()
        if width <= 0 or heads <= 0 or width % heads or width % 2:
            raise ValueError('Width must be positive, even and divisible by heads')
        self.width, self.heads = width, heads
        self.embedding = nn.Embedding(vocab, width)
        self.qkv = nn.Linear(width, 3 * width, bias=False)
        self.proj = nn.Linear(width, width, bias=False)
        self.norm1 = nn.LayerNorm(width)
        self.norm2 = nn.LayerNorm(width)
        self.ffn = nn.Sequential(nn.Linear(width, 4 * width), nn.ReLU(), nn.Linear(4 * width, width))
        self.double()

    def forward(self, ids, cache=None, causal=True):
        if ids.ndim != 2 or ids.shape[1] == 0:
            raise ValueError('Expected nonempty [batch, time] IDs')
        batch, length = ids.shape
        offset = 0 if cache is None else cache[0].shape[2]
        embedding = self.embedding(ids)
        positional = positions(length, self.width, offset)
        x = embedding + positional
        normalized = self.norm1(x)
        packed = self.qkv(normalized)
        q, k, v = [part.reshape(batch, length, self.heads, self.width // self.heads).transpose(1, 2)
                   for part in packed.chunk(3, dim=-1)]
        if cache is not None:
            k, v = torch.cat((cache[0], k), dim=2), torch.cat((cache[1], v), dim=2)
        scores = q @ k.transpose(-2, -1) / math.sqrt(self.width // self.heads)
        allowed = torch.arange(k.shape[2])[None, :] <= torch.arange(offset, offset + length)[:, None]
        if not causal:
            allowed = torch.ones_like(allowed)
        masked = scores.masked_fill(~allowed, float('-inf'))
        weights = torch.softmax(masked, dim=-1)
        context = weights @ v
        merged = context.transpose(1, 2).contiguous().reshape(batch, length, self.width)
        projected = self.proj(merged)
        residual = x + projected
        norm2 = self.norm2(residual)
        ffn_hidden = self.ffn[1](self.ffn[0](norm2))
        ffn_output = self.ffn[2](ffn_hidden)
        output = residual + ffn_output
        trace = dict(ids=ids, embedding=embedding, positions=positional, x=x,
                     norm1=normalized, packed_qkv=packed, q=q, k=k, v=v, scores=scores,
                     allowed=allowed, weights=weights, context=context, merged=merged,
                     projected=projected, residual=residual, norm2=norm2,
                     ffn_hidden=ffn_hidden, ffn_output=ffn_output, output=output)
        return output, (k, v), trace


def make_model():
    torch.manual_seed(SEED)
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    return TinyBlock().eval()


def verify(model, ids):
    with torch.no_grad():
        full, _, trace = model(ids)
        cache, chunks, steps = None, [], []
        for i in range(ids.shape[1]):
            value, cache, step = model(ids[:, i:i + 1], cache)
            chunks.append(value)
            steps.append({key: list(tensor.shape) for key, tensor in step.items()})
        increment = torch.cat(chunks, dim=1)
        changed = ids.clone()
        changed[:, 3:] = (changed[:, 3:] + 1) % 16
        altered, _, _ = model(changed)
        unmasked, _, _ = model(ids, causal=False)
        unmasked_changed, _, _ = model(changed, causal=False)
        sdpa = torch.nn.functional.scaled_dot_product_attention(
            trace['q'], trace['k'], trace['v'], attn_mask=trace['allowed'], dropout_p=0.0)
        metrics = {
            'kv_max_abs_error': (full - increment).abs().max().item(),
            'prefix_max_abs_error': (full[:, :3] - altered[:, :3]).abs().max().item(),
            'future_weight_max': trace['weights'].triu(1).abs().max().item(),
            'row_sum_max_error': (trace['weights'].sum(-1) - 1).abs().max().item(),
            'sdpa_max_abs_error': (sdpa - trace['context']).abs().max().item(),
            'unmasked_prefix_change': (unmasked[:, :3] - unmasked_changed[:, :3]).abs().max().item(),
        }
        checks = {name: value <= 1e-12 for name, value in metrics.items() if name != 'unmasked_prefix_change'}
        checks['unmasked_negative_control'] = metrics['unmasked_prefix_change'] > 1e-6
        if not all(checks.values()):
            raise AssertionError(metrics)
        return trace, increment, steps, metrics, checks


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=Path('output/transformer_internals'))
    args = parser.parse_args()
    if args.output.resolve().is_relative_to((Path(__file__).parent / 'results').resolve()):
        parser.error('Published results are read-only; choose output/ or /tmp')
    model = make_model()
    trace, increment, steps, metrics, checks = verify(model, torch.tensor(IDS))
    args.output.mkdir(parents=True, exist_ok=True)
    config = dict(seed=SEED, ids=IDS, batch=1, length=6, width=8, heads=2,
                  head_width=4, ffn_width=32, vocab=16, dtype='float64', device='cpu',
                  weights='random, untrained; no language capability', position='sinusoidal',
                  architecture='one pre-norm decoder block; no LM head',
                  torch=torch.__version__, python=platform.python_version())
    for name, value in [('config', config), ('tensors', {k: v.tolist() for k, v in trace.items()}),
                        ('incremental_output', increment.tolist()),
                        ('report', dict(metrics=metrics, checks=checks, decode_shapes=steps))]:
        (args.output / (name + '.json')).write_text(json.dumps(value, indent=2) + '\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(9, 4), constrained_layout=True)
    for head, ax in enumerate(axes):
        data = trace['weights'][0, head].numpy()
        plot = ax.imshow(data, vmin=0, vmax=1, cmap='YlGnBu')
        ax.set(title=f'Head {head} | random weights', xlabel='Key position', ylabel='Query position')
        ax.set_xticks(range(6))
        ax.set_yticks(range(6))
        for row in range(6):
            for col in range(6):
                ax.text(col, row, f'{data[row, col]:.2f}', ha='center', va='center',
                        fontsize=8, color='white' if data[row, col] > .6 else 'black')
    fig.colorbar(plot, ax=axes, label='Attention probability', shrink=.8)
    fig.savefig(args.output / 'attention.png', dpi=160)
    plt.close(fig)
    for name, tensor in trace.items():
        print(f'{name:16} {list(tensor.shape)}')
    print(json.dumps(metrics, indent=2))
    print(f'PASS: {len(checks)} numerical checks')


if __name__ == '__main__':
    main()

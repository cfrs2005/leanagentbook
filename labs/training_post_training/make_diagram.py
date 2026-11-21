"""Editable, dependency-free SVG architecture source."""
from pathlib import Path
from xml.sax.saxutils import escape

parts=['''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1120 620" role="img" aria-labelledby="title desc">
<title id="title">训练与后训练：数据边界和真实 LoRA 实验</title>
<desc id="desc">数据按场景独立划分。训练集更新适配器，验证集选择轮次，测试集仅最终评测。冻结底座与适配器重载后验证一致性。</desc>
<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8" fill="#66777c"/></marker></defs>
<rect width="1120" height="620" fill="#f7f3eb"/>
<g font-family="PingFang SC, Noto Sans CJK SC, sans-serif" fill="#243b41">
<text x="48" y="52" font-size="28" font-weight="700">模型训练与后训练</text>
<text x="48" y="83" font-size="17">先定义可测的行为，再决定是否改变权重。</text>''']

def box(x,y,w,h,title,lines,fill='#ffffff'):
    parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="{fill}" stroke="#b6c4c5"/>')
    parts.append(f'<text x="{x+18}" y="{y+30}" font-size="19" font-weight="600">{escape(title)}</text>')
    for i,line in enumerate(lines):
        parts.append(f'<text x="{x+18}" y="{y+58+i*24}" font-size="16">{escape(line)}</text>')

def arrow(x1,y1,x2,y2):
    parts.append(f'<path d="M{x1},{y1} L{x2},{y2}" stroke="#66777c" stroke-width="2" marker-end="url(#arrow)"/>')

box(48,116,290,122,'训练集 · 36 条',['仅用于梯度更新','场景不跨集，输入不重复'])
box(412,116,290,122,'验证集 · 12 条',['每轮计算 token loss','仅据此选择 checkpoint'])
box(776,116,296,122,'测试集 · 12 条',['选定后评测一次','保留全部预测与错误'])
box(48,296,290,136,'冻结 FLAN-T5-small',['FP32 CPU · 固定 revision','训练 LoRA：q / v，rank 8','真实反向传播与参数更新'],'#e6eeeb')
box(412,296,290,136,'8 轮 SFT → 选定适配器',['交叉熵 + AdamW','loss 曲线、配置与种子','权重留本机，不入仓库'],'#e6eeeb')
box(776,296,296,136,'对比基线 / 训练后',['同提示词、同解码配置','accuracy / macro-F1','重新加载后核对 logits'],'#e6eeeb')
arrow(193,238,193,296);arrow(557,238,557,296);arrow(924,238,924,296)
arrow(338,364,412,364);arrow(702,364,776,364)
box(48,488,1024,88,'边界',['本实验只执行 SFT + LoRA；QLoRA、PPO、DPO、GRPO 与蒸馏用于路线比较，不宣称已实跑。'],'#f1e5d7')
parts.append('</g></svg>')
root=Path(__file__).resolve().parents[2]
(root/'diagrams'/'training-post-training.svg').write_text('\n'.join(parts))

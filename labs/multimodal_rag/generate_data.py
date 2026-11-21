"""Create original synthetic SVGs and explicit query annotations, without models."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
COLORS = {'red': '#d62828', 'blue': '#1769d2', 'green': '#208444'}
SHAPES = {
    'circle': '<circle cx="160" cy="160" r="90" fill="{color}"/>',
    'square': '<rect x="70" y="70" width="180" height="180" fill="{color}"/>',
    'triangle': '<polygon points="160,55 265,250 55,250" fill="{color}"/>',
    'star': '<polygon points="160,45 188,120 270,120 205,170 230,250 160,200 90,250 115,170 50,120 132,120" fill="{color}"/>',
}


def generate():
    data = ROOT / 'data'
    (data / 'images').mkdir(parents=True, exist_ok=True)
    items, queries = [], []
    synonyms = {'circle': 'round disk', 'square': 'four sided square',
                'triangle': 'three sided triangle', 'star': 'five pointed star'}
    for color, value in COLORS.items():
        for shape, template in SHAPES.items():
            key = f'{color}_{shape}'
            svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 320" '
                   f'role="img" aria-labelledby="title desc"><title id="title">{key}</title>'
                   '<desc id="desc">Original synthetic geometric teaching sample, not a photograph.</desc>'
                   '<rect width="320" height="320" fill="white"/>' +
                   template.format(color=value) + '</svg>\n')
            (data / 'images' / f'{key}.svg').write_text(svg)
            items.append({'id': key, 'title': f'{color} {shape}',
                          'title_origin': 'author_annotation_not_ocr',
                          'tenant': 'course', 'collection': 'synthetic_shapes_v1',
                          'source': f'images/{key}.svg', 'image': f'images/{key}.png',
                          'page': 1, 'bbox_xyxy': [0, 0, 320, 320],
                          'width': 320, 'height': 320, 'synthetic': True})
            for split, query in [('dev', f'a {color} {shape} on a white background'),
                                 ('test', f'an illustration of a {color} {synonyms[shape]}')]:
                queries.append({'id': f'{split}_{key}', 'split': split,
                                'text': query, 'relevant': [key], 'kind': 'known'})
    unknown = {
        'dev': ['a yellow circle on a white background', 'a purple square on a white background',
                'a red hexagon on a white background', 'a photograph of a dog',
                'a bicycle parked on a street', 'a bowl of fresh fruit'],
        'test': ['an illustration of an orange round disk', 'an illustration of a pink triangle',
                 'an illustration of a blue pentagon', 'a photograph of a cat',
                 'a damaged industrial motor', 'a bowl of hot soup'],
    }
    for split, texts in unknown.items():
        for index, query in enumerate(texts):
            queries.append({'id': f'{split}_unknown_{index}', 'split': split,
                            'text': query, 'relevant': [], 'kind': 'unknown'})
    (data / 'manifest.json').write_text(json.dumps(items, indent=2) + '\n')
    (data / 'queries.json').write_text(json.dumps(queries, indent=2) + '\n')


if __name__ == '__main__':
    generate()

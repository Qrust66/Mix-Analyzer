import json
from collections import Counter
from pathlib import Path

extraction = json.loads(Path('.graphify_extract.json').read_text(encoding='utf-8'))
analysis   = json.loads(Path('.graphify_analysis.json').read_text(encoding='utf-8'))

id_to_label = {n['id']: n.get('label', n['id']) for n in extraction['nodes']}
id_to_source = {n['id']: n.get('source_file', '') for n in extraction['nodes']}

communities = analysis['communities']
ranked = sorted(communities.items(), key=lambda kv: -len(kv[1]))

lines = []
lines.append(f'Total communities: {len(ranked)}')
lines.append('')
for cid, members in ranked:
    labels = [id_to_label.get(m, m) for m in members[:6]]
    sources = Counter()
    for m in members:
        s = id_to_source.get(m, '')
        if s:
            top = s.split('\\')[0] if '\\' in s else s.split('/')[0]
            sources[top] += 1
    src_summary = ', '.join(f'{k}({v})' for k,v in sources.most_common(3))
    lines.append(f'C{cid:>3} ({len(members):>4} nodes) [{src_summary}]')
    lines.append(f'   top: {labels}')

Path('.graphify_label_summary.txt').write_text('\n'.join(lines), encoding='utf-8')
print(f'Wrote {len(ranked)} community summaries')

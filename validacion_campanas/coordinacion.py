"""Grafo exploratorio: >=3 textos distintos compartidos en intervalos de 60 s.

Las etiquetas solo se incorporan después de construir la red.
"""
import argparse
import gc
import hashlib
import itertools
import json
import math
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import networkx as nx
import pandas as pd

from preparar import WINDOW, creation_time

P = Path(__file__).resolve().parent


def main(campaign, data_dir):
    table = pd.read_csv(P/f'{campaign}_curado.csv.gz', dtype={'userid': str})
    labels = dict(zip(table.userid, table.label.astype(int)))
    canonical = {u: u for u in labels}
    del table
    start, end = map(creation_time, WINDOW[campaign])
    events = {}; scanned = skipped_date = skipped_short = 0
    for kind in ['bad', 'good']:
        with (data_dir/f'{campaign}-{kind}-anonymized').open() as f:
            for line in f:
                d = json.loads(line); scanned += 1
                t = float(d['tweet_time'])/1000
                if not start <= t < end:
                    skipped_date += 1; continue
                uid = canonical.get(str(d['userid']))
                if uid is None:
                    continue
                txt = d.get('tweet_text') or ''
                if len(txt) < 30:
                    skipped_short += 1; continue
                key = (hashlib.blake2b(txt.encode(), digest_size=16).digest(), int(t//60))
                if key not in events:
                    events[key] = uid
                else:
                    old = events[key]
                    if old is None:
                        continue
                    if isinstance(old, str):
                        if old != uid:
                            events[key] = {old, uid}
                    else:
                        old.add(uid)
                        if len(old) > 50:
                            events[key] = None
                if scanned % 500000 == 0:
                    print(campaign, scanned, 'tweets', len(events), 'eventos', flush=True)
    grouped = [(key[0], value) for key, value in events.items() if isinstance(value, set)]
    oversized = sum(v is None for v in events.values())
    unique_events = len(events)
    del events; gc.collect()
    pairs = {}
    for digest, members in grouped:
        for pair in itertools.combinations(sorted(members), 2):
            pairs.setdefault(pair, set()).add(digest)
    candidate_pairs = len(pairs)
    g = nx.Graph()
    for (u, v), texts in pairs.items():
        if len(texts) >= 3:
            g.add_edge(u, v, weight=len(texts))
    del pairs, grouped; gc.collect()
    components = sorted(nx.connected_components(g), key=lambda c: (-len(c), min(c)))
    component_id = {u: i+1 for i, comp in enumerate(components) for u in comp}
    nx.set_node_attributes(g, {u: int(labels[u]) for u in g}, 'label')
    nx.set_node_attributes(g, component_id, 'component')
    nx.write_graphml(g, P/f'{campaign}_coordinacion.graphml.gz')
    pd.DataFrame([{'source': u, 'target': v, 'shared_distinct_texts': d['weight']} for u, v, d in g.edges(data=True)],
                 columns=['source', 'target', 'shared_distinct_texts']).to_csv(P/f'{campaign}_aristas.csv.gz', index=False)
    pd.DataFrame([{'userid': u, 'label': labels[u], 'degree': int(g.degree(u)), 'component': component_id[u]}
                  for u in g], columns=['userid', 'label', 'degree', 'component']).to_csv(P/f'{campaign}_nodos.csv.gz', index=False)
    comp_rows = [{'component': i+1, 'accounts': len(c), 'positive_accounts': sum(labels[u] for u in c),
                  'edges': g.subgraph(c).number_of_edges()} for i, c in enumerate(components)]
    pd.DataFrame(comp_rows, columns=['component', 'accounts', 'positive_accounts', 'edges']).to_csv(P/f'{campaign}_componentes.csv', index=False)
    positive_nodes = sum(labels[u] for u in g)
    info = {'rows_scanned': scanned, 'outside_window_rows': skipped_date, 'short_text_rows': skipped_short,
            'time_bin_seconds': 60, 'min_distinct_texts': 3, 'max_users_per_event': 50,
            'unique_events': unique_events, 'oversized_events_excluded': oversized,
            'candidate_pairs': candidate_pairs, 'nodes': g.number_of_nodes(), 'edges': g.number_of_edges(),
            'components': len(components), 'positive_nodes': positive_nodes,
            'reference_nodes': g.number_of_nodes()-positive_nodes,
            'positive_fraction_among_nodes': positive_nodes/max(1, g.number_of_nodes()),
            'positive_coverage': positive_nodes/max(1, sum(labels.values())), 'largest_components': comp_rows[:10]}
    (P/f'{campaign}_coordinacion.json').write_text(json.dumps(info, indent=2))
    fig, ax = plt.subplots(figsize=(10, 6))
    shown = set()
    for comp in components[:5]:
        remaining = 150-len(shown)
        shown.update(sorted(comp, key=lambda u: (-g.degree(u), u))[:remaining])
        if len(shown) >= 150:
            break
    sub = g.subgraph(shown).copy()
    if shown:
        pos = nx.spring_layout(sub, seed=42, iterations=60)
        nx.draw_networkx_edges(sub, pos, ax=ax, alpha=.12, width=.6)
        nx.draw_networkx_nodes(sub, pos, ax=ax, node_size=[20+10*math.log1p(g.degree(u)) for u in sub],
                               node_color=['#ca4b45' if labels[u] else '#3b79a5' for u in sub], linewidths=0)
    ax.set_title(f'{campaign.upper()}: coincidencia repetida de textos en intervalos de 60 s\n'
                 f'Muestra de {len(shown)} nodos de {g.number_of_nodes():,}; red exploratoria')
    ax.legend(handles=[Line2D([0], [0], marker='o', color='w', markerfacecolor='#ca4b45', label='Etiqueta: operación'),
                       Line2D([0], [0], marker='o', color='w', markerfacecolor='#3b79a5', label='Etiqueta: referencia')], loc='lower right')
    ax.axis('off'); fig.tight_layout(); fig.savefig(P/f'{campaign}_grafo.png', dpi=160); plt.close(fig)
    print(json.dumps(info, indent=2), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('campaign', choices=WINDOW)
    parser.add_argument(
        '--data-dir',
        type=Path,
        default=Path.home() / 'Downloads',
        help='Directorio que contiene <campaña>-{bad,good}-anonymized '
             '(por defecto: ~/Downloads)',
    )
    args = parser.parse_args()
    main(args.campaign, args.data_dir)

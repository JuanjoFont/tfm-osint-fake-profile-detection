"""Controles independientes de particiones, recuentos y modelos guardados."""
import gc
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import confusion_matrix, average_precision_score

P = Path(__file__).resolve().parent


def read(path):
    return pd.read_csv(path, dtype={'userid': str})


def main():
    checks = []
    frames = {c: read(P/f'{c}_curado.csv.gz') for c in ['honduras', 'uae']}
    for c, df in frames.items():
        audit = json.loads((P/f'{c}_full_curado_auditoria.json').read_text())
        assert df.userid.is_unique and not df.isna().any().any()
        assert set(df.label) == {0, 1}
        assert len(df) == audit['full']['accounts']
        assert df.label.sum() == audit['full']['positives']
        assert df.tweet_count.sum() == audit['full']['tweets']
        expected = sum(audit[k]['rows']-audit[k]['duplicates_removed']-audit[k]['outside_window_excluded'] for k in ['bad', 'good'])
        assert expected == df.tweet_count.sum()
        temporal = json.loads((P/f'{c}_temporal_curado_auditoria.json').read_text())
        assert temporal['early']['tweets']+temporal['late']['tweets'] == expected
        checks.append(c+': recuentos, etiquetas, unicidad, ausencia de nulos y conservación temporal correctos')
    for path in P.glob('*_particiones.csv.gz'):
        parts = read(path)
        assert parts.userid.is_unique
        assert set(parts.split) <= {'train', 'validation', 'test'}
        checks.append(path.name+': ninguna cuenta compartida entre particiones')
    shared = set(frames['honduras'].userid) & set(frames['uae'].userid)
    assert len(shared) == json.loads((P/'solapamiento_curado.json').read_text())['shared_userids']
    specs = {
        'honduras_curado_interno': ('honduras_curado', 'honduras'),
        'uae_curado_interno': ('uae_curado', 'uae'),
        'honduras_curado_a_uae': ('honduras_curado', 'uae'),
        'uae_curado_a_honduras': ('uae_curado', 'honduras'),
        'conjunto_global': ('conjunto', 'both'),
        'conjunto_honduras': ('conjunto', 'honduras'),
        'conjunto_uae': ('conjunto', 'uae'),
        'temporal_honduras': ('temporal_honduras', 'honduras_late'),
        'temporal_uae': ('temporal_uae', 'uae_late'),
    }
    for name, (model_name, source) in specs.items():
        if not (P/f'{name}_resultados.json').exists():
            continue
        pred = read(P/f'{name}_predicciones.csv.gz')
        r = json.loads((P/f'{name}_resultados.json').read_text())
        assert pred.userid.is_unique and len(pred) == r['n']
        assert int(pred.label.sum()) == r['positives']
        tn, fp, fn, tp = confusion_matrix(pred.label, pred.prediction, labels=[0, 1]).ravel()
        assert [int(tn), int(fp), int(fn), int(tp)] == [r[k] for k in ['tn', 'fp', 'fn', 'tp']]
        assert np.isclose(average_precision_score(pred.label, pred.score), r['average_precision'])
        assert np.array_equal((pred.score >= r['threshold']).astype(int), pred.prediction)
        if '_a_' in name:
            assert not (set(pred.userid) & shared)
            source_campaign = 'honduras' if name.startswith('honduras') else 'uae'
            assert not (set(pred.userid) & set(frames[source_campaign].userid))
        elif name.startswith('temporal'):
            campaign = name.removeprefix('temporal_')
            early = read(P/f'{campaign}_early.csv.gz')
            assert not (set(pred.userid) & set(early.userid))
            del early
        else:
            parts = read(P/f'{model_name}_particiones.csv.gz')
            assert set(pred.userid) <= set(parts.loc[parts.split == 'test', 'userid'])
        if source == 'both':
            data = pd.concat([df[~df.userid.isin(shared)] for df in frames.values()])
        elif source.endswith('_late'):
            data = read(P/(source+'.csv.gz'))
        else:
            data = frames[source]
        sample = pred.sample(min(2000, len(pred)), random_state=91)
        x = data.set_index('userid').loc[sample.userid]
        bundle = joblib.load(P/f'{model_name}_modelo.joblib')
        scores = bundle['model'].predict_proba(x[bundle['features']])[:, 1]
        assert np.allclose(scores, sample.score, rtol=1e-12, atol=1e-12)
        assert bundle['threshold'] == r['threshold']
        checks.append(name+': métricas recalculadas y 2.000 scores reproducidos con el modelo recargado')
        del bundle, data, x, sample; gc.collect()
    for c in frames:
        graph = json.loads((P/f'{c}_coordinacion.json').read_text())
        edges = pd.read_csv(P/f'{c}_aristas.csv.gz', dtype={'source': str, 'target': str})
        nodes = read(P/f'{c}_nodos.csv.gz')
        assert len(edges) == graph['edges'] and len(nodes) == graph['nodes']
        assert (edges.shared_distinct_texts >= 3).all() and (edges.source != edges.target).all()
        assert not edges[['source', 'target']].duplicated().any()
        assert set(edges.source) | set(edges.target) == set(nodes.userid)
        assert nodes.label.sum() == graph['positive_nodes']
        checks.append(c+': red, nodos, aristas y etiquetas consistentes')
    (P/'verificacion.json').write_text(json.dumps({'status': 'passed', 'checks': checks}, indent=2))
    print('\n'.join(checks))


if __name__ == '__main__':
    main()

"""Fusión tardía de dos señales reales con calibración exclusiva en validación.

Combina la probabilidad del Random Forest de metadatos con el grado observado
en la red de coincidencia temporal. La red se construye sin usar etiquetas,
pero sobre la ventana completa de la campaña: el análisis es transductivo y
retrospectivo, no una simulación de alerta en producción.
"""
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import (average_precision_score, confusion_matrix,
                             f1_score, precision_score, recall_score,
                             roc_auc_score)

from experimentos import FEATURES

P = Path(__file__).resolve().parent


def metrics(y, scores, threshold):
    pred = (scores >= threshold).astype(int)
    tn, fp, fn, tp = [int(x) for x in confusion_matrix(y, pred, labels=[0, 1]).ravel()]
    return {
        'n': int(len(y)), 'positives': int(y.sum()), 'threshold': float(threshold),
        'precision': float(precision_score(y, pred, zero_division=0)),
        'recall': float(recall_score(y, pred, zero_division=0)),
        'f1': float(f1_score(y, pred, zero_division=0)),
        'average_precision': float(average_precision_score(y, scores)),
        'roc_auc': float(roc_auc_score(y, scores)),
        'tn': tn, 'fp': fp, 'fn': fn, 'tp': tp,
    }


def best_threshold(y, scores):
    candidates = np.linspace(0, 1, 201)
    values = np.array([f1_score(y, scores >= t, zero_division=0) for t in candidates])
    return float(candidates[int(np.argmax(values))])


def campaign(name):
    accounts = pd.read_csv(P/f'{name}_curado.csv.gz', dtype={'userid': str})
    parts = pd.read_csv(P/f'{name}_curado_particiones.csv.gz', dtype={'userid': str})[['userid', 'split']]
    nodes = pd.read_csv(P/f'{name}_nodos.csv.gz', dtype={'userid': str})[['userid', 'degree']]
    bundle = joblib.load(P/f'{name}_curado_modelo.joblib')
    frame = accounts.merge(parts, on='userid', how='inner', validate='one_to_one')
    frame = frame.merge(nodes, on='userid', how='left', validate='one_to_one')
    frame['degree'] = frame.degree.fillna(0)
    frame['score_rf'] = bundle['model'].predict_proba(frame[FEATURES])[:, 1]

    development = frame[frame.split.isin(['train', 'validation'])]
    nonzero_development = development.loc[development.degree > 0, 'degree']
    scale = float(np.quantile(np.log1p(nonzero_development), .95)) if len(nonzero_development) else 1.0
    if scale <= 0:
        scale = 1.0
    frame['score_network'] = np.clip(np.log1p(frame.degree)/scale, 0, 1)
    validation = frame[frame.split == 'validation']
    test = frame[frame.split == 'test']

    candidates = []
    for alpha in np.linspace(0, 1, 21):
        score = alpha*validation.score_rf.to_numpy() + (1-alpha)*validation.score_network.to_numpy()
        threshold = best_threshold(validation.label.to_numpy(), score)
        value = f1_score(validation.label, score >= threshold, zero_division=0)
        candidates.append((value, float(alpha), threshold))
    _, alpha, threshold = max(candidates, key=lambda x: (x[0], x[1]))

    y = test.label.to_numpy()
    rf = test.score_rf.to_numpy()
    network = test.score_network.to_numpy()
    fused = alpha*rf + (1-alpha)*network
    network_threshold = best_threshold(validation.label.to_numpy(), validation.score_network.to_numpy())
    result = {
        'campaign': name,
        'design': 'retrospective_transductive_two_signal_late_fusion',
        'network_score': 'clip(log1p(degree)/q95_nonzero_development_log_degree, 0, 1)',
        'network_scale_q95': scale,
        'alpha_rf': alpha,
        'alpha_network': 1-alpha,
        'selection': 'alpha and threshold selected only on validation F1',
        'rf': metrics(y, rf, bundle['threshold']),
        'network': metrics(y, network, network_threshold),
        'fusion': metrics(y, fused, threshold),
    }
    return result


def main():
    results = [campaign(name) for name in ['honduras', 'uae']]
    rows = []
    for item in results:
        for signal in ['rf', 'network', 'fusion']:
            rows.append({'campaign': item['campaign'], 'signal': signal,
                         'alpha_rf': item['alpha_rf'] if signal == 'fusion' else None,
                         'alpha_network': item['alpha_network'] if signal == 'fusion' else None,
                         **item[signal]})
    pd.DataFrame(rows).to_csv(P/'fusion_real_resultados.csv', index=False)
    (P/'fusion_real_detalle.json').write_text(json.dumps(results, indent=2))
    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()

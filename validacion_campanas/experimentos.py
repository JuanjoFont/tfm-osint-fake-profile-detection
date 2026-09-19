"""Experimentos predefinidos; ejecución por etapas para limitar memoria y disco."""
import argparse
import gc
import json
import platform
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (average_precision_score, roc_auc_score, precision_score,
                             recall_score, f1_score, confusion_matrix, precision_recall_curve)
from sklearn.model_selection import train_test_split

P = Path(__file__).resolve().parent
H = P.parent/'entrenamiento_honduras'
FEATURES = [
    'tweet_count', 'active_days', 'span_days', 'duplicate_text_fraction',
    'hour_entropy', 'max_hour_fraction', 'tweets_per_active_day',
    'retweet_fraction', 'reply_fraction', 'quote_fraction',
    'mean_text_length', 'mean_hashtags', 'mean_urls', 'mean_user_mentions',
    'mean_follower_count', 'mean_following_count', 'mean_account_age_days',
]
SEED = 42


def read(path):
    return pd.read_csv(path, dtype={'userid': str})


def make_model():
    return RandomForestClassifier(n_estimators=300, min_samples_leaf=3, max_features=.8,
                                  class_weight='balanced_subsample', n_jobs=3, random_state=SEED)


def choose_threshold(y, scores):
    pr, re, th = precision_recall_curve(y, scores)
    fs = 2*pr[:-1]*re[:-1]/np.maximum(pr[:-1]+re[:-1], 1e-15)
    return float(th[int(np.argmax(fs))])


def evaluate(name, bundle, df):
    scores = bundle['model'].predict_proba(df[FEATURES])[:, 1]
    y = df.label.to_numpy(); pred = (scores >= bundle['threshold']).astype(int)
    tn, fp, fn, tp = [int(x) for x in confusion_matrix(y, pred, labels=[0, 1]).ravel()]
    result = {'n': len(df), 'positives': int(y.sum()), 'prevalence': float(y.mean()),
              'threshold': bundle['threshold'], 'precision': float(precision_score(y, pred, zero_division=0)),
              'recall': float(recall_score(y, pred, zero_division=0)), 'f1': float(f1_score(y, pred, zero_division=0)),
              'average_precision': float(average_precision_score(y, scores)),
              'roc_auc': float(roc_auc_score(y, scores)) if len(np.unique(y)) == 2 else None,
              'false_positive_rate': fp/(fp+tn) if fp+tn else None,
              'accuracy': (tp+tn)/len(df), 'tn': tn, 'fp': fp, 'fn': fn, 'tp': tp}
    # Intervalos condicionales al modelo, umbral y prevalencia del test.
    # El muestreo multinomial de la matriz equivale al bootstrap estratificado
    # para las métricas binarias sin ordenar scores; no estima IC de AP.
    rng = np.random.default_rng(SEED)
    tps = rng.binomial(tp+fn, tp/(tp+fn), 2000) if tp+fn else np.zeros(2000)
    fps = rng.binomial(fp+tn, fp/(fp+tn), 2000) if fp+tn else np.zeros(2000)
    precision = tps/np.maximum(tps+fps, 1)
    recall = tps/max(tp+fn, 1)
    f1 = 2*tps/np.maximum(2*tps+fps+(tp+fn-tps), 1)
    result['conditional_bootstrap_95_ci'] = {k: np.percentile(v, [2.5, 97.5]).tolist()
                                            for k, v in [('precision', precision), ('recall', recall), ('f1', f1)]}
    meta = [c for c in ['userid', 'campaign', 'label'] if c in df]
    df[meta].assign(score=scores, prediction=pred).to_csv(P/f'{name}_predicciones.csv.gz', index=False)
    (P/f'{name}_resultados.json').write_text(json.dumps(result, indent=2))
    print(name, json.dumps(result), flush=True)
    return result


def fit(name, df, stratify, train_fraction=.6):
    idx = np.arange(len(df))
    tr, other = train_test_split(idx, train_size=train_fraction, stratify=stratify, random_state=SEED)
    if train_fraction == .6:
        va, te = train_test_split(other, test_size=.5, stratify=stratify.iloc[other], random_state=SEED)
    else:
        va, te = other, np.array([], dtype=int)
    assert not (set(df.iloc[tr].userid) & set(df.iloc[va].userid))
    if len(te):
        assert not (set(df.iloc[tr].userid) & set(df.iloc[te].userid))
    parts = np.full(len(df), 'train', dtype=object); parts[va] = 'validation'; parts[te] = 'test'
    meta = [c for c in ['userid', 'campaign', 'label'] if c in df]
    df[meta].assign(split=parts).to_csv(P/f'{name}_particiones.csv.gz', index=False)
    print('Entrenando', name, len(tr), 'cuentas', flush=True)
    m = make_model(); m.fit(df.iloc[tr][FEATURES], df.iloc[tr].label)
    scores = m.predict_proba(df.iloc[va][FEATURES])[:, 1]
    threshold = choose_threshold(df.iloc[va].label, scores)
    bundle = {'model': m, 'features': FEATURES, 'threshold': threshold, 'seed': SEED,
              'validation_average_precision': float(average_precision_score(df.iloc[va].label, scores)),
              'split_counts': {s: {'n': int(sum(parts == s)), 'positives': int(df.label[parts == s].sum())}
                               for s in ['train', 'validation', 'test']}}
    joblib.dump(bundle, P/f'{name}_modelo.joblib', compress=3)
    (P/f'{name}_ajuste.json').write_text(json.dumps({k: v for k, v in bundle.items() if k != 'model'}, indent=2))
    return bundle, df.iloc[te]


def cross():
    if not (H/'cuentas.csv').exists() or not (H/'modelo.joblib').exists():
        raise FileNotFoundError(
            'La etapa histórica cross requiere entrenamiento_honduras/cuentas.csv '
            'y entrenamiento_honduras/modelo.joblib; esos artefactos no forman '
            'parte del paquete público. Use curated para la evaluación depurada.'
        )
    h = read(H/'cuentas.csv'); u = read(P/'uae_cuentas.csv.gz')
    shared = set(h.userid) & set(u.userid)
    shared_labels = h[h.userid.isin(shared)][['userid', 'label']].merge(u[u.userid.isin(shared)][['userid', 'label']], on='userid')
    audit = {'shared_userids': len(shared), 'conflicting_shared_labels': int((shared_labels.label_x != shared_labels.label_y).sum()),
             'honduras_n': len(h), 'uae_n': len(u)}
    (P/'solapamiento.json').write_text(json.dumps(audit, indent=2))
    print('Solapamiento', audit, flush=True)
    frozen = joblib.load(H/'modelo.joblib')
    evaluate('honduras_a_uae', frozen, u[~u.userid.isin(shared)])
    del frozen; gc.collect()
    bundle, test = fit('uae', u, u.label)
    evaluate('uae_interno', bundle, test)
    evaluate('uae_a_honduras', bundle, h[~h.userid.isin(shared)])


def combined():
    h = read(P/'honduras_curado.csv.gz').assign(campaign='honduras'); u = read(P/'uae_curado.csv.gz').assign(campaign='uae')
    shared = set(h.userid) & set(u.userid)
    both = pd.concat([h[~h.userid.isin(shared)], u[~u.userid.isin(shared)]], ignore_index=True)
    assert both.userid.is_unique
    bundle, test = fit('conjunto', both, both.campaign+'_'+both.label.astype(str))
    evaluate('conjunto_global', bundle, test)
    for campaign in ['honduras', 'uae']:
        evaluate('conjunto_'+campaign, bundle, test[test.campaign == campaign])


def curated():
    h = read(P/'honduras_curado.csv.gz'); u = read(P/'uae_curado.csv.gz')
    shared = set(h.userid) & set(u.userid)
    (P/'solapamiento_curado.json').write_text(json.dumps({'shared_userids': len(shared)}, indent=2))
    # Comparación histórica opcional. El modelo y las predicciones individuales
    # no se redistribuyen en el paquete público.
    if (H/'modelo.joblib').exists() and (H/'cuentas.csv').exists():
        original = joblib.load(H/'modelo.joblib')
        original_ids = set(read(H/'cuentas.csv').userid)
        evaluate('original_honduras_a_uae_curado', original, u[~u.userid.isin(original_ids)])
        del original; gc.collect()
    else:
        print('Comparación histórica omitida: no están los artefactos privados de entrenamiento_honduras.', flush=True)
    for name, source, dest in [('honduras', h, u), ('uae', u, h)]:
        bundle, test = fit(name+'_curado', source, source.label)
        evaluate(name+'_curado_interno', bundle, test)
        destination = 'uae' if name == 'honduras' else 'honduras'
        evaluate(name+'_curado_a_'+destination, bundle, dest[~dest.userid.isin(shared)])
        del bundle; gc.collect()


def temporal():
    for campaign in ['honduras', 'uae']:
        early = read(P/f'{campaign}_early.csv.gz'); late = read(P/f'{campaign}_late.csv.gz')
        unseen = late[~late.userid.isin(early.userid)]
        info = {'early_accounts': len(early), 'early_positives': int(early.label.sum()),
                'late_accounts': len(late), 'late_unseen_accounts': len(unseen),
                'late_unseen_positives': int(unseen.label.sum()), 'excluded_seen_accounts': len(late)-len(unseen)}
        (P/f'temporal_{campaign}_poblacion.json').write_text(json.dumps(info, indent=2))
        if early.label.value_counts().min() < 10 or unseen.label.nunique() < 2:
            print('No evaluable temporal', campaign, info, flush=True)
            continue
        bundle, _ = fit('temporal_'+campaign, early, early.label, train_fraction=.8)
        evaluate('temporal_'+campaign, bundle, unseen)
        del bundle, early, late, unseen; gc.collect()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('stage', choices=['cross', 'curated', 'combined', 'temporal'])
    stage = parser.parse_args().stage
    (P/'versiones.json').write_text(json.dumps({'python': platform.python_version(), 'sklearn': sklearn.__version__,
                                              'numpy': np.__version__, 'pandas': pd.__version__}, indent=2))
    {'cross': cross, 'curated': curated, 'combined': combined, 'temporal': temporal}[stage]()

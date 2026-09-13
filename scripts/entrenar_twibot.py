"""Entrena solo con train y exporta evaluación test y demostración sintética.

Uso: python scripts/entrenar_twibot.py --data-dir /ruta/TwiBot-22 --output salidas/reentrenamiento
No ajusta pesos, umbrales ni hiperparámetros utilizando test.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import platform
import secrets
import time

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (accuracy_score, auc, average_precision_score,
    classification_report, confusion_matrix, f1_score, precision_recall_curve,
    precision_score, recall_score, roc_auc_score, roc_curve)

FEATURES = ['followers_count', 'following_count', 'ratio_rep', 'tweet_count',
    'listed_count', 'antiguedad_dias', 'has_description', 'len_description',
    'has_location', 'has_url', 'verified', 'protected']


def iter_users(path):
    """Lee un array JSON incrementalmente sin cargar todo el documento."""
    decoder = json.JSONDecoder()
    with path.open(encoding='utf-8') as stream:
        buffer = ''
        eof = False
        started = False
        while True:
            if not eof and len(buffer) < 1048576:
                chunk = stream.read(1048576)
                eof = not chunk
                buffer += chunk
            buffer = buffer.lstrip()
            if not started:
                if not buffer.startswith('['):
                    raise ValueError('Se esperaba un array JSON de usuarios')
                buffer = buffer[1:]
                started = True
                continue
            buffer = buffer.lstrip()
            if buffer.startswith(']'):
                if buffer[1:].strip() or stream.read().strip():
                    raise ValueError('Contenido tras el array JSON')
                return
            if buffer.startswith(','):
                buffer = buffer[1:].lstrip()
            try:
                user, end = decoder.raw_decode(buffer)
            except json.JSONDecodeError:
                if eof:
                    raise
                chunk = stream.read(1048576)
                eof = not chunk
                buffer += chunk
                continue
            yield user
            buffer = buffer[end:]


def extract_features(path):
    records = []
    for n, u in enumerate(iter_users(path), 1):
        m = u.get('public_metrics') or {}
        e = u.get('entities') or {}
        followers = m.get('followers_count', 0) or 0
        following = m.get('following_count', 0) or 0
        records.append([u['id'], followers, following, followers/(following+1),
            m.get('tweet_count', 0) or 0, m.get('listed_count', 0) or 0,
            u.get('created_at'), int(bool(u.get('description'))),
            len(u.get('description') or ''), int(bool(u.get('location'))),
            int(bool(e.get('url'))) if isinstance(e, dict) else 0,
            int(bool(u.get('verified'))), int(bool(u.get('protected')))])
        if n % 200000 == 0:
            print(f'Metadatos leídos: {n:,}', flush=True)
    frame = pd.DataFrame(records, columns=['id']+FEATURES)
    dates = pd.to_datetime(frame.antiguedad_dias, utc=True, errors='coerce', format='mixed')
    invalid_dates = int(dates.isna().sum())
    frame['antiguedad_dias'] = (pd.Timestamp('2022-06-01', tz='UTC')-dates).dt.days.fillna(0).clip(lower=0)
    return frame, invalid_dates


def metrics(truth, scores, pred):
    tn, fp, fn, tp = confusion_matrix(truth, pred, labels=[0,1]).ravel()
    precision, recall, _ = precision_recall_curve(truth, scores)
    return dict(precision=precision_score(truth,pred,zero_division=0),
        recall=recall_score(truth,pred,zero_division=0), f1=f1_score(truth,pred,zero_division=0),
        accuracy=accuracy_score(truth,pred), roc_auc=roc_auc_score(truth,scores),
        pr_auc_trapecios=auc(recall,precision), average_precision=average_precision_score(truth,scores),
        TN=int(tn), FP=int(fp), FN=int(fn), TP=int(tp))


def sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('salidas/reentrenamiento'))
    parser.add_argument('--data-dir', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    out = root / args.output
    out.mkdir(parents=True, exist_ok=False)
    start = time.perf_counter()
    timestamp = datetime.now(timezone.utc).isoformat()
    raw = args.data_dir.resolve()
    labels = pd.read_csv(raw/'label.csv', dtype={'id':str})
    splits = pd.read_csv(raw/'split.csv', dtype={'id':str})
    for frame in (labels,splits):
        if frame.id.isna().any() or frame.id.duplicated().any():
            raise ValueError('Identificadores ausentes o duplicados')
    if set(labels.id) != set(splits.id):
        raise ValueError('Etiquetas y particiones no cubren las mismas cuentas')
    if not set(labels.label).issubset({'bot','human'}):
        raise ValueError('Etiquetas desconocidas')
    if not set(splits.split).issubset({'train','val','test'}):
        raise ValueError('Particiones desconocidas')
    meta = labels.merge(splits,on='id',validate='one_to_one')
    features, invalid_dates = extract_features(raw/'user.json')
    if features.id.duplicated().any() or features.id.isna().any():
        raise ValueError('Metadatos con identificadores duplicados o ausentes')
    if set(meta.id) != set(features.id):
        raise ValueError('No coinciden metadatos y cuentas etiquetadas; revisar cobertura')
    dataset = meta.merge(features,on='id',validate='one_to_one')
    del features, meta, labels, splits
    dataset['target'] = dataset.label.map({'human':0,'bot':1})
    train = dataset.split.eq('train')
    test = dataset.split.eq('test')
    if not train.any() or not test.any():
        raise ValueError('Train o test vacío')
    counts = pd.crosstab(dataset.split,dataset.label)
    counts.to_csv(out/'distribucion_particiones.csv')
    print(counts.to_string(),flush=True)
    model = RandomForestClassifier(n_estimators=100,max_depth=12,random_state=42,n_jobs=-1)
    print('Entrenamiento con train exclusivamente...',flush=True)
    model.fit(dataset.loc[train,FEATURES],dataset.loc[train,'target'])
    train_end = time.perf_counter()
    joblib.dump(model,out/'modelo_rf_cuenta.pkl')
    scores = model.predict_proba(dataset.loc[test,FEATURES])[:,list(model.classes_).index(1)]
    predicted = (scores>=0.5).astype(int)
    truth = dataset.loc[test,'target']
    result = metrics(truth,scores,predicted)
    result.update(n_train=int(train.sum()),n_test=int(test.sum()),
        train_bots=int(dataset.loc[train,'target'].sum()),train_humanos=int(train.sum()-dataset.loc[train,'target'].sum()),
        test_bots=int(truth.sum()),test_humanos=int(test.sum()-truth.sum()),
        n_estimators=100,max_depth=12,random_state=42,umbral=0.5,fecha_utc=timestamp)
    pd.DataFrame([result]).to_csv(out/'evaluacion_rf_twibot_test.csv',index=False)
    report = classification_report(truth,predicted,target_names=['human','bot'],output_dict=True,zero_division=0)
    (out/'classification_report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(result,indent=2),flush=True)
    private = root/'.private'
    private.mkdir(mode=0o700,exist_ok=True)
    key_path = private/'seudonimizacion_twibot.key'
    if not key_path.exists():
        fd = os.open(key_path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'wb') as stream:
            stream.write(secrets.token_bytes(32))
    key = key_path.read_bytes()
    def pseudonym(value):
        return 'TwiBot_'+hmac.new(key,str(value).encode(),hashlib.sha256).hexdigest()
    predictions = pd.DataFrame({'id_seudonimizado':dataset.loc[test,'id'].map(pseudonym).to_numpy(),
        'etiqueta_real':dataset.loc[test,'label'].to_numpy(),'score_rf_cuenta':scores,
        'prediccion_rf':np.where(predicted==1,'bot','human'), 'cohorte':'twibot22_test_real',
        'origen_etiqueta':'label.csv de TwiBot-22','objetivo_evaluacion':'bot_vs_human'})
    assert predictions.id_seudonimizado.is_unique
    predictions.to_csv(out/'predicciones_twibot_test.csv',index=False)
    historical = root/'datos/muestras_sinteticas_54.csv'
    synthetic = pd.read_csv(historical)
    synthetic['Score_RF_Cuenta'] = model.predict_proba(synthetic[FEATURES])[:,list(model.classes_).index(1)]
    synthetic['score_botometer'] = 0.5
    synthetic['origen_score_botometer'] = 'sustituto_neutral_0.5'
    synthetic['cohorte'] = 'escenario_sintetico'
    synthetic['origen_etiqueta'] = 'generador_sintetico'
    max_deg = synthetic.groupby('Escenario').degree.transform('max').replace(0,1)
    net = (synthetic.betweenness_centrality+synthetic.degree/max_deg)/2
    synthetic['Score_Amenaza_OSINT'] = (0.3*synthetic.Score_RF_Cuenta+0.5*net+0.2*0.5).round(4)
    sy_pred = (synthetic.betweenness_centrality>=0.08)|(synthetic.Score_Amenaza_OSINT>=0.35)
    synthetic['Clasificacion_Final'] = np.where(synthetic.betweenness_centrality>=0.08,
        'Nodo Puente / Coordinador',np.where(sy_pred,'Perfil Sospechoso / Amplificador','Comportamiento Orgánico / Humano'))
    synthetic.to_csv(out/'benchmark_sintetico_con_cohorte.csv',index=False)
    sy_result = metrics(synthetic.tipo_real.ne('Humano Orgánico').astype(int),synthetic.Score_Amenaza_OSINT,sy_pred)
    pd.DataFrame([sy_result]).to_csv(out/'evaluacion_sintetica_fusion.csv',index=False)
    sy_export = pd.DataFrame({'id_seudonimizado':synthetic.id_seudonimizado,
        'etiqueta_real':synthetic.tipo_real,'score_rf_cuenta':synthetic.Score_RF_Cuenta,
        'prediccion_rf':np.where(synthetic.Score_RF_Cuenta>=0.5,'bot','human'),
        'cohorte':synthetic.cohorte,'origen_etiqueta':synthetic.origen_etiqueta,
        'objetivo_evaluacion':'rol_sintetico_amenaza_vs_organico', 'escenario':synthetic.Escenario,
        'score_fusion':synthetic.Score_Amenaza_OSINT,'clasificacion_fusion':synthetic.Clasificacion_Final})
    consolidated = pd.concat([predictions,sy_export],ignore_index=True)
    assert len(consolidated)==int(test.sum())+54
    consolidated.to_csv(out/'entidades_demostracion_consolidada.csv',index=False)
    pd.Series(model.feature_importances_,index=FEATURES,name='importancia').sort_values(ascending=False).to_csv(out/'importancia_variables.csv')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from sklearn.metrics import ConfusionMatrixDisplay
    fig,axes=plt.subplots(1,3,figsize=(14,4.2))
    ConfusionMatrixDisplay.from_predictions(truth,predicted,display_labels=['Humano','Bot'],ax=axes[0],colorbar=False,cmap='Blues',values_format='d')
    axes[0].set_title('Matriz de confusión · test'); axes[0].set_xlabel('Predicción'); axes[0].set_ylabel('Etiqueta real')
    fpr,tpr,_=roc_curve(truth,scores)
    axes[1].plot(fpr,tpr,label=f'ROC-AUC = {result["roc_auc"]:.4f}')
    axes[1].plot([0,1],[0,1],'--',color='gray'); axes[1].set(xlabel='Tasa de falsos positivos',ylabel='Sensibilidad',title='Curva ROC'); axes[1].legend()
    pp,rr,_=precision_recall_curve(truth,scores)
    axes[2].plot(rr,pp,label=f'PR-AUC = {result["pr_auc_trapecios"]:.4f}')
    axes[2].axhline(float(truth.mean()),linestyle='--',color='gray',label='Prevalencia bot')
    axes[2].set(xlabel='Recall',ylabel='Precisión',title='Curva precisión-recall'); axes[2].legend()
    fig.tight_layout(); fig.savefig(out/'evaluacion_twibot_test.png',dpi=240); fig.savefig(out/'evaluacion_twibot_test.pdf'); plt.close(fig)
    hashes={path.name:sha256(path) for path in [raw/'user.json',raw/'label.csv',raw/'split.csv',historical,Path(__file__).resolve(),out/'modelo_rf_cuenta.pkl']}
    manifest=dict(fecha_utc=timestamp,python=platform.python_version(),pandas=pd.__version__,numpy=np.__version__,sklearn=sklearn.__version__,parametros=model.get_params(),variables=FEATURES,
        segundos_hasta_fin_entrenamiento=train_end-start,segundos_total=time.perf_counter()-start,
        fecha_referencia_antiguedad='2022-06-01 UTC',fechas_ausentes_o_invalidas=invalid_dates,
        ids_duplicados=0,solapamiento_ids_train_test=0,cobertura_metadatos_completa=True,
        validacion_no_usada_para_ajustes=True,umbral_fijado_antes_de_test=0.5,
        seudonimizacion='HMAC-SHA256 completo; clave local .private, excluida de entregables',sha256=hashes)
    (out/'manifiesto_ejecucion.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(f'Completado: {out}',flush=True)


if __name__=='__main__':
    main()

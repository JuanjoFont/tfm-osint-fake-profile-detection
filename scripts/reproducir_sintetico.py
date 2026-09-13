"""Reproduce fusión y ablaciones con las 54 muestras y scores RF guardados."""
import argparse
from pathlib import Path
import numpy as np
import pandas as pd
import networkx as nx
from sklearn.metrics import precision_score,recall_score,f1_score,confusion_matrix,roc_auc_score,precision_recall_curve,auc,accuracy_score

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, default=root/'salidas/reproduccion')
parser.add_argument('--model', type=Path, help='Opcional: recalcula y verifica los scores con un modelo local de confianza')
args = parser.parse_args()
s = pd.read_csv(root/'datos/muestras_sinteticas_54.csv')
assert len(s)==54 and s.id_seudonimizado.is_unique
assert s.score_botometer.eq(.5).all()
edges = pd.read_csv(root/'datos/aristas_sinteticas.csv')
assert len(edges)==81
for scenario, nodes in s.groupby('Escenario'):
    graph = nx.Graph()
    graph.add_nodes_from(nodes.id_seudonimizado)
    for edge in edges[edges.Escenario.eq(scenario)].itertuples(index=False):
        assert edge.Source in graph and edge.Target in graph and edge.Weight>0
        graph.add_edge(edge.Source,edge.Target,weight=edge.Weight)
    betweenness = nx.betweenness_centrality(graph,weight='weight')
    np.testing.assert_allclose(nodes.degree,[graph.degree(n) for n in nodes.id_seudonimizado],rtol=0,atol=1e-12)
    np.testing.assert_allclose(nodes.betweenness_centrality,[betweenness[n] for n in nodes.id_seudonimizado],rtol=0,atol=1e-12)
if args.model:
    import joblib
    from entrenar_twibot import FEATURES
    model = joblib.load(args.model)
    scores = model.predict_proba(s[FEATURES])[:,list(model.classes_).index(1)]
    np.testing.assert_allclose(scores,s.Score_RF_Cuenta,rtol=0,atol=1e-12)

def metrics(y,s,pred):
    precision,recall,_=precision_recall_curve(y,s)
    tn,fp,fn,tp=confusion_matrix(y,pred,labels=[0,1]).ravel()
    return dict(precision=precision_score(y,pred,zero_division=0),recall=recall_score(y,pred,zero_division=0),f1=f1_score(y,pred,zero_division=0),accuracy=accuracy_score(y,pred),roc_auc=roc_auc_score(y,s),pr_auc=auc(recall,precision),TN=int(tn),FP=int(fp),FN=int(fn),TP=int(tp))
y=s.tipo_real.ne('Humano Orgánico');rf=s.Score_RF_Cuenta
net=(s.betweenness_centrality+s.degree/s.groupby('Escenario').degree.transform('max').replace(0,1))/2
full=(.3*rf+.5*net+.1).round(4);bridge=s.betweenness_centrality.ge(.08)
assert np.allclose(full,s.Score_Amenaza_OSINT,rtol=0,atol=1e-12)
configs=[('RF individual (referencia cruzada)',rf,rf.ge(.5),'RF >= 0.5; objetivo sintético distinto de bot/human'),
 ('Red aislada (ablación)',.5*net,bridge|(.5*net).round(4).ge(.35),'0.5*red >= 0.35 O betweenness >= 0.08'),
 ('Fusión sin RF (sin renormalizar)',(.5*net+.1).round(4),bridge|(.5*net+.1).round(4).ge(.35),'0.5*red+0.1 >= 0.35 O betweenness >= 0.08'),
 ('Fusión sin red ni regla puente',(.3*rf+.1).round(4),(.3*rf+.1).round(4).ge(.35),'0.3*RF+0.1 >= 0.35'),
 ('Fusión sin auxiliar (sin renormalizar)',(.3*rf+.5*net).round(4),bridge|(.3*rf+.5*net).round(4).ge(.35),'0.3*RF+0.5*red >= 0.35 O betweenness >= 0.08'),
 ('Fusión completa corregida',full,bridge|full.ge(.35),'0.3*RF+0.5*red+0.1 >= 0.35 O betweenness >= 0.08')]
rows=[]; preds=s[['id_seudonimizado','Escenario','tipo_real']].copy();scenario=[]
for i,(name,sc,pr,rule) in enumerate(configs):
    rows.append(dict(variante=name,regla=rule,**metrics(y,sc,pr)))
    preds[f'score_{i}']=sc;preds[f'pred_{i}']=pr.astype(int)
    for label,idx in s.groupby('Escenario').groups.items():
        tn,fp,fn,tp=confusion_matrix(y.loc[idx],pr.loc[idx],labels=[0,1]).ravel()
        scenario.append(dict(variante=name,escenario=label,TN=int(tn),FP=int(fp),FN=int(fn),TP=int(tp)))

outputs = {'comparacion_componentes.csv':pd.DataFrame(rows),
           'comparacion_por_escenario.csv':pd.DataFrame(scenario),
           'predicciones_componentes.csv':preds}
for name, frame in outputs.items():
    expected = pd.read_csv(root/'resultados_referencia'/name)
    pd.testing.assert_frame_equal(frame,expected,check_dtype=False,atol=1e-12,rtol=0)
args.output.mkdir(parents=True,exist_ok=False)
for name, frame in outputs.items():
    frame.to_csv(args.output/name,index=False)
print(outputs['comparacion_componentes.csv'][['variante','precision','recall','f1','TN','FP','FN','TP']].to_string(index=False))
print('OK: 54 muestras, 81 aristas; métricas de red, fusión y seis variantes coinciden con la referencia.')
print('Los scores RF son resultados guardados; use --model para verificarlos con un modelo local.')

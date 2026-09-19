"""Informe de resultados, tablas y figuras a partir de salidas verificables."""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

P = Path(__file__).resolve().parent
NAMES = {
    'honduras_curado_interno': 'Honduras → Honduras (interno)',
    'uae_curado_interno': 'UAE → UAE (interno)',
    'honduras_curado_a_uae': 'Honduras → UAE (externo)',
    'uae_curado_a_honduras': 'UAE → Honduras (externo)',
    'conjunto_global': 'Modelo conjunto: prueba global',
    'conjunto_honduras': 'Modelo conjunto: prueba Honduras',
    'conjunto_uae': 'Modelo conjunto: prueba UAE',
    'temporal_honduras': 'Temporal Honduras: cuentas nuevas',
    'temporal_uae': 'Temporal UAE: cuentas nuevas',
}


def load(name):
    return json.loads((P/name).read_text())


def table(results, keys):
    lines = ['| Experimento | Cuentas | Positivas | Precisión | Sensibilidad | F1 | AP | FP | FN |',
             '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for k in keys:
        if k not in results:
            continue
        r = results[k]
        lines.append(f"| {NAMES[k]} | {r['n']:,} | {r['positives']:,} | {100*r['precision']:.2f}% | "
                     f"{100*r['recall']:.2f}% | {r['f1']:.4f} | {r['average_precision']:.4f} | {r['fp']} | {r['fn']} |")
    return lines


def main():
    results = {k: load(k+'_resultados.json') for k in NAMES if (P/(k+'_resultados.json')).exists()}
    assert all(k in results for k in list(NAMES)[:7]), 'Faltan experimentos principales'
    audits = {c: load(c+'_full_curado_auditoria.json') for c in ['honduras', 'uae']}
    graphs = {c: load(c+'_coordinacion.json') for c in ['honduras', 'uae']}
    rows = [{'experiment': k, 'description': NAMES[k], **{f: v for f, v in r.items() if not isinstance(v, dict)}}
            for k, r in results.items()]
    pd.DataFrame(rows).to_csv(P/'resumen_metricas.csv', index=False)
    # Mismas cuatro condiciones, con métricas de clase positiva, no exactitud.
    keys = list(NAMES)[:4]; x = np.arange(4); width = .24
    fig, ax = plt.subplots(figsize=(11, 5))
    for j, (metric, label, color) in enumerate([('precision', 'Precisión', '#2c6587'), ('recall', 'Sensibilidad', '#d58241'), ('f1', 'F1', '#519486')]):
        values = [100*results[k][metric] for k in keys]
        bars = ax.bar(x+(j-1)*width, values, width, label=label, color=color)
        ax.bar_label(bars, labels=[f'{v:.1f}' for v in values], padding=3, fontsize=9)
    ax.set_xticks(x, ['Honduras → Honduras', 'UAE → UAE', 'Honduras → UAE', 'UAE → Honduras'])
    ax.set_ylim(0, 115); ax.set_ylabel('Porcentaje'); ax.set_title('El rendimiento interno y la transferencia entre campañas')
    ax.legend(loc='upper center', ncol=3); ax.spines[['top', 'right']].set_visible(False)
    fig.tight_layout(); fig.savefig(P/'comparacion_campanas.png', dpi=170); plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.5))
    for ax, key in zip(axes, keys[2:]):
        r = results[key]; matrix = np.array([[r['tn'], r['fp']], [r['fn'], r['tp']]])
        ax.imshow(np.log1p(matrix), cmap='Blues')
        for i in range(2):
            for j in range(2):
                ax.text(j, i, f'{matrix[i,j]:,}', ha='center', va='center', color='white' if np.log1p(matrix[i,j]) > np.log1p(matrix).max()/2 else 'black', fontsize=13)
        ax.set_xticks([0, 1], ['Referencia', 'Operación']); ax.set_yticks([0, 1], ['Referencia', 'Operación'])
        ax.set_xlabel('Predicción'); ax.set_ylabel('Etiqueta del corpus'); ax.set_title(NAMES[key])
    fig.suptitle('Errores de transferencia — color en escala logarítmica')
    fig.tight_layout(); fig.savefig(P/'matrices_transferencia.png', dpi=170); plt.close(fig)
    medians = []
    for c in ['honduras', 'uae']:
        df = pd.read_csv(P/f'{c}_curado.csv.gz', dtype={'userid': str})
        for label, group in df.groupby('label'):
            medians.append({'campaign': c, 'label': label, **group.drop(columns=['userid', 'label']).median().to_dict()})
    pd.DataFrame(medians).to_csv(P/'medianas_variables.csv', index=False)
    h2u = results['honduras_curado_a_uae']; u2h = results['uae_curado_a_honduras']
    lines = ['# Validación de Honduras y UAE: resultados para el TFM', '',
             'Ejecución local: 18 de septiembre de 2026. Todos los resultados proceden de los archivos descargados; no se han simulado datos ni métricas.', '',
             '**Conclusión:** el clasificador funciona bien dentro de cada campaña, pero su sensibilidad disminuye al aplicarlo a una campaña distinta con el umbral fijado en origen. Se ha realizado una validación externa entre dos campañas; no se ha demostrado un detector universal de perfiles falsos.', '',
             f"En la comparación depurada Honduras → UAE se detectaron {h2u['tp']} de {h2u['positives']} cuentas positivas (sensibilidad {100*h2u['recall']:.2f}%), con {h2u['fp']} falsos positivos. En UAE → Honduras se detectaron {u2h['tp']} de {u2h['positives']} ({100*u2h['recall']:.2f}%), con {u2h['fp']} falsos positivos.", '',
             '## 1. Procedencia y significado de las etiquetas', '',
             'Fuente: Cima et al., *Twitter dataset about Information Operations in Honduras and UAE*, [Zenodo v3](https://zenodo.org/records/13912659). Artículo: [Coordinated Behavior in Information Operations on Twitter](https://doi.org/10.1109/ACCESS.2024.3393482). Los archivos positivos proceden del archivo de operaciones de información de Twitter; los de referencia se recuperaron con búsquedas temáticas. «Referencia» significa ausencia en el conjunto de la operación, no autenticidad individual verificada. La etiqueta positiva tampoco demuestra que cada mensaje sea falso ni que la cuenta sea automatizada.', '',
             '## 2. Auditoría y corrección de la limpieza inicial', '',
             'Los cuatro MD5 coinciden con los publicados. Se conserva una huella SHA-256 local por archivo. Los originales permanecen intactos.', '',
             '| Campaña | Registros originales | Duplicados retirados | Colisiones conservadas | Fuera de periodo | Tweets usados | Cuentas | Positivas |',
             '|---|---:|---:|---:|---:|---:|---:|---:|']
    for c, a in audits.items():
        lines.append(f"| {c} | {sum(a[k]['rows'] for k in ['bad','good']):,} | {sum(a[k]['duplicates_removed'] for k in ['bad','good']):,} | "
                     f"{sum(a[k]['tweetid_collisions_preserved'] for k in ['bad','good']):,} | {sum(a[k]['outside_window_excluded'] for k in ['bad','good']):,} | "
                     f"{a['full']['tweets']:,} | {a['full']['accounts']:,} | {a['full']['positives']:,} |")
    lines += ['', 'La primera ejecución de Honduras eliminaba cualquier repetición de tweetid. La auditoría ampliada comprobó que hay identificadores compartidos por mensajes distintos. Ahora se elimina solo la repetición de tweetid, usuario, fecha y texto; se conservan las colisiones distintas. Por ello cambian los recuentos y algunos resultados respecto al primer informe. Los resultados depurados de este informe son la referencia actual.', '',
              'Las ventanas usadas son [2019-09-10, 2020-01-09) UTC para Honduras y [2019-01-26, 2019-05-27) UTC para UAE. Se incluyen los días iniciales observados en los positivos, que difieren en unas horas de la descripción resumida de Zenodo. En UAE había registros de referencia anteriores, incluso de 2011; se excluyen del conjunto depurado.', '',
              f"Se detectaron {load('solapamiento_curado.json')['shared_userids']} userids compartidos entre campañas. Se excluyen del destino en cada transferencia y de ambas partes del conjunto combinado. La comprobación depende de los identificadores disponibles en el corpus.", '',
              '## 3. Diseño y resultados entre campañas', '',
              'Las 17 variables describen actividad, repetición, uso de entidades y metadatos de perfil. No se usan identificadores, idioma, texto literal, etiqueta good ni nombre de campaña como predictores. Se mantiene el Random Forest original: 300 árboles, mínimo 3 muestras por hoja, max_features=0.8, ponderación balanced_subsample y semilla 42. Cada fuente se divide por cuentas en 60% entrenamiento, 20% validación y 20% prueba; el umbral maximiza F1 solo en validación de origen. La campaña de destino no se usa para elegir umbral o hiperparámetros.', '']
    lines += table(results, keys)
    lines += ['', 'Los tests internos usan el 20% reservado; las transferencias usan todas las cuentas del destino excepto las compartidas. Son poblaciones y prevalencias diferentes: la comparación no es un ensayo pareado con idénticos sujetos.', '',
              '![Comparación](comparacion_campanas.png)', '', '![Matrices](matrices_transferencia.png)', '',
              'La precisión mide qué proporción de alertas coincide con la etiqueta positiva; la sensibilidad mide cuántas cuentas positivas se detectan. Una precisión alta acompañada de sensibilidad baja indica que quedan muchas cuentas de la operación sin detectar. AP evalúa el orden de los scores sin elegir un umbral; su baseline es la prevalencia. No se ajustó retrospectivamente el umbral con las etiquetas del destino.', '',
              'Se utiliza una única partición por experimento. Cambiar el número de cuentas tras depurar los datos cambia la partición aunque se conserve la semilla; también cambia el umbral óptimo de validación. Por tanto, las diferencias respecto al modelo original no pueden atribuirse solo a la corrección de registros. No se ha cuantificado la variabilidad entre semillas.', '',
              '### Comprobación del modelo original congelado', '']
    frozen_path = P/'original_honduras_a_uae_curado_resultados.json'
    if frozen_path.exists():
        frozen = load(frozen_path.name)
        lines += [f"El modelo de la primera ejecución, conservado sin modificar, obtuvo sobre UAE depurado precisión {100*frozen['precision']:.2f}%, sensibilidad {100*frozen['recall']:.2f}% y F1 {frozen['f1']:.4f}: {frozen['tp']} detectadas, {frozen['fn']} no detectadas y {frozen['fp']} falsos positivos. La conclusión de pérdida de sensibilidad no depende solo del reentrenamiento tras corregir la limpieza.", '']
    else:
        lines += ['La comparación con el modelo histórico se omite cuando los artefactos privados de entrenamiento_honduras no están disponibles. No interviene en las métricas depuradas principales.', '']
    lines += ['## 4. Entrenamiento combinado', '',
              'Se mezclan las cuentas de ambas campañas y se estratifica por campaña y etiqueta. Cada usuario aparece en una única partición. Esto evalúa cuentas nuevas de dos campañas ya conocidas; no equivale a validar en una tercera campaña desconocida.', '']
    lines += table(results, ['conjunto_global', 'conjunto_honduras', 'conjunto_uae'])
    lines += ['', '## 5. Evaluación temporal', '',
              'Se recalculan las variables separadamente antes y después de los cortes 2019-11-10 UTC (Honduras) y 2019-03-28 UTC (UAE). Dentro del periodo inicial se entrena con el 80% de las cuentas y se selecciona el umbral con el 20% restante. La evaluación posterior excluye todas las cuentas ya vistas en el periodo inicial, incluidas las de validación.', '']
    lines += table(results, ['temporal_honduras', 'temporal_uae'])
    for c in ['honduras', 'uae']:
        info = load(f'temporal_{c}_poblacion.json')
        lines.append(f"\n{c.upper()}: {info['early_accounts']:,} cuentas iniciales; {info['late_accounts']:,} posteriores; {info['excluded_seen_accounts']:,} posteriores excluidas por haber aparecido antes; {info['late_unseen_accounts']:,} nuevas, con {info['late_unseen_positives']} positivas.")
        if 'temporal_'+c not in results:
            lines.append('No fue posible calcular una evaluación binaria representativa con ambas clases; revisar población y registro de ejecución.')
        elif info['late_unseen_positives'] < 30:
            lines.append('**Muestra positiva muy pequeña:** las métricas temporales son inestables; cada cuenta tiene gran impacto en la sensibilidad. No usar este resultado como evidencia sólida de generalización temporal.')
    lines += ['', 'Esta es una prueba retrospectiva con la ventana posterior completa. No mide el tiempo hasta la primera alerta, y los contadores de seguidores del corpus podrían reflejar la fecha de recogida, no la de publicación. Por ello no constituye una demostración de alerta temprana en producción. UAE precede cronológicamente a Honduras: Honduras → UAE es transferencia entre contextos, no predicción hacia el futuro.', '',
              '## 6. Redes de coincidencia temporal de mensajes', '',
              'Se conecta una pareja cuando comparte al menos tres textos idénticos diferentes en los mismos intervalos fijos de 60 segundos. Se cuentan textos distintos, aunque aparezcan en varios intervalos. Se omiten textos de menos de 30 caracteres y eventos de más de 50 usuarios. Las etiquetas no intervienen en la creación de enlaces. Son redes exploratorias de coincidencia repetida, no prueba de intención maliciosa.', '',
              '| Campaña | Nodos | Enlaces | Componentes | Nodos positivos | Nodos de referencia | Cobertura de positivos |',
              '|---|---:|---:|---:|---:|---:|---:|']
    for c, g in graphs.items():
        lines.append(f"| {c} | {g['nodes']:,} | {g['edges']:,} | {g['components']:,} | {g['positive_nodes']:,} | {g['reference_nodes']:,} | {100*g['positive_coverage']:.2f}% |")
    lines += ['', '![Grafo Honduras](honduras_grafo.png)', '', '![Grafo UAE](uae_grafo.png)', '',
              'Las figuras muestran una selección de hasta 150 nodos, priorizando grado y componentes mayores; la red completa está en GraphML y CSV. Los nodos aislados no se incluyen. Los límites de intervalo pueden separar publicaciones cercanas; los textos truncados, el idioma, la popularidad del mensaje y la selección de eventos afectan a la red. No se controló estadísticamente una hipótesis nula de coincidencia ni se ajustó por múltiples comparaciones. Las cifras de cobertura son descriptivas del corpus completo, no métricas de un clasificador probado en un test independiente. No se fusionaron estas señales con el clasificador evaluado.', '',
              '## 7. Interpretación para la memoria', '',
              'La evaluación aporta evidencia de que una validación aleatoria dentro de una misma campaña puede sobreestimar la utilidad fuera de ese contexto. Se observa buena separación interna y una pérdida de sensibilidad en ambas transferencias con umbrales fijados en origen. La combinación de campañas amplía la representación del entrenamiento, pero su prueba interna no resuelve por sí misma la generalización a nuevas operaciones.', '',
              'Los grafos complementan la clasificación individual con agrupaciones de comportamiento compartido y permiten orientar una revisión OSINT. La etiqueta del corpus debe usarse como referencia experimental, sin equiparar coincidencia temporal, perfil falso, bot y desinformación.', '',
              'Persisten sesgos de recogida entre positivos y referencia, dependencia entre cuentas de una misma operación, diferencias de idioma y cobertura, y ausencia de verificación individual de las cuentas de referencia. Las diferencias de medianas se exportan en medianas_variables.csv; no demuestran por sí solas qué factor causa el cambio de rendimiento.', '',
              'Los JSON incluyen intervalos del 95% por bootstrap estratificado de 2.000 réplicas equivalentes sobre la matriz de confusión para precisión, sensibilidad y F1, con modelo y umbral fijos. No incluyen variabilidad de reentrenamiento ni dependencia entre cuentas. La exactitud de un baseline que siempre responde referencia es 1 − prevalencia y tiene sensibilidad y F1 nulos.', '',
              'El siguiente estudio justificable es reservar una tercera campaña completamente intacta y validar en ella un método fijado con Honduras y UAE, incluyendo selección de señales de coordinación solo con datos de desarrollo. También hace falta una simulación por ventanas cortas y metadatos disponibles en cada momento para sostener una afirmación de alerta temprana.', '',
              '## 8. Entregables y reproducción', '',
              '- resumen_metricas.csv: comparación numérica; *_resultados.json: métricas, errores y umbrales.',
              '- *_modelo.joblib: modelos entrenados; *_predicciones.csv.gz: scores y decisiones por cuenta.',
              '- *_particiones.csv.gz: asignación auditable a entrenamiento, validación y prueba.',
              '- *_curado.csv.gz: variables por cuenta; *_early.csv.gz / *_late.csv.gz: ventanas temporales.',
              '- *_coordinacion.graphml.gz: redes completas para herramientas de grafos; *_aristas.csv.gz / *_nodos.csv.gz / *_componentes.csv: tablas de red.',
              '- *_auditoria.json, PROTOCOLO.md y versiones.json: integridad, decisiones y entorno.',
              '- preparar.py, experimentos.py, coordinacion.py, informe.py, verificar.py: código de ejecución y controles.', '',
              'Los nombres sin «curado» del primer experimento cruzado se conservan como referencia histórica. Para nuevas conclusiones, usar las filas depuradas de resumen_metricas.csv.', '',
              'Desde la raíz del proyecto, con el entorno .venv de la primera ejecución:', '',
              '```bash',
              '.venv/bin/python validacion_campanas/preparar.py honduras --data-dir /ruta/a/zenodo',
              '.venv/bin/python validacion_campanas/preparar.py uae --data-dir /ruta/a/zenodo',
              '.venv/bin/python validacion_campanas/preparar.py honduras --mode temporal --data-dir /ruta/a/zenodo',
              '.venv/bin/python validacion_campanas/preparar.py uae --mode temporal --data-dir /ruta/a/zenodo',
              'OMP_NUM_THREADS=3 OPENBLAS_NUM_THREADS=3 .venv/bin/python validacion_campanas/experimentos.py curated',
              'OMP_NUM_THREADS=3 OPENBLAS_NUM_THREADS=3 .venv/bin/python validacion_campanas/experimentos.py combined',
              'OMP_NUM_THREADS=3 OPENBLAS_NUM_THREADS=3 .venv/bin/python validacion_campanas/experimentos.py temporal',
              'MPLCONFIGDIR=/tmp/tfm-matplotlib .venv/bin/python validacion_campanas/coordinacion.py honduras --data-dir /ruta/a/zenodo',
              'MPLCONFIGDIR=/tmp/tfm-matplotlib .venv/bin/python validacion_campanas/coordinacion.py uae --data-dir /ruta/a/zenodo',
              'MPLCONFIGDIR=/tmp/tfm-matplotlib .venv/bin/python validacion_campanas/informe.py',
              '.venv/bin/python validacion_campanas/verificar.py',
              '```', '',
              'Conservar el READ.ME original al redistribuir datos y su aviso de uso para investigación. Los scores no son probabilidades calibradas de autenticidad ni de culpabilidad.']
    (P/'INFORME_TFM.md').write_text('\n'.join(lines)+'\n')
    print(pd.DataFrame(rows)[['description', 'precision', 'recall', 'f1', 'tp', 'fp', 'fn']].to_string(index=False))


if __name__ == '__main__':
    main()

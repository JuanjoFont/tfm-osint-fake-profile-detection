# Datos y método

## Diccionario de muestras

Una fila corresponde a una entidad ficticia. Se conservan todas las columnas del CSV revisado salvo `username`.

| Columnas | Significado |
|---|---|
| `id_seudonimizado` | Identificador sintético estable `User_…`, no identificador de TwiBot |
| `Escenario`, `tipo_real` | Escenario y rol asignados por el generador, no anotación independiente |
| `followers_count`, `following_count`, `tweet_count`, `listed_count` | Contadores sintéticos del perfil |
| `ratio_rep` | Seguidores / (seguidos + 1) |
| `antiguedad_dias` | Antigüedad en días; TwiBot usa como referencia 2022-06-01 UTC |
| `has_description`, `has_location`, `has_url`, `verified`, `protected` | Indicadores 0/1 |
| `len_description` | Longitud de la descripción; no se incluyen textos personales |
| `degree`, `betweenness_centrality` | Grado e intermediación calculados sobre la red del escenario |
| `cluster_comunidad` | Identificador histórico de comunidad, no entra en la fusión |
| `Score_RF_Cuenta` | Score guardado del RF entrenado en TwiBot; verificable con `--model` |
| `score_botometer`, `origen_score_botometer` | Sustituto constante 0,5, sin consulta externa |
| `Score_Amenaza_OSINT`, `Clasificacion_Final` | Score integrado y decisión guardados |
| `cohorte`, `origen_etiqueta` | Procedencia sintética |

Las aristas contienen `Escenario`, `Source`, `Target`, `Weight`. Se reconstruye un grafo no dirigido por escenario, añadiendo también los nodos aislados de la tabla de muestras. Los pares ya están agregados. Se conservaron 12, 10, 14, 8 y 10 nodos, con 11, 29, 27, 10 y 4 aristas respectivamente.

## Cálculos conservados

```text
red = (betweenness + degree / max_degree_del_escenario) / 2
score = round(0.30 * RF + 0.50 * red + 0.20 * 0.5, 4)
positivo = betweenness >= 0.08 OR score >= 0.35
```

La referencia sintética es `tipo_real != 'Humano Orgánico'`: 35 positivos y 19 negativos. Incluye roles que no son necesariamente bots. El código usa `tipo_real` exclusivamente para evaluar, no como característica del RF ni para calcular el auxiliar.

Para reproducir el cálculo histórico, NetworkX recibe `weight='weight'` en intermediación y trata el peso como distancia. Los pesos se originaron como intensidades de interacción: esa interpretación es una limitación del diseño original. Cambiar a distancia inversa requiere otro experimento y nuevas cifras. Las comunidades históricas se obtuvieron con modularidad voraz; sus números identificadores son arbitrarios y no intervienen en los resultados evaluados.

La muestra original se generó sin una semilla histórica recuperable. Una semilla añadida después no reconstruye sus metadatos y enlaces. Por eso se distribuyen los datos y aristas exactos, no se afirma regeneración desde semilla.

## Trazabilidad y límites de reproducción

Las aristas proceden de los cinco GEXF históricos, contrastados con grado e intermediación de todas las filas. El script de reproducción recalcula estas métricas y comprueba las tres tablas sintéticas de referencia completas. Con `--model` también recalcula los 54 scores RF. El entrenamiento portátil conserva el algoritmo, las variables, el orden de entrada y la separación train/test del script revisado; cambia rutas y selección de archivos para ejecutarse fuera de la VM original.

Las métricas reales publicadas son agregadas de la ejecución original. Para recalcularlas se necesita el dataset oficial; el paquete por sí solo no permite verificar los 100.000 scores reales. El entrenamiento no mezcla muestras sintéticas con train ni incorpora test a train.

Las fechas no interpretables se convierten a antigüedad 0 y las antigüedades negativas se recortan a 0, como en la ejecución original. `has_url` se deriva de `entities.url`. PR-AUC trapezoidal y average precision se exportan por separado y no son intercambiables. Cuando no hay positivos predichos, la precisión se informa como 0 por convenio computacional.

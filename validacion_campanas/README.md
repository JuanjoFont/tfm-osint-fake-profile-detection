# Reproducción de la validación Honduras/UAE

Este directorio contiene la ampliación experimental con las campañas de Honduras y UAE del corpus publicado en Zenodo 13912659. Los cuatro archivos originales no se redistribuyen; deben descargarse desde la fuente y conservar estos nombres:

- `honduras-bad-anonymized`
- `honduras-good-anonymized`
- `uae-bad-anonymized`
- `uae-good-anonymized`

Los scripts verifican los MD5 publicados antes de procesar los datos. El argumento `--data-dir` permite indicar cualquier carpeta de entrada y evita depender de rutas locales del autor.

## Entorno

La ejecución registrada utilizó Python 3.14.4, scikit-learn 1.9.1, NumPy 2.3.5 y pandas 2.3.3. Las versiones exactas están en `versiones.json`.

Desde la raíz del proyecto:

```bash
source .venv/bin/activate
export OMP_NUM_THREADS=3
export OPENBLAS_NUM_THREADS=3
export MKL_NUM_THREADS=3
```

## Preparación de cuentas

Sustituya `/ruta/a/zenodo` por la carpeta que contiene los cuatro archivos:

```bash
python validacion_campanas/preparar.py honduras --data-dir /ruta/a/zenodo
python validacion_campanas/preparar.py uae --data-dir /ruta/a/zenodo
python validacion_campanas/preparar.py honduras --mode temporal --data-dir /ruta/a/zenodo
python validacion_campanas/preparar.py uae --mode temporal --data-dir /ruta/a/zenodo
```

La preparación comprueba integridad, elimina duplicados exactos, conserva colisiones distintas de `tweetid`, aplica las ventanas documentadas y excluye identidades con etiquetas contradictorias.

## Experimentos

```bash
python validacion_campanas/experimentos.py curated
python validacion_campanas/experimentos.py combined
python validacion_campanas/experimentos.py temporal
python validacion_campanas/coordinacion.py honduras --data-dir /ruta/a/zenodo
python validacion_campanas/coordinacion.py uae --data-dir /ruta/a/zenodo
python validacion_campanas/fusion_real.py
python validacion_campanas/informe.py
python validacion_campanas/verificar.py
```

`curated` ejecuta evaluación interna y transferencia cruzada; `combined` prueba una mezcla de campañas conocidas; `temporal` evalúa cuentas nuevas en la ventana posterior. `coordinacion.py` construye redes exploratorias sin usar las etiquetas para crear enlaces. `fusion_real.py` combina la probabilidad del clasificador y el grado de la red, seleccionando peso y umbral únicamente en validación y evaluando una sola vez en test.

## Interpretación

Las etiquetas distinguen cuentas incluidas en una operación documentada y cuentas de referencia. No equivalen por sí solas a bot/humano, identidad verdadera/falsa ni contenido verdadero/desinformación. La fusión real es una evaluación retrospectiva y transductiva de dos señales: la red se obtiene de la ventana completa sin utilizar etiquetas para crear enlaces. Por ello no constituye una prueba de alerta temprana ni una validación prospectiva.

La comprobación final debe terminar con `status: passed` en `verificacion.json`. El verificador recalcula matrices y AP, reproduce muestras de scores a partir de los modelos guardados, comprueba la separación de particiones y valida los ficheros de nodos y aristas.

## Rendimiento y escalabilidad observada

`rendimiento_entorno.csv` registra tiempos de pared y máximo de memoria residente medidos con `/usr/bin/time -v` en la máquina virtual documentada. La preparación secuencial pasó de 1.262.830 a 2.849.468 registros y de 35,36 a 93,57 segundos; el máximo de memoria pasó de 1,14 a 2,13 GiB. La construcción de coordinación pasó de 15,12 a 37,95 segundos. Son dos puntos de carga reales, suficientes para describir el comportamiento observado, pero no para afirmar complejidad asintótica ni capacidad ilimitada. El coste depende además del número de eventos repetidos y pares candidatos, no solo del número de mensajes. Las APIs externas quedan fuera de esta medición y conservan sus límites de cuota y disponibilidad.

La comparación `cross` de la primera ejecución y la comprobación con el modelo histórico congelado son opcionales. Requieren artefactos de `entrenamiento_honduras` que contienen información por cuenta y no se incluyen en el paquete público. Las etapas `curated`, `combined` y `temporal` son independientes de esos artefactos.

## Exclusiones del paquete público

No deben subirse los cuatro archivos originales, tablas por cuenta, particiones, predicciones, modelos serializados, grafos con identificadores, registros de ejecución, claves ni ficheros `.env`. El repositorio público conserva código, protocolo, auditorías agregadas, métricas agregadas y figuras sin identificadores visibles.

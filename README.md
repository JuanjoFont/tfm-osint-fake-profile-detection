# TFM: detección de cuentas y análisis de coordinación

Código de reproducción de la evaluación revisada del TFM **Identificación de perfiles falsos y campañas de desinformación mediante técnicas OSINT**.

Se distinguen tres bloques: un Random Forest evaluado en TwiBot-22, una demostración de fusión en cinco escenarios sintéticos y una ampliación con las campañas reales de Honduras y UAE. En estas campañas se evalúan por separado clasificadores de cuenta y grafos exploratorios de coincidencia temporal; no se presenta todavía una fusión real de ambas señales.

## Reproducción rápida sin descargar datos

Desde la raíz de esta carpeta, con Python 3.14.4 (versión del experimento):

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python scripts/reproducir_sintetico.py
```

Tras instalar las dependencias, la reproducción funciona sin red ni claves API. Comprueba las 54 muestras, reconstruye los cinco grafos a partir de 81 aristas y verifica grado, intermediación, fusión y seis variantes contra los resultados guardados. Exporta tres CSV en `salidas/reproduccion/`. Para repetir, indique una carpeta nueva mediante `--output salidas/otra_ejecucion`.

**Esta orden reutiliza los scores RF guardados. No reentrena el modelo.** La extracción de características y el entrenamiento completo están en `scripts/entrenar_twibot.py`.

## Contenido

| Ruta | Contenido |
|---|---|
| `scripts/reproducir_sintetico.py` | Verificación de topologías, integración y ablaciones |
| `scripts/entrenar_twibot.py` | Lectura incremental, extracción de 12 variables, entrenamiento y evaluación |
| `datos/muestras_sinteticas_54.csv` | Las 54 filas utilizadas, con variables, roles y scores; se elimina únicamente el alias `username` |
| `datos/aristas_sinteticas.csv` | Las 81 aristas recuperadas de los cinco grafos originales y verificadas contra sus métricas |
| `resultados_referencia/` | Métricas agregadas reales, resultados sintéticos y figura de evaluación |
| `docs/DATOS_Y_METODO.md` | Diccionario, procedencia y límites |
| `docs/procedencia.json` | Versiones, parámetros y hashes de entradas originales |
| `validacion_campanas/` | Código, protocolo, métricas agregadas y figuras de Honduras/UAE |
| `MANIFEST_SHA256.json` | Integridad de los archivos entregados |

## Resultados esperados

| Evaluación | N | Precisión | Recall | F1 | TN / FP / FN / TP |
|---|---:|---:|---:|---:|---|
| RF, test real TwiBot-22 | 100.000 | 0,7454 | 0,2654 | 0,3914 | 67.887 / 2.669 / 21.631 / 7.813 |
| Fusión, escenarios sintéticos | 54 | 0,9375 | 0,4286 | 0,5882 | 18 / 1 / 20 / 15 |

El RF obtiene ROC-AUC 0,7536 y PR-AUC trapezoidal 0,5853. En el experimento sintético, RF aislado da F1 0,4091 y red aislada 0,2500. Los objetivos son distintos: `bot/human` en TwiBot y rol sintético frente a orgánico en la demostración; no se calcula una métrica conjunta ni se comparan ambas filas como si fueran el mismo problema.

La ampliación Honduras/UAE obtiene F1 interno de 0,9578 y 0,9590. Al transferir los modelos entre campañas, la sensibilidad desciende a 49,57 % y 27,92 %, con F1 de 0,6459 y 0,4318. Consulte [`validacion_campanas/README.md`](validacion_campanas/README.md) para descargar los originales desde Zenodo y ejecutar el protocolo depurado.

## Reentrenar con TwiBot-22

Obtenga `user.json`, `label.csv` y `split.csv` siguiendo las instrucciones del [repositorio oficial de TwiBot-22](https://github.com/LuoUndergradXJTU/TwiBot-22). Los archivos originales y las predicciones por cuenta real no se redistribuyen aquí. El README oficial describe un procedimiento de solicitud de acceso; la licencia del código del repositorio no se toma como permiso para redistribuir los registros.

```bash
python scripts/entrenar_twibot.py --data-dir /ruta/TwiBot-22 --output salidas/reentrenamiento
python scripts/reproducir_sintetico.py --model salidas/reentrenamiento/modelo_rf_cuenta.pkl --output salidas/verificacion_modelo
```

El entrenamiento usa exclusivamente las 700.000 cuentas de `train`, mantiene las 200.000 de `val` sin ajustes y evalúa las 100.000 de `test`. Son 100 árboles, profundidad máxima 12, semilla 42 y umbral 0,5. Usa CPU, memoria para la tabla de un millón de cuentas y espacio para los originales; no se requiere GPU. No se ha fijado un mínimo de RAM mediante pruebas de capacidad.

La segunda orden verifica que el modelo reproduce los scores históricos con tolerancia 1e-12. Para buscar coincidencia numérica, mantenga las versiones fijadas y los hashes de los tres archivos registrados en `docs/procedencia.json`. Otras versiones u otros datos pueden dar diferencias: no sustituya las referencias para ocultarlas. Cargue con `--model` únicamente un modelo local de confianza.

Se generan métricas, curvas, importancias, modelo, predicciones individuales y manifiesto en la carpeta de salida. Los identificadores reales se sustituyen mediante HMAC-SHA256 con una clave local en `.private/`. Las salidas y esa clave están excluidas mediante `.gitignore` y no forman parte del paquete público.

## Alcance y publicación

Las muestras sintéticas son las usadas, no ejemplos nuevos generados con otra semilla. Las aristas y metadatos son ficticios. No se atribuyen sus etiquetas a personas reales. TwiBot contiene datos reales, pero su tarea es `bot/human`. Honduras y UAE permiten estudiar pertenencia a operaciones documentadas y transferencia entre contextos; sus etiquetas no certifican individualmente que una cuenta sea falsa, automatizada o responsable de desinformación.

El auxiliar denominado `score_botometer` vale 0,5 para todas las filas: no es una respuesta de Botometer. No se utiliza `tipo_real` para generar scores. Las ablaciones mantienen los pesos restantes y los umbrales, por lo que también cambia la escala. No permiten atribuir causalmente una ganancia a un componente.

El paquete no incluye credenciales, datos crudos de terceros, identificadores del corpus, predicciones por cuenta, particiones ni modelos serializados. Antes de publicar, el titular debe elegir una licencia para el código. Las dependencias y los conjuntos de terceros conservan sus propias licencias y condiciones de uso.

# Comprobaciones del entregable

- Las 54 filas coinciden con el CSV revisado salvo la retirada de `username`.
- Los cinco grafos recuperados contienen 81 aristas. Su grado e intermediación coinciden en todas las filas con los resultados históricos, con tolerancia absoluta 1e-12.
- Las tres tablas sintéticas de salida se comparan completas con las referencias: seis variantes, resultados por escenario y scores/predicciones individuales sintéticos.
- Se recalcularon los 54 scores utilizando el modelo local del experimento original. Coinciden con las referencias con tolerancia absoluta 1e-12.
- Se ejecutó el entrenamiento portátil completo con un conjunto ficticio de prueba de 80 cuentas, separado en 40 train, 20 val y 20 test. Se comprobaron las exportaciones de 54 entidades sintéticas, 20 predicciones test, métricas y manifiesto. Es una prueba funcional del programa, no un nuevo resultado científico; esas cuentas de prueba no se distribuyen como muestras del TFM.
- Se verificó la sintaxis de los dos scripts y la ejecución sin modelo desde el paquete.

Se verificó una reconstrucción limpia del entorno Python 3.14.4: se creó un entorno virtual nuevo, se instalaron de nuevo las dependencias fijadas en `requirements.txt`, el manifiesto de 65 archivos se validó y `scripts/reproducir_sintetico.py` reprodujo las 54 muestras, 81 aristas y seis variantes de referencia. La guía completa de la máquina virtual está en [ENTORNO_VIRTUALBOX.md](ENTORNO_VIRTUALBOX.md).

Además, se repitió de extremo a extremo la validación Honduras/UAE con las versiones exactas de `validacion_campanas/requirements.txt`: verificación MD5 de los cuatro originales, preparación completa y temporal, entrenamiento interno, transferencia, entrenamiento combinado, redes, fusión real e informe. `validacion_campanas/verificar.py` recalculó todas las matrices y AP, reprodujo muestras de scores con los modelos recargados, comprobó la separación de particiones y verificó las dos fusiones reales. El resultado final quedó registrado como `status: passed`.

La repetición completa detectó que algunas métricas agregadas conservadas previamente no coincidían con la ejecución actual de los scripts. Se sustituyeron por los resultados regenerados con el entorno fijado y se actualizó el manifiesto. Los datos originales, modelos, particiones y predicciones por cuenta permanecen excluidos del paquete público.

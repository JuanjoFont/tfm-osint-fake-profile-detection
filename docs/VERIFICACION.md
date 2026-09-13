# Comprobaciones del entregable

- Las 54 filas coinciden con el CSV revisado salvo la retirada de `username`.
- Los cinco grafos recuperados contienen 81 aristas. Su grado e intermediación coinciden en todas las filas con los resultados históricos, con tolerancia absoluta 1e-12.
- Las tres tablas sintéticas de salida se comparan completas con las referencias: seis variantes, resultados por escenario y scores/predicciones individuales sintéticos.
- Se recalcularon los 54 scores utilizando el modelo local del experimento original. Coinciden con las referencias con tolerancia absoluta 1e-12.
- Se ejecutó el entrenamiento portátil completo con un conjunto ficticio de prueba de 80 cuentas, separado en 40 train, 20 val y 20 test. Se comprobaron las exportaciones de 54 entidades sintéticas, 20 predicciones test, métricas y manifiesto. Es una prueba funcional del programa, no un nuevo resultado científico; esas cuentas de prueba no se distribuyen como muestras del TFM.
- Se verificó la sintaxis de los dos scripts y la ejecución sin modelo desde el paquete.

No se repitió el entrenamiento de un millón de cuentas al preparar este entregable, ni se probó una instalación limpia descargando nuevamente todas las dependencias. Las comprobaciones se ejecutaron con las versiones fijadas en el entorno existente. Los resultados reales de referencia corresponden a la ejecución original.

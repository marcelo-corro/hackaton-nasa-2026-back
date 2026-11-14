"""Armonización MODIS <-> VIIRS (pendiente).

Objetivo: que el sensor de origen deje de importar y la serie 2000-hoy sea comparable.

Ojo, no sumar satélites que ven lo mismo: Suomi NPP y NOAA-20 pasan con ~50 min de diferencia y detectan
los mismos incendios (Viña del Mar, feb-2024: SNPP 117 focos, NOAA-20 127). Sumarlos cuenta cada incendio
dos veces. Tratar cada satélite como serie propia (lo mismo vale para Terra y Aqua dentro de MODIS si se
compara por satélite).

La razón entre sensores NO es estable (ver docs/calidad_datos.md): las órbitas de Terra y Aqua se desvían
~1 h desde 2020-2022 y la versión de procesamiento de MODIS cambia en 2018 y 2023. Con `uso_base`,
SNPP/MODIS va de ~3,1-3,5 (2013-2021) a 3,8-4,2 (2022-2025); SNPP/Terra llega a 17 en 2025.
Entrada: data/interim/focos_calidad.parquet, filtrado por `uso_base` y contado por `fecha_local`.

Plan:
1. Período de traslape: 2012-03 a 2025 (MODIS y VIIRS-SNPP a la vez); NOAA-20 desde 2018-04 sirve para
   calibrar la continuidad de la serie VIIRS cuando Suomi NPP deja de entregar datos.
   Calibrar por satélite (Terra y Aqua por separado) y dejar que el factor varíe en el tiempo
   (por período de órbita/versión o con una tendencia), no un único número.
2. Métodos a comparar:
   - factor único (línea base, para mostrar por qué falla),
   - razón por zona y mes (medida por el equipo: norte 10,1; centro 3,83; centro-sur 3,14; sur 3,94),
   - quantile mapping por celda,
   - modelo de conteo (Poisson / binomial negativa) con efecto sensor x zona x mes x cobertura de suelo.
3. Validación fuera de muestra: calibrar con 2012-2018 y probar con 2019-2025.
4. Entregar la serie armonizada con intervalo de incertidumbre (p05-p95).
"""

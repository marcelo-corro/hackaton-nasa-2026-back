"""Armonización MODIS <-> VIIRS (pendiente).

Objetivo: que el sensor de origen deje de importar y la serie 2000-hoy sea comparable.

Plan:
1. Período de traslape: 2012-03 a 2025 (MODIS y VIIRS-SNPP a la vez).
2. Métodos a comparar:
   - factor único (línea base; ya se midió ~3,3 en Chile),
   - razón por zona y mes (medida por el equipo: norte 10,1; centro 3,83; centro-sur 3,14; sur 3,94),
   - quantile mapping por celda,
   - modelo de conteo (Poisson / binomial negativa) con efecto sensor x zona x mes x cobertura de suelo.
3. Validación fuera de muestra: calibrar con 2012-2018 y probar con 2019-2025.
4. Entregar la serie armonizada con intervalo de incertidumbre (p05-p95).
"""

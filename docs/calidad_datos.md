# Reporte de calidad de los focos FIRMS
_Generado por `scripts/04_marcar_calidad.py` el 2026-11-21 16:28 UTC. No editar a mano: se regenera._

## 1. Integridad
- Focos: **916 542**, del 2000-11-01 al 2026-11-14.
- Duplicados exactos (lat, lon, fecha, hora, satélite): **0**.
- Coordenadas fuera del rango de Chile (incluye Isla de Pascua): **0**.
- Focos cuyo día local es distinto al día UTC: **0.7 %** (usar `fecha_local` en series diarias).

Valores nulos (la confianza numérica solo existe en MODIS):

|  | nulos |
|---|---|
| confianza_modis | 726 825 |
| region_id | 46 578 |
| asignacion | 46 578 |

## 2. Tipos de foco por sensor (%)
Tipo 0 = vegetación, 1 = volcán, 2 = otra fuente fija (industria, faenas), 3 = costa afuera.

| sensor | tipo 0 | tipo 1 | tipo 2 | tipo 3 |
|---|---|---|---|---|
| MODIS | 79.65 | 1.54 | 18.78 | 0.03 |
| VIIRS | 82.40 | 1.44 | 15.86 | 0.30 |

## 3. Marcas de calidad por satélite (% de focos)

| satelite | es_vegetacion | confianza_ok | frp_valido | pixel_grande | fuente_persistente | uso_base |
|---|---|---|---|---|---|---|
| Aqua | 87.3 | 94.7 | 100.0 | 31.4 | 1.2 | 82.4 |
| NOAA20 | 83.6 | 89.9 | 99.9 | 20.2 | 4.6 | 71.6 |
| SNPP | 81.7 | 91.6 | 99.9 | 20.6 | 3.8 | 71.9 |
| Terra | 67.4 | 88.8 | 100.0 | 25.7 | 2.1 | 59.3 |

## 4. Versiones del producto
La versión indica la colección y el tipo de procesamiento (documentación de FIRMS). Cambios de versión pueden producir saltos en la serie.

|  | focos | desde | hasta |
|---|---|---|---|
| Aqua / 6.03 | 22 508 | 2018-01-01 | 2022-12-31 |
| Aqua / 6.2 | 77 155 | 2002-07-04 | 2017-12-31 |
| Aqua / 61.03 | 16 982 | 2023-01-01 | 2025-12-31 |
| NOAA20 / 2 | 253 275 | 2018-04-01 | 2026-07-31 |
| NOAA20 / 2.0NRT | 9 772 | 2026-08-01 | 2026-11-14 |
| SNPP / 2 | 454 784 | 2012-01-20 | 2026-07-31 |
| SNPP / 2.0NRT | 8 994 | 2026-08-01 | 2026-11-01 |
| Terra / 6.03 | 15 871 | 2018-01-01 | 2022-12-31 |
| Terra / 6.2 | 44 478 | 2000-11-01 | 2017-12-31 |
| Terra / 61.03 | 12 723 | 2023-01-01 | 2025-12-31 |

## 5. Deriva de órbita: hora UTC mediana del paso diurno (focos `uso_base`)
Terra y Aqua (MODIS) se están desviando de su órbita original; Suomi NPP y NOAA-20 (VIIRS) no.

| año | Aqua | NOAA20 | SNPP | Terra |
|---|---|---|---|---|
| 2000 | — | — | — | 14.98 |
| 2001 | — | — | — | 15.12 |
| 2002 | 18.77 | — | — | 15.02 |
| 2003 | 18.75 | — | — | 14.97 |
| 2004 | 18.87 | — | — | 14.88 |
| 2005 | 18.83 | — | — | 14.93 |
| 2006 | 18.78 | — | — | 14.95 |
| 2007 | 18.82 | — | — | 14.97 |
| 2008 | 18.88 | — | — | 14.97 |
| 2009 | 18.88 | — | — | 14.95 |
| 2010 | 18.92 | — | — | 14.97 |
| 2011 | 18.82 | — | — | 14.97 |
| 2012 | 18.80 | — | 18.78 | 14.95 |
| 2013 | 18.90 | — | 18.80 | 14.97 |
| 2014 | 18.90 | — | 18.95 | 14.97 |
| 2015 | 18.82 | — | 18.88 | 14.97 |
| 2016 | 18.80 | — | 18.83 | 14.97 |
| 2017 | 18.83 | — | 18.80 | 14.98 |
| 2018 | 18.82 | 18.70 | 18.80 | 14.98 |
| 2019 | 18.90 | 18.82 | 18.80 | 14.97 |
| 2020 | 18.90 | 18.80 | 18.80 | 14.87 |
| 2021 | 18.90 | 18.82 | 18.80 | 14.90 |
| 2022 | 18.88 | 18.82 | 18.82 | 14.70 |
| 2023 | 19.05 | 18.90 | 18.85 | 14.45 |
| 2024 | 19.38 | 18.83 | 18.73 | 14.23 |
| 2025 | 19.77 | 18.85 | 18.92 | 13.97 |
| 2026 | — | 18.75 | 18.75 | — |

## 6. Razones anuales entre satélites (focos `uso_base`)
Si la razón cambia con los años, un factor calibrado con todo el período no sirve: hay que calibrar en el período en que ambos sensores son estables (ver [armonizacion.md](armonizacion.md)).

| año | SNPP/Terra | SNPP/Aqua | SNPP/MODIS | NOAA20/SNPP |
|---|---|---|---|---|
| 2012 | 9.09 | 3.40 | 2.47 | — |
| 2013 | 13.27 | 4.09 | 3.13 | — |
| 2014 | 9.93 | 4.73 | 3.20 | — |
| 2015 | 11.58 | 4.88 | 3.43 | — |
| 2016 | 10.11 | 4.57 | 3.15 | — |
| 2017 | 8.36 | 5.02 | 3.13 | — |
| 2018 | 15.57 | 4.39 | 3.42 | 0.54 |
| 2019 | 12.01 | 4.73 | 3.39 | 0.99 |
| 2020 | 10.22 | 5.26 | 3.47 | 0.97 |
| 2021 | 11.10 | 4.83 | 3.37 | 1.02 |
| 2022 | 12.00 | 6.13 | 4.06 | 0.95 |
| 2023 | 8.31 | 5.77 | 3.40 | 0.93 |
| 2024 | 12.92 | 5.02 | 3.62 | 1.02 |
| 2025 | 16.95 | 5.25 | 4.01 | 0.98 |

Sensibilidad de la razón SNPP/MODIS al filtro de confianza:

| año | uso_base | solo vegetación (con baja confianza) |
|---|---|---|
| 2012 | 2.47 | 2.47 |
| 2013 | 3.13 | 3.01 |
| 2014 | 3.20 | 3.14 |
| 2015 | 3.43 | 3.42 |
| 2016 | 3.15 | 3.12 |
| 2017 | 3.13 | 3.17 |
| 2018 | 3.42 | 3.69 |
| 2019 | 3.39 | 3.58 |
| 2020 | 3.47 | 3.69 |
| 2021 | 3.37 | 3.73 |
| 2022 | 4.06 | 4.53 |
| 2023 | 3.40 | 3.63 |
| 2024 | 3.62 | 4.43 |
| 2025 | 4.01 | 4.72 |

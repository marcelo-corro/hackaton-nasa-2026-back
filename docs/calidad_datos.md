# Reporte de calidad de los focos FIRMS
_Generado por `scripts/04_marcar_calidad.py` el 2026-11-14 17:42 UTC. No editar a mano: se regenera._

## 1. Integridad
- Focos: **821 539**, del 2000-11-01 al 2025-12-31.
- Duplicados exactos (lat, lon, fecha, hora, satélite): **0**.
- Coordenadas fuera del rango de Chile (incluye Isla de Pascua): **0**.
- Focos cuyo día local es distinto al día UTC: **0.8 %** (usar `fecha_local` en series diarias).

Valores nulos (la confianza numérica solo existe en MODIS):

|  | nulos |
|---|---|
| confianza_modis | 631 822 |
| region_id | 16 |
| asignacion | 16 |

## 2. Tipos de foco por sensor (%)
Tipo 0 = vegetación, 1 = volcán, 2 = otra fuente fija (industria, faenas), 3 = costa afuera.

| sensor | tipo 0 | tipo 1 | tipo 2 | tipo 3 |
|---|---|---|---|---|
| MODIS | 79.65 | 1.54 | 18.78 | 0.03 |
| VIIRS | 81.43 | 1.62 | 16.71 | 0.23 |

## 3. Marcas de calidad por satélite (% de focos)

| satelite | es_vegetacion | confianza_ok | frp_valido | pixel_grande | uso_base |
|---|---|---|---|---|---|
| Aqua | 87.3 | 94.7 | 100.0 | 31.4 | 83.5 |
| NOAA20 | 82.4 | 89.7 | 99.9 | 20.0 | 72.8 |
| SNPP | 80.9 | 91.6 | 99.9 | 20.7 | 73.4 |
| Terra | 67.4 | 88.8 | 100.0 | 25.7 | 61.1 |

## 4. Versiones del producto
La versión indica la colección y el tipo de procesamiento (documentación de FIRMS). Cambios de versión pueden producir saltos en la serie.

|  | focos | desde | hasta |
|---|---|---|---|
| Aqua / 6.03 | 22 508 | 2018-01-01 | 2022-12-31 |
| Aqua / 6.2 | 77 155 | 2002-07-04 | 2017-12-31 |
| Aqua / 61.03 | 16 982 | 2023-01-01 | 2025-12-31 |
| NOAA20 / 2 | 215 009 | 2018-04-01 | 2025-12-31 |
| SNPP / 2 | 416 813 | 2012-01-20 | 2025-12-31 |
| Terra / 6.03 | 15 871 | 2018-01-01 | 2022-12-31 |
| Terra / 6.2 | 44 478 | 2000-11-01 | 2017-12-31 |
| Terra / 61.03 | 12 723 | 2023-01-01 | 2025-12-31 |

## 5. Deriva de órbita: hora UTC mediana del paso diurno (focos `uso_base`)
Terra y Aqua (MODIS) se están desviando de su órbita original; Suomi NPP y NOAA-20 (VIIRS) no.

| año | Aqua | NOAA20 | SNPP | Terra |
|---|---|---|---|---|
| 2000 | — | — | — | 14.95 |
| 2001 | — | — | — | 15.12 |
| 2002 | 18.77 | — | — | 15.02 |
| 2003 | 18.75 | — | — | 14.95 |
| 2004 | 18.87 | — | — | 14.92 |
| 2005 | 18.83 | — | — | 14.93 |
| 2006 | 18.78 | — | — | 14.95 |
| 2007 | 18.80 | — | — | 14.97 |
| 2008 | 18.88 | — | — | 14.95 |
| 2009 | 18.88 | — | — | 14.95 |
| 2010 | 18.92 | — | — | 14.97 |
| 2011 | 18.82 | — | — | 14.97 |
| 2012 | 18.80 | — | 18.78 | 14.95 |
| 2013 | 18.90 | — | 18.80 | 14.97 |
| 2014 | 18.90 | — | 18.95 | 14.97 |
| 2015 | 18.82 | — | 18.88 | 14.97 |
| 2016 | 18.80 | — | 18.83 | 14.97 |
| 2017 | 18.82 | — | 18.73 | 14.98 |
| 2018 | 18.82 | 18.70 | 18.80 | 14.98 |
| 2019 | 18.90 | 18.82 | 18.72 | 14.97 |
| 2020 | 18.90 | 18.75 | 18.72 | 14.87 |
| 2021 | 18.90 | 18.82 | 18.72 | 14.90 |
| 2022 | 18.88 | 18.82 | 18.80 | 14.70 |
| 2023 | 19.05 | 18.83 | 18.83 | 14.45 |
| 2024 | 19.38 | 18.83 | 18.72 | 14.23 |
| 2025 | 19.77 | 18.83 | 18.90 | 13.97 |

## 6. Razones anuales entre satélites (focos `uso_base`)
Si la razón cambia con los años, un factor calibrado con todo el período no sirve: hay que calibrar en el período en que ambos sensores son estables (ver [armonizacion.md](armonizacion.md)).

| año | SNPP/Terra | SNPP/Aqua | SNPP/MODIS | NOAA20/SNPP |
|---|---|---|---|---|
| 2012 | 9.06 | 3.46 | 2.50 | — |
| 2013 | 12.74 | 4.08 | 3.09 | — |
| 2014 | 9.87 | 4.77 | 3.21 | — |
| 2015 | 11.58 | 4.93 | 3.46 | — |
| 2016 | 10.00 | 4.60 | 3.15 | — |
| 2017 | 8.31 | 5.02 | 3.13 | — |
| 2018 | 15.70 | 4.56 | 3.54 | 0.55 |
| 2019 | 11.99 | 4.87 | 3.46 | 0.98 |
| 2020 | 10.45 | 5.42 | 3.57 | 0.97 |
| 2021 | 11.46 | 5.02 | 3.49 | 1.01 |
| 2022 | 12.30 | 6.32 | 4.18 | 0.95 |
| 2023 | 8.42 | 5.87 | 3.46 | 0.93 |
| 2024 | 13.26 | 5.29 | 3.78 | 1.01 |
| 2025 | 17.39 | 5.50 | 4.18 | 0.97 |

Sensibilidad de la razón SNPP/MODIS al filtro de confianza:

| año | uso_base | solo vegetación (con baja confianza) |
|---|---|---|
| 2012 | 2.50 | 2.47 |
| 2013 | 3.09 | 3.01 |
| 2014 | 3.21 | 3.14 |
| 2015 | 3.46 | 3.42 |
| 2016 | 3.15 | 3.12 |
| 2017 | 3.13 | 3.17 |
| 2018 | 3.54 | 3.69 |
| 2019 | 3.46 | 3.58 |
| 2020 | 3.57 | 3.69 |
| 2021 | 3.49 | 3.73 |
| 2022 | 4.18 | 4.53 |
| 2023 | 3.46 | 3.63 |
| 2024 | 3.78 | 4.43 |
| 2025 | 4.18 | 4.72 |

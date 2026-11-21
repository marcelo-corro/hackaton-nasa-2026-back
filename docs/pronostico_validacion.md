# Riesgo con el pronóstico del tiempo real (Open-Meteo)

Generado por `scripts/08b_validar_pronostico.py` el 2026-11-21. Resultado versionado en
`ref/validacion_pronostico.json` (lo cita el paso 8).

## Por qué
El modelo de riesgo usa el clima del día (NASA POWER) y, desde la v4, el de los días que predice. NASA POWER llega con
~4 días de rezago y no tiene el futuro: al publicar se repetía el último clima disponible. Ahora Open-Meteo rellena el
rezago (su corrida más reciente) y pone el pronóstico de mañana y pasado mañana. La prueba del paso 8 usa el clima
observado de esos días (cota superior); aquí se mide con lo que de verdad hay al publicar.

## Cómo
- **Período:** 2024-01-08 a 2025-12-29 (Open-Meteo archiva sus pronósticos por plazo desde enero de 2024).
- **Comunas:** las 80 con más días con fuego en 2022-2025 (56,880 días-comuna con todos los
  datos). Las métricas no son comparables con las del paso 8 (otras comunas y años), sí entre variantes.
- **Pronóstico:** Previous Runs API de Open-Meteo, variables horarias resumidas por día como en el paso 5e; t+1 emitido
  1 día antes y t+2 emitido 2 días antes (al publicar, a las ~08 de Chile, el de t+1 es del mismo día: algo mejor).
- **Modelos:** los mismos del paso 8 (entrenados 2012-2019 con NASA POWER, calibrados 2020-2021).

## 24 h
| Variante | AUC | Precisión media | Captura top 10 % |
|---|---|---|---|
| Climatología (lo normal) | 0.699 | 0.189 | 0.292 |
| Como antes (clima de hace 4 días) | 0.717 | 0.248 | 0.351 |
| NASA POWER al día | 0.772 | 0.308 | 0.402 |
| Open-Meteo al día | 0.767 | 0.297 | 0.392 |
| Open-Meteo al día + su pronóstico | 0.782 | 0.318 | 0.396 |
| Pronóstico perfecto (cota) | 0.794 | 0.352 | 0.428 |

## 48 h
| Variante | AUC | Precisión media | Captura top 10 % |
|---|---|---|---|
| Climatología (lo normal) | 0.693 | 0.284 | 0.258 |
| Como antes (clima de hace 4 días) | 0.704 | 0.315 | 0.288 |
| NASA POWER al día | 0.745 | 0.364 | 0.326 |
| Open-Meteo al día | 0.743 | 0.358 | 0.319 |
| Open-Meteo al día + su pronóstico | 0.758 | 0.389 | 0.330 |
| Pronóstico perfecto (cota) | 0.768 | 0.412 | 0.351 |

## Conclusión
- A 24 h, la precisión media de lo que se publica pasa de **0.248** (clima de hace 4
  días) a **0.318** con el relleno y el pronóstico de Open-Meteo (la cota con el
  clima observado es 0.352).
- Open-Meteo y NASA POWER no miden igual (tabla de abajo), pero el modelo entrenado con NASA POWER funciona casi igual
  con Open-Meteo: no hizo falta corregir sesgos.
- A 7 días no se usa pronóstico: con el clima real de la semana la ventaja sobre la climatología solo sube de ×1,09 a
  ×1,14 (experimento del 21-11-2026, docs/decisiones.md).

## Open-Meteo vs NASA POWER el mismo día (comunas y días de la validación)
| Variable | Open-Meteo (media) | NASA POWER (media) | Correlación |
|---|---|---|---|
| tmax | 18.11 | 19.68 | 0.93 |
| hrmin | 48.26 | 40.91 | 0.81 |
| viento_max | 4.77 | 4.88 | 0.45 |
| precip | 3.00 | 1.24 | 0.61 |

Fuente: Weather data by Open-Meteo.com (CC BY 4.0), https://open-meteo.com. NASA POWER: ver docs/fuentes.md.

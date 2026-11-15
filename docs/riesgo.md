# Riesgo de focos por comuna a 24 h, 48 h y 7 días
_Generado por `scripts/08_riesgo.py` el 2026-11-15 00:11 UTC. No editar a mano: se regenera._

## Resumen
- **Pregunta:** ¿habrá al menos un foco VIIRS (Suomi NPP) en la comuna mañana? Unidad: comuna × día (1 753 635 filas). Tasa base en prueba: 3.6 %.
- **Bloques de variables usados:** FIRMS, clima. Modelo elegido: **Gradient boosting (FIRMS + clima)** (`hgb_firms_clima_v3`), por precisión media en el período de calibración.
- **Prueba 2022-2025 (nunca vista al entrenar):** AUC **0.846**, precisión media **0.282** (la tasa base es 0.036), el 10 % de días-comuna de mayor riesgo captura el **52 %** de los días con fuego (lift ×5.2).
- **Supera a las líneas base** (climatología AUC 0.789, persistencia 0.811). La regresión logística rinde casi igual (AUC 0.831): la ganancia viene de las variables, no de la complejidad del modelo. Se usa gradient boosting porque admite nuevos bloques (clima, vegetación) sin rediseñar.
- **Horizontes:** en precisión media, el modelo supera a la climatología de su horizonte ×1.88 a 24 h, ×1.43 a 48 h y ×1.10 a 7 días: la vista semanal es sobre todo estacional (orientativa).
- **Límite honesto:** sus alertas (nivel alto o muy alto) **sirven para priorizar, no para anticipar todo**. En comunas **con fuego reciente** acertaron el **31 %** de las veces (tasa base 16 %) y cubrieron el 79 % de los días con fuego. En comunas **sin fuego reciente** acertaron el **15 %** (6 veces la tasa base de 2.4 %), pero el **82 %** de los incendios nuevos empezó sin alerta. La mayoría de las igniciones son humanas.
- **Caso Viña del Mar:** la víspera del 3 de febrero de 2024, con el fuego todavía en comunas vecinas, el modelo subió el riesgo de Viña de 1.5 % a **2.9 %** (nivel `bajo`), pero no lo marcó como alto. Ni siquiera con el clima de ese día (calor, baja humedad y viento) anticipa el salto de un incendio a otra comuna: el clima eleva el riesgo de toda la zona, no dice hacia dónde avanza el fuego.

![Caso Viña del Mar y captura por método](figuras/riesgo_vina_2024.png)

## 1. Comparación de modelos (24 h)
Entrenamiento 2012-02 a 2019-12; calibración de probabilidades (isotónica) 2020-2021; prueba 2022-2025. La climatología es la frecuencia histórica de la comuna en ese mes; la persistencia ordena primero las comunas con fuego hoy (no es probabilidad: sin Brier).

| Modelo (prueba 2022-2025, 24 h) | AUC | Precisión media | Captura top 10 % | Lift top 10 % | Brier | Tasa base |
|---|---|---|---|---|---|---|
| Climatología (comuna × mes) | 0.789 | 0.150 | 0.403 | 4.025 | 0.033 | 0.036 |
| Persistencia + climatología | 0.811 | 0.204 | 0.444 | 4.435 | — | 0.036 |
| Regresión logística (FIRMS) | 0.831 | 0.258 | 0.495 | 4.945 | 0.030 | 0.036 |
| Gradient boosting (FIRMS) | 0.833 | 0.264 | 0.501 | 5.006 | 0.030 | 0.036 |
| Gradient boosting (FIRMS + clima) | 0.846 | 0.282 | 0.520 | 5.200 | 0.030 | 0.036 |

## 2. Ignición vs. propagación (prueba 2022-2025)

|  | AUC | Precisión media | Captura top 10 % | Tasa base |
|---|---|---|---|---|
| Gradient boosting (FIRMS + clima) / ignición | 0.803 | 0.102 | 0.410 | 0.024 |
| Gradient boosting (FIRMS + clima) / propagación | 0.805 | 0.510 | 0.359 | 0.164 |
| Climatología / ignición | 0.758 | 0.074 | 0.329 | 0.024 |
| Climatología / propagación | 0.696 | 0.319 | 0.244 | 0.164 |
| Persistencia + climatología / ignición | 0.758 | 0.074 | 0.329 | 0.024 |
| Persistencia + climatología / propagación | 0.737 | 0.365 | 0.287 | 0.164 |

Alertas del modelo elegido (nivel alto o muy alto, probabilidad ≥ 12 %):

| Segmento | Días-comuna | Alertas (alto o muy alto) | % de alertas con fuego | % del fuego que tuvo alerta | Tasa base (%) |
|---|---|---|---|---|---|
| propagación | 43 045 | 18 056 | 30.8 | 78.8 | 16.4 |
| ignición | 460 655 | 13 167 | 15.3 | 18.4 | 2.4 |

## 3. Horizontes de 48 h y 7 días
Mismas variables que a 24 h. Cada modelo se compara con la climatología de su propio horizonte (frecuencia histórica, en la comuna y el mes, de tener al menos un foco en esos días). La precisión media sube con el horizonte solo porque hay más casos positivos: lo que importa es cuánto supera a la climatología.

|  | AUC | Precisión media | Captura top 10 % | Lift top 10 % | Brier | Tasa base |
|---|---|---|---|---|---|---|
| Gradient boosting 48 h | 0.831 | 0.323 | 0.454 | 4.536 | 0.049 | 0.062 |
| Climatología 48 h | 0.786 | 0.226 | 0.375 | 3.747 | 0.054 | 0.062 |
| Gradient boosting 7 días | 0.817 | 0.490 | 0.345 | 3.446 | 0.108 | 0.163 |
| Climatología 7 días | 0.791 | 0.444 | 0.316 | 3.163 | 0.114 | 0.163 |

Ventaja sobre la climatología en precisión media: 24 h ×1.88, 48 h ×1.43, 7 días ×1.10. **A 7 días el modelo aporta poco sobre el calendario:** usa el clima observado del último día, que dice poco de la semana siguiente. La vista semanal debe rotularse como orientativa (estacional); para mejorarla haría falta un pronóstico del tiempo.

Umbrales de nivel por horizonte. A 48 h y 7 días se fijan para que, en calibración 2020-2021, cada nivel agrupe la misma proporción de días-comuna que a 24 h (con los umbrales de 24 h, a 7 días casi todo saldría "alto").

| Horizonte | muy alto desde (%) | alto desde (%) | medio desde (%) |
|---|---|---|---|
| 24 h | 30.0 | 12.0 | 4.0 |
| 48 h | 45.2 | 21.8 | 7.9 |
| 7 días | 79.1 | 52.3 | 22.8 |

## 4. Calibración (prueba 2022-2025)
Si la probabilidad está bien calibrada, lo predicho y lo observado coinciden en cada decil.

|  | predicho | observado | n |
|---|---|---|---|
| decil 1 | 0.000 | 0.000 | 50 370 |
| decil 2 | 0.001 | 0.001 | 50 370 |
| decil 3 | 0.005 | 0.004 | 50 370 |
| decil 4 | 0.008 | 0.008 | 50 370 |
| decil 5 | 0.013 | 0.013 | 50 370 |
| decil 6 | 0.021 | 0.021 | 50 370 |
| decil 7 | 0.028 | 0.028 | 50 370 |
| decil 8 | 0.040 | 0.038 | 50 370 |
| decil 9 | 0.066 | 0.060 | 50 370 |
| decil 10 | 0.215 | 0.184 | 50 370 |

## 5. Qué variables pesan
Caída de la precisión media al desordenar cada variable (muestra de la prueba).

| Variable | Caída de precisión media |
|---|---|
| frp_hoy | 0.0485 |
| dias_desde_ultimo | 0.0381 |
| precip | 0.0342 |
| clim_comuna_mes | 0.0332 |
| n_7d | 0.0240 |
| hrmin | 0.0231 |
| lat | 0.0220 |
| n_30d | 0.0176 |
| clim_comuna | 0.0169 |
| tmax | 0.0141 |
| lon | 0.0069 |
| viento_max | 0.0065 |
| precip_7d | 0.0047 |
| mes | 0.0034 |

## 6. Caso Viña del Mar, febrero de 2024

| Día | Riesgo predicho la víspera (%) | Nivel | Focos reales |
|---|---|---|---|
| 2024-01-27 | 1.0 | bajo | 0.0 |
| 2024-01-28 | 1.0 | bajo | 0.0 |
| 2024-01-29 | 1.0 | bajo | 0.0 |
| 2024-01-30 | 1.0 | bajo | 0.0 |
| 2024-01-31 | 2.6 | bajo | 0.0 |
| 2024-02-01 | 1.5 | bajo | 0.0 |
| 2024-02-02 | 1.7 | bajo | 0.0 |
| 2024-02-03 | 2.9 | bajo | 97.0 |
| 2024-02-04 | 87.6 | muy_alto | 5.0 |
| 2024-02-05 | 23.4 | alto | 0.0 |
| 2024-02-06 | 11.5 | medio | 0.0 |
| 2024-02-07 | 6.4 | medio | 0.0 |
| 2024-02-08 | 6.4 | medio | 0.0 |
| 2024-02-09 | 4.3 | medio | 0.0 |
| 2024-02-10 | 4.3 | medio | 0.0 |
| 2024-02-11 | 2.7 | bajo | 0.0 |
| 2024-02-12 | 2.4 | bajo | 0.0 |

## 7. Niveles y salidas
- Niveles por probabilidad a 24 h: `bajo` < 4 % (≈ tasa base) ≤ `medio` < 12 % ≤ `alto` < 30 % ≤ `muy_alto`. A 48 h y 7 días, los umbrales de la sección 3.
- `percentil`: posición de la probabilidad contra las del mismo comuna y mes en 2020-2025.
- `data/processed/riesgo.parquet`: riesgo desde el día siguiente al último dato (2025-12-31) a 24 h, 48 h y 7 días, con el contrato `riesgo`. Para un riesgo de verdad para mañana hacen falta los focos de 2026 (FIRMS casi en tiempo real, MAP_KEY).
- `data/processed/riesgo_backtest.parquet`: predicciones de 2020-2025 con lo que pasó, para revisar casos.
- Para sumar variables (clima, vegetación) basta crear el bloque con llave comuna × día: el script lo detecta y agrega la fila a la comparación.

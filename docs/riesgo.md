# Riesgo de focos a 24-48 h por comuna
_Generado por `scripts/08_riesgo.py` el 2026-11-14 19:57 UTC. No editar a mano: se regenera._

## Resumen
- **Pregunta:** ¿habrá al menos un foco VIIRS (Suomi NPP) en la comuna mañana? Unidad: comuna × día (1 753 635 filas). Tasa base en prueba: 3.6 %.
- **Bloques de variables usados:** FIRMS, clima. Modelo elegido: **Gradient boosting (FIRMS + clima)** (`hgb_firms_clima_v1`), por precisión media en el período de calibración.
- **Prueba 2022-2025 (nunca vista al entrenar):** AUC **0.837**, precisión media **0.271** (la tasa base es 0.036), el 10 % de días-comuna de mayor riesgo captura el **52 %** de los días con fuego (lift ×5.2).
- **Supera a las líneas base** (climatología AUC 0.789, persistencia 0.811). La regresión logística rinde casi igual (AUC 0.832): la ganancia viene de las variables, no de la complejidad del modelo. Se usa gradient boosting porque admite nuevos bloques (clima, vegetación) sin rediseñar.
- **Límite honesto:** sus alertas (nivel alto o muy alto) **sirven para priorizar, no para anticipar todo**. En comunas **con fuego reciente** acertaron el **32 %** de las veces (tasa base 16 %) y cubrieron el 75 % de los días con fuego. En comunas **sin fuego reciente** acertaron el **15 %** (6 veces la tasa base de 2.4 %), pero el **80 %** de los incendios nuevos empezó sin alerta. La mayoría de las igniciones son humanas.
- **Caso Viña del Mar:** la víspera del 3 de febrero de 2024, con el fuego todavía en comunas vecinas, el modelo subió el riesgo de Viña de 2.7 % a **5.4 %** (nivel `medio`), pero no lo marcó como alto. Ni siquiera con el clima de ese día (calor, baja humedad y viento) anticipa el salto de un incendio a otra comuna: el clima eleva el riesgo de toda la zona, no dice hacia dónde avanza el fuego.

![Caso Viña del Mar y captura por método](figuras/riesgo_vina_2024.png)

## 1. Comparación de modelos (24 h)
Entrenamiento 2012-02 a 2019-12; calibración de probabilidades (isotónica) 2020-2021; prueba 2022-2025. La climatología es la frecuencia histórica de la comuna en ese mes; la persistencia ordena primero las comunas con fuego hoy (no es probabilidad: sin Brier).

| Modelo (prueba 2022-2025, 24 h) | AUC | Precisión media | Captura top 10 % | Lift top 10 % | Brier | Tasa base |
|---|---|---|---|---|---|---|
| Climatología (comuna × mes) | 0.789 | 0.150 | 0.403 | 4.025 | 0.033 | 0.036 |
| Persistencia + climatología | 0.811 | 0.204 | 0.444 | 4.435 | — | 0.036 |
| Regresión logística (FIRMS) | 0.832 | 0.254 | 0.496 | 4.962 | 0.030 | 0.036 |
| Gradient boosting (FIRMS) | 0.827 | 0.253 | 0.503 | 5.035 | 0.030 | 0.036 |
| Gradient boosting (FIRMS + clima) | 0.837 | 0.271 | 0.516 | 5.157 | 0.030 | 0.036 |

## 2. Ignición vs. propagación (prueba 2022-2025)

|  | AUC | Precisión media | Captura top 10 % | Tasa base |
|---|---|---|---|---|
| Gradient boosting (FIRMS + clima) / ignición | 0.796 | 0.105 | 0.409 | 0.024 |
| Gradient boosting (FIRMS + clima) / propagación | 0.790 | 0.488 | 0.347 | 0.164 |
| Climatología / ignición | 0.758 | 0.074 | 0.329 | 0.024 |
| Climatología / propagación | 0.696 | 0.319 | 0.244 | 0.164 |
| Persistencia + climatología / ignición | 0.758 | 0.074 | 0.329 | 0.024 |
| Persistencia + climatología / propagación | 0.737 | 0.365 | 0.287 | 0.164 |

Alertas del modelo elegido (nivel alto o muy alto, probabilidad ≥ 12 %):

| Segmento | Días-comuna | Alertas (alto o muy alto) | % de alertas con fuego | % del fuego que tuvo alerta | Tasa base (%) |
|---|---|---|---|---|---|
| propagación | 43 045 | 16 636 | 31.7 | 74.7 | 16.4 |
| ignición | 460 655 | 14 422 | 15.3 | 20.3 | 2.4 |

## 3. Horizonte de 48 h

|  | AUC | Precisión media | Captura top 10 % | Lift top 10 % | Brier | Tasa base |
|---|---|---|---|---|---|---|
| Gradient boosting 48 h | 0.821 | 0.317 | 0.450 | 4.499 | 0.050 | 0.062 |
| Climatología 48 h | 0.784 | 0.225 | 0.372 | 3.723 | 0.054 | 0.062 |

## 4. Calibración (prueba 2022-2025)
Si la probabilidad está bien calibrada, lo predicho y lo observado coinciden en cada decil.

|  | predicho | observado | n |
|---|---|---|---|
| decil 1 | 0.001 | 0.003 | 50 370 |
| decil 2 | 0.002 | 0.002 | 50 370 |
| decil 3 | 0.006 | 0.005 | 50 370 |
| decil 4 | 0.009 | 0.009 | 50 370 |
| decil 5 | 0.013 | 0.015 | 50 370 |
| decil 6 | 0.020 | 0.018 | 50 370 |
| decil 7 | 0.028 | 0.027 | 50 370 |
| decil 8 | 0.039 | 0.038 | 50 370 |
| decil 9 | 0.065 | 0.058 | 50 370 |
| decil 10 | 0.209 | 0.182 | 50 370 |

## 5. Qué variables pesan
Caída de la precisión media al desordenar cada variable (muestra de la prueba).

| Variable | Caída de precisión media |
|---|---|
| clim_comuna_mes | 0.1434 |
| frp_hoy | 0.0300 |
| precip | 0.0264 |
| lat | 0.0149 |
| dias_desde_ultimo | 0.0147 |
| n_7d | 0.0125 |
| hrmin | 0.0114 |
| n_hoy | 0.0089 |
| tmax | 0.0068 |
| doy_cos | 0.0051 |
| vecinos_hoy | 0.0048 |
| viento_max | 0.0042 |
| lon | 0.0041 |
| n_30d | 0.0035 |
| dias_sin_lluvia | 0.0027 |
| n_3d | 0.0026 |
| area_km2 | 0.0022 |
| dia_semana | 0.0017 |
| precip_7d | 0.0011 |
| mes | -0.0000 |
| clim_comuna | -0.0002 |
| vecinos_3d | -0.0017 |
| doy_sin | -0.0018 |

## 6. Caso Viña del Mar, febrero de 2024

| Día | Riesgo predicho la víspera (%) | Nivel | Focos reales |
|---|---|---|---|
| 2024-01-27 | 1.1 | bajo | 0.0 |
| 2024-01-28 | 1.1 | bajo | 0.0 |
| 2024-01-29 | 1.0 | bajo | 0.0 |
| 2024-01-30 | 1.9 | bajo | 0.0 |
| 2024-01-31 | 3.6 | bajo | 0.0 |
| 2024-02-01 | 2.7 | bajo | 0.0 |
| 2024-02-02 | 2.2 | bajo | 0.0 |
| 2024-02-03 | 5.4 | medio | 97.0 |
| 2024-02-04 | 95.0 | muy_alto | 5.0 |
| 2024-02-05 | 22.1 | alto | 0.0 |
| 2024-02-06 | 4.2 | medio | 0.0 |
| 2024-02-07 | 1.9 | bajo | 0.0 |
| 2024-02-08 | 2.3 | bajo | 0.0 |
| 2024-02-09 | 1.9 | bajo | 0.0 |
| 2024-02-10 | 2.3 | bajo | 0.0 |
| 2024-02-11 | 1.7 | bajo | 0.0 |
| 2024-02-12 | 1.9 | bajo | 0.0 |

## 7. Niveles y salidas
- Niveles por probabilidad: `bajo` < 4 % (≈ tasa base) ≤ `medio` < 12 % ≤ `alto` < 30 % ≤ `muy_alto`.
- `percentil`: posición de la probabilidad contra las del mismo comuna y mes en 2020-2025.
- `data/processed/riesgo.parquet`: riesgo para el día siguiente al último dato (2025-12-31), con el contrato `riesgo`. Para un riesgo de verdad para mañana hacen falta los focos de 2026 (FIRMS casi en tiempo real, MAP_KEY).
- `data/processed/riesgo_backtest.parquet`: predicciones de 2020-2025 con lo que pasó, para revisar casos.
- Para sumar variables (clima, vegetación) basta crear el bloque con llave comuna × día: el script lo detecta y agrega la fila a la comparación.

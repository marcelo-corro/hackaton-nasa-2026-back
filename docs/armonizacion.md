# Armonización MODIS ↔ VIIRS
_Generado por `scripts/05_armonizar.py` el 2026-11-14 17:42 UTC. No editar a mano: se regenera._

## Resumen
- **Serie:** 345 comunas × 302 meses (2000-11 a 2025-12), en **focos equivalentes MODIS**: lo que habrían contado Terra + Aqua con su órbita nominal y su procesamiento previo a 2018.
- **Método elegido:** Factor único. Razón VIIRS/MODIS = **3.18** (calibrada 2012-03 a 2017-12).
- **Validación fuera de muestra (2016-2017):** sesgo -2.9 %, error región-mes 16.6 %, error nacional-mes 7.8 %, correlación nacional 0.999, cobertura del intervalo del 90 % 92 %.
- **Hallazgo:** los métodos más complejos (por región, por mes, modelos de conteo) no mejoran fuera de muestra: las diferencias por región y temporada que se ven al calibrar no se repiten de un año a otro. Lo decisivo es calibrar en el período en que MODIS todavía es estable.

| Período | Serie armonizada | Por qué |
|---|---|---|
| 2000-11 a 2002-06 | Terra convertido a Terra + Aqua (Factor por mes) | Aqua todavía no existía |
| 2002-07 a 2017-12 | MODIS observado (Terra + Aqua) | Referencia estable |
| 2018-01 en adelante | VIIRS Suomi NPP convertido a escala MODIS | MODIS cambia de procesamiento en 2018 y su órbita se desvía; VIIRS es estable |

![Focos por año: crudos vs. armonizados](figuras/armonizacion_chile.png)

## 1. VIIRS → MODIS: comparación de métodos
Calibración 2012-03 a 2015-12, prueba 2016-01 a 2017-12 (incluye los megaincendios de 2017). Errores relativos ponderados (suma de errores absolutos / suma observada). Regla de elección: menor error región-mes; con diferencias menores a 0.5 puntos, el método más simple.

| Método | Sesgo total | Error comuna-mes | Error región-mes | Error nacional-mes | Correlación nacional | Cobertura 90 % |
|---|---|---|---|---|---|---|
| Factor único | -0.029 | 0.360 | 0.166 | 0.078 | 0.999 | 0.920 |
| Factor por temporada | -0.048 | 0.369 | 0.177 | 0.074 | 0.999 | 0.922 |
| Factor por mes | -0.048 | 0.377 | 0.191 | 0.093 | 0.999 | 0.921 |
| Factor por zona | -0.018 | 0.369 | 0.195 | 0.091 | 0.999 | 0.919 |
| Factor por región | -0.049 | 0.377 | 0.199 | 0.081 | 0.999 | 0.921 |
| Proporcional Poisson (C(zona) + C(temporada)) | -0.061 | 0.400 | 0.199 | 0.087 | 0.999 | 0.943 |
| Proporcional Poisson (C(cod_region) + C(mes)) | -0.075 | 0.416 | 0.217 | 0.099 | 1.000 | 0.943 |
| Binomial negativa con pendiente (región + mes) | 0.644 | 0.998 | 0.812 | 0.681 | 0.995 | 0.961 |

## 2. Terra → Terra + Aqua (meses antes de Aqua)
Calibración 2003-2008, prueba 2009-2011.

| Método | Sesgo total | Error comuna-mes | Error región-mes | Error nacional-mes | Correlación nacional | Cobertura 90 % |
|---|---|---|---|---|---|---|
| Factor único | -0.019 | 0.822 | 0.462 | 0.327 | 0.835 | 0.868 |
| Factor por temporada | -0.038 | 0.794 | 0.413 | 0.253 | 0.884 | 0.868 |
| Factor por mes | -0.065 | 0.767 | 0.389 | 0.199 | 0.931 | 0.867 |
| Factor por zona | -0.019 | 0.818 | 0.455 | 0.329 | 0.832 | 0.867 |
| Factor por región | -0.022 | 0.813 | 0.436 | 0.315 | 0.849 | 0.867 |
| Proporcional Poisson (C(zona) + C(temporada)) | -0.061 | 0.887 | 0.502 | 0.270 | 0.880 | 0.947 |
| Proporcional Poisson (C(cod_region) + C(mes)) | -0.088 | 0.860 | 0.434 | 0.222 | 0.933 | 0.948 |
| Binomial negativa con pendiente (región + mes) | 0.998 | 1.743 | 1.261 | 1.083 | 0.861 | 0.958 |

## 3. Deriva de MODIS: cuánto cuenta respecto de lo esperado según VIIRS (%)
Negativo = MODIS detecta menos de lo que debería. Cerca de 0 en 2012-2017 (período de calibración); desde 2018 refleja el cambio de procesamiento y la deriva de órbita (ver [calidad_datos.md](calidad_datos.md)).

| año | MODIS (Terra + Aqua) | Terra | Aqua |
|---|---|---|---|
| 2012 | 6.9 | -27.3 | 22.7 |
| 2013 | 3.1 | -21.0 | 14.3 |
| 2014 | -1.0 | 1.9 | -2.3 |
| 2015 | -7.9 | -13.1 | -5.5 |
| 2016 | 1.0 | 0.6 | 1.2 |
| 2017 | 1.8 | 21.1 | -7.2 |
| 2018 | -9.9 | -35.9 | 2.1 |
| 2019 | -8.0 | -16.1 | -4.3 |
| 2020 | -10.8 | -3.8 | -14.1 |
| 2021 | -8.8 | -12.2 | -7.2 |
| 2022 | -23.8 | -18.2 | -26.3 |
| 2023 | -7.9 | 19.5 | -20.6 |
| 2024 | -15.8 | -24.1 | -11.9 |
| 2025 | -23.8 | -42.2 | -15.3 |

## 4. Continuidad de VIIRS: NOAA-20 frente a Suomi NPP
Factor NOAA-20 / Suomi NPP calibrado 2019-01 a 2025-12: **0.964**. Guardado en `data/processed/calibracion.json` para cuando Suomi NPP deje de entregar datos. No se usa en la serie actual (Suomi NPP cubre hasta 2025) y nunca se suman ambos satélites.

| año | NOAA-20 / Suomi NPP |
|---|---|
| 2018 | 0.929 |
| 2019 | 0.984 |
| 2020 | 0.969 |
| 2021 | 1.008 |
| 2022 | 0.947 |
| 2023 | 0.930 |
| 2024 | 1.008 |
| 2025 | 0.970 |

## 5. Límites
- La conversión supone que la relación VIIRS/MODIS de 2012-2017 se mantiene. VIIRS es estable en ese período y después; la validación cubre dos años, uno de ellos extremo (2017).
- Los meses de 2000-11 a 2002-06 (solo Terra) son los menos precisos: error nacional-mes 20 % en la prueba, contra 7.8 % de la conversión desde VIIRS. Sus intervalos son más anchos.
- A escala de una comuna y un mes el error es alto (ver la tabla); para decidir conviene mirar agregados (región, temporada, año) y el intervalo `armonizado_p05`-`armonizado_p95`.
- Desde 2018 la serie es un valor esperado (más suave) y antes es un conteo observado: los percentiles que mezclan ambos períodos deben leerse con cuidado.
- Se cuentan **detecciones** de vegetación con confianza nominal o alta (`uso_base`), no incendios ni superficie quemada.

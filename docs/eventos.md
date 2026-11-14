# Focos vs. incendios: ¿por qué VIIRS ve más que MODIS?
_Generado por `scripts/06_eventos.py` el 2026-11-14 18:08 UTC. No editar a mano: se regenera._

## Resumen
- **Hipótesis:** VIIRS (375 m) parte un mismo incendio en más píxeles que MODIS (1 km); contando incendios en vez de focos, la diferencia debería acercarse a 1.
- **Resultado: se cumple solo en parte.** En 2013-2017 la razón Suomi NPP / MODIS baja de **3.2** (focos) a **2.3** (incendios), y con cualquier definición razonable de incendio queda entre 1.8 y 2.3, nunca cerca de 1.
- **La mayor parte de la diferencia es sensibilidad:** 55 % de los incendios que ve VIIRS son de un solo foco, y MODIS ve solo el **11 %** de ellos; de los incendios de más de 50 focos ve el **100 %**.
- **La deriva de MODIS también se ve en incendios grandes:** en 2012-2020 MODIS veía en promedio el **92 %** de los incendios grandes que veía VIIRS; en 2024-2025, el **78 %**.
- **Consecuencia para el producto:** agrupar en incendios no armoniza los sensores; por eso la serie usa calibración ([armonizacion.md](armonizacion.md)). La serie en equivalente MODIS sub-representa los incendios chicos, que solo VIIRS ve bien.

![Coincidencia entre sensores](figuras/eventos_deteccion.png)

## 1. Razón entre sensores contando focos y contando incendios
Incendio (evento) = focos del mismo sensor a ≤2 km y ≤2 días, encadenados. MODIS = Terra + Aqua juntos. 2012 sin enero para VIIRS.

| año | Focos SNPP/MODIS | Eventos SNPP/MODIS | Focos por evento MODIS | Focos por evento SNPP |
|---|---|---|---|---|
| 2012 | 2.50 | 2.24 | 2.23 | 2.50 |
| 2013 | 3.09 | 2.52 | 1.95 | 2.38 |
| 2014 | 3.21 | 2.37 | 2.50 | 3.38 |
| 2015 | 3.46 | 2.27 | 2.75 | 4.19 |
| 2016 | 3.15 | 2.28 | 2.20 | 3.04 |
| 2017 | 3.13 | 1.94 | 5.64 | 9.09 |
| 2018 | 3.54 | 2.62 | 2.13 | 2.87 |
| 2019 | 3.46 | 2.75 | 2.76 | 3.47 |
| 2020 | 3.57 | 2.66 | 2.71 | 3.64 |
| 2021 | 3.49 | 2.74 | 2.38 | 3.04 |
| 2022 | 4.18 | 3.14 | 3.06 | 4.07 |
| 2023 | 3.46 | 2.61 | 6.71 | 8.89 |
| 2024 | 3.78 | 2.73 | 2.32 | 3.21 |
| 2025 | 4.18 | 2.89 | 2.73 | 3.95 |

## 2. Sensibilidad de la razón de incendios (2013-2017)

| Distancia (km) | 1 día(s) | 2 día(s) | 4 día(s) |
|---|---|---|---|
| 1 | 1.77 | 1.80 | 1.81 |
| 2 | 2.23 | 2.28 | 2.28 |
| 4 | 2.17 | 2.21 | 2.20 |
| 8 | 2.01 | 2.04 | 1.99 |

## 3. ¿Qué incendios vistos por VIIRS ve también MODIS? (2013-2017)
Coincidencia: algún foco MODIS a ≤2 km y ≤1 día de algún foco del incendio.

| Tamaño (focos VIIRS) | Incendios | % del total | MODIS también lo ve (%) | FRP total mediana (MW) |
|---|---|---|---|---|
| 1 foco | 15 812.0 | 54.7 | 10.7 | 3.2 |
| 2-3 | 8 292.0 | 28.7 | 27.5 | 11.3 |
| 4-10 | 3 708.0 | 12.8 | 58.9 | 45.9 |
| 11-50 | 936.0 | 3.2 | 91.8 | 238.6 |
| más de 50 | 158.0 | 0.5 | 100.0 | 1 973.2 |

Por año:

| año | Todos | Incendios grandes (más de 10 focos) |
|---|---|---|
| 2012 | 24.6 | 91.2 |
| 2013 | 22.8 | 91.7 |
| 2014 | 22.8 | 94.1 |
| 2015 | 27.7 | 95.5 |
| 2016 | 23.7 | 92.1 |
| 2017 | 27.2 | 90.0 |
| 2018 | 25.6 | 92.3 |
| 2019 | 23.7 | 93.4 |
| 2020 | 23.8 | 92.0 |
| 2021 | 22.9 | 86.5 |
| 2022 | 19.2 | 86.0 |
| 2023 | 24.7 | 89.0 |
| 2024 | 19.4 | 76.2 |
| 2025 | 19.8 | 79.8 |

Al revés, VIIRS ve el **58 %** de los incendios que ve MODIS (2013-2017): cada sensor ve incendios que el otro no, en parte porque pasan a horas distintas (Terra en la mañana; Aqua y Suomi NPP después del mediodía). NOAA-20 ve el **44 %** de los incendios de Suomi NPP (2019-2025), coherente con que ambos VIIRS ven casi lo mismo.

## 4. Caso Viña del Mar, febrero de 2024 (comuna 05109)

| Sensor | Incendios que tocan Viña | Focos dentro de Viña | Focos del mayor incendio (todas las comunas) | Comunas que abarca el mayor |
|---|---|---|---|---|
| MODIS | 3 | 16 | 64 | 3 |
| SNPP | 2 | 102 | 354 | 3 |
| NOAA20 | 1 | 126 | 426 | 3 |

## 5. Límites
- La definición de incendio es una aproximación (vecindario cuadrado y encadenamiento); dos incendios vecinos y simultáneos se cuentan como uno.
- La coincidencia depende de la geolocalización: los píxeles MODIS del borde del barrido miden hasta ~3 km, así que a 2 km algunas coincidencias reales quedan fuera.
- Se usan focos de vegetación con confianza nominal o alta (`uso_base`).

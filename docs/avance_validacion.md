# Validación de la dirección de avance (cono)
_Generado por `scripts/14_validar_avance.py` el 2026-11-15 06:09 UTC. No editar a mano._

6.674 avances día a día de incendios en Chile (frente nuevo del día siguiente a más de 0.75 km). Al azar. el 25 % cae a ±45° y el 50 % a ±90°; error mediano al azar: 90°.

|  | n | % a ±45° | IC95 inferior | % a ±90° | error mediano (°) |
|---|---|---|---|---|---|
| Calibración 2012-2021 / Viento a favor (día d), todos | 4 421.0 | 29.3 | 28.0 | 53.2 | 84.1 |
| Calibración 2012-2021 / Cota: viento del día d+1, todos | 4 421.0 | 28.2 | 26.9 | 53.2 | 83.1 |
| Calibración 2012-2021 / Viento a favor, ya avanzaba | 1 009.0 | 29.1 | 26.3 | 52.9 | 85.7 |
| Calibración 2012-2021 / Persistencia, ya avanzaba | 1 009.0 | 25.4 | 22.7 | 41.9 | 109.4 |
| Calibración 2012-2021 / Combinada, ya avanzaba | 1 009.0 | 23.2 | 20.6 | 45.5 | 98.3 |
| Prueba 2022-2026 / Viento a favor (día d), todos | 2 253.0 | 30.8 | 28.9 | 55.3 | 80.3 |
| Prueba 2022-2026 / Cota: viento del día d+1, todos | 2 253.0 | 29.6 | 27.8 | 55.7 | 79.7 |
| Prueba 2022-2026 / Viento a favor, ya avanzaba | 700.0 | 30.7 | 27.3 | 57.4 | 75.9 |
| Prueba 2022-2026 / Persistencia, ya avanzaba | 700.0 | 23.0 | 19.9 | 42.4 | 106.0 |
| Prueba 2022-2026 / Combinada, ya avanzaba | 700.0 | 24.6 | 21.4 | 49.9 | 90.3 |

Regla elegida en calibración: **viento a favor**. Calibración: 29.3 % a ±45° → **pasa** el criterio. Prueba 2022-2026: 30.8 % a ±45° (error mediano 80°).

Por velocidad del viento (terciles de calibración):

|  | n | % a ±45° | IC95 inferior | % a ±90° | error mediano (°) | avance mediano (km/día) | avance p75 (km/día) |
|---|---|---|---|---|---|---|---|
| Calibración / fuerte | 1 479.0 | 33.9 | 31.5 | 56.9 | 75.1 | 1.7 | 2.7 |
| Calibración / medio | 1 478.0 | 27.8 | 25.5 | 52.2 | 85.2 | 1.7 | 2.5 |
| Calibración / suave | 1 464.0 | 26.1 | 23.8 | 50.5 | 89.3 | 1.7 | 2.4 |
| Prueba / fuerte | 842.0 | 35.7 | 32.5 | 59.5 | 73.3 | 1.9 | 3.0 |
| Prueba / medio | 757.0 | 30.5 | 27.2 | 55.6 | 79.6 | 1.9 | 2.8 |
| Prueba / suave | 654.0 | 24.8 | 21.5 | 49.4 | 91.2 | 1.8 | 2.7 |

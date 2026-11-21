# Simulación de la lista de alertas (piloto Región de Valparaíso)
_Generado por `scripts/12d_validar_alertas.py` el 2026-11-21 16:37 UTC. No editar a mano._

Cada día t se arma la lista con lo conocido hasta t (riesgo a 24 h del modelo. historial y focos de t-2 a t) y se mide contra los focos de t+1. 17.952 sectores en total (sin fuentes persistentes). v0.4: 25 sectores siempre. orden fijo. v0.5: fuego activo primero (cercanía). alerta (alto o muy alto) y vigilancia (medio); sin nivel bajo.

|  | Calibración 2020-2021 | Prueba 2022-2025 | Prueba nueva 2026 (hasta 2026-10-31) |
|---|---|---|---|
| Días | 730.0 | 1 460.0 | 303.0 |
| Sector-días con fuego al día siguiente | 592.0 | 1 377.0 | 139.0 |
| v0.4: % del fuego en los sectores listados | 3.9 | 5.2 | 12.9 |
| v0.4: sectores listados por día | 25.0 | 25.0 | 25.0 |
| v0.4: % de los sectores listados que tuvo fuego | 0.1 | 0.2 | 0.2 |
| v0.5: % del fuego en sectores de alerta (fuego activo + alerta) | 14.0 | 4.9 | 6.5 |
| v0.5: % del fuego en todos los sectores listados | 14.4 | 6.2 | 6.5 |
| v0.5: sectores listados por día | 7.5 | 9.0 | 6.3 |
| v0.5: % de los sectores listados que tuvo fuego | 1.6 | 0.7 | 0.5 |
| v0.5: % de los sectores de fuego activo que tuvo fuego | 2.0 | 0.7 | 0.6 |
| v0.5: % de los sectores de alerta (modelo) que tuvo fuego | — | 0.0 | 0.0 |
| v0.5: % de los sectores de vigilancia que tuvo fuego | 0.2 | 0.6 | 0.0 |
| v0.5: días con lista vacía (%) | 26.8 | 29.5 | 42.6 |
| Comuna-días con fuego al día siguiente | 316.0 | 695.0 | 101.0 |
| v0.5: % de esas comunas en fuego activo o alerta | 21.2 | 14.5 | 13.9 |
| v0.5: % en fuego activo, alerta o vigilancia | 25.0 | 22.4 | 18.8 |
| v0.4: % de esas comunas en la lista | 38.6 | 34.5 | 42.6 |

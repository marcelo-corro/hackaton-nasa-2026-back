# Simulación de la lista de alertas (piloto Región de Valparaíso)
_Generado por `scripts/12d_validar_alertas.py` el 2026-11-15 04:35 UTC. No editar a mano._

Cada día t se arma la lista con lo conocido hasta t (riesgo a 24 h del modelo. historial y focos de t-2 a t) y se mide contra los focos de t+1. 17.936 sectores en total (sin fuentes persistentes). v0.4: 25 sectores siempre. orden fijo. v0.5: fuego activo primero (cercanía). alerta (alto o muy alto) y vigilancia (medio); sin nivel bajo.

|  | Calibración 2020-2021 | Prueba 2022-2025 |
|---|---|---|
| Días | 730.0 | 1 460.0 |
| Sector-días con fuego al día siguiente | 601.0 | 1 388.0 |
| v0.4: % del fuego en los sectores listados | 3.7 | 4.7 |
| v0.4: sectores listados por día | 25.0 | 25.0 |
| v0.4: % de los sectores listados que tuvo fuego | 0.1 | 0.2 |
| v0.5: % del fuego en sectores de alerta (fuego activo + alerta) | 13.8 | 4.8 |
| v0.5: % del fuego en todos los sectores listados | 14.3 | 6.9 |
| v0.5: sectores listados por día | 9.9 | 12.0 |
| v0.5: % de los sectores listados que tuvo fuego | 1.2 | 0.5 |
| v0.5: % de los sectores de fuego activo que tuvo fuego | 1.9 | 0.7 |
| v0.5: % de los sectores de alerta (modelo) que tuvo fuego | 0.0 | 0.0 |
| v0.5: % de los sectores de vigilancia que tuvo fuego | 0.1 | 0.4 |
| v0.5: días con lista vacía (%) | 18.9 | 21.0 |
| Comuna-días con fuego al día siguiente | 324.0 | 704.0 |
| v0.5: % de esas comunas en fuego activo o alerta | 20.7 | 14.6 |
| v0.5: % en fuego activo, alerta o vigilancia | 27.8 | 27.7 |
| v0.4: % de esas comunas en la lista | 35.5 | 30.5 |

# Validación de la prioridad por sector (piloto Región de Valparaíso)
_Generado por `scripts/12b_validar_sectores.py` el 2026-11-15 00:15 UTC. No editar a mano._

¿Qué % de los días-sector con fuego cae en el 10 % de sectores de su comuna con mayor puntaje? El azar da 10 %. Historial contado solo antes de cada período (sin fuga); capas fijas: vegetación, interfaz, pendiente. Rasgos: umbrales fijados antes de esta prueba; historial = fuego en ≥ 2 días o algún incendio grande. Fuentes persistentes (probable industria) excluidas.

| Período | Días-sector con fuego | Azar | Historial previo | Interfaz | Exposición (n.º de factores) | Historial, luego interfaz |
|---|---|---|---|---|---|---|
| calibración 2020-2021 | 602 | 10.0 | 24.4 | 17.1 | 12.3 | 26.4 |
| prueba 2022-2025 | 1 388 | 10.0 | 26.8 | 18.9 | 17.2 | 29.3 |

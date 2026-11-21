"""Riesgo de focos por comuna a 24 h, 48 h y 7 días (paso 8, `scripts/08_riesgo.py`). Resultados en docs/riesgo.md.

Módulos:
- `variables`: tabla comuna × día, objetivos (y24, y48, y7d), bloques de variables (FIRMS, climatología, clima) y
  las 14 variables que usa el modelo (`VARIABLES_MODELO_FIRMS`, `VARIABLES_MODELO_CLIMA`; v3).
- `evaluar`: AUC, precisión media, captura del 10 % de mayor riesgo, calibración y curva de captura.

Decisiones (14-11-2026):
- Objetivo: al menos un foco VIIRS Suomi NPP (`uso_base`) en la comuna al día siguiente (el sensor estable).
- Partición temporal: entrena 2012-02..2019, calibra (isotónica, tope 95 %) 2020-2021, prueba 2022-2025.
- La climatología (comuna × mes) se calcula solo con años de entrenamiento (sin fuga del período de prueba) y, en
  cada año de entrenamiento, con los otros años: incluir el propio año filtraba la respuesta y el modelo confiaba
  de más en esa variable (corregido en v2: AUC de prueba 0,837 -> 0,850).
- v3 (noche del 14-11): 14 de las 23 variables (selección en calibración, ver docs/decisiones.md) y modelos de 48 h
  y 7 días con umbrales de nivel propios. Prueba 24 h: AUC 0,846, precisión media 0,282.
- v4 (21-11-2026): v3 + clima de los días que se predicen (t+1 a 24 h; t+1 y t+2 a 48 h). Al entrenar y probar, el
  observado (NASA POWER); al publicar, el pronóstico de Open-Meteo (paso 5e), que además rellena el rezago de POWER.
  Validado con pronósticos reales en scripts/08b_validar_pronostico.py (docs/pronostico_validacion.md).
- Se evalúa por separado propagación (comuna con focos en los últimos 3 días) e ignición (sin focos recientes).
- Para sumar fuentes, se crea un bloque con llave (region_id, fecha) y el script lo agrega a la comparación.
"""

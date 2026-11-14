"""Riesgo de focos a 24-48 h por comuna (paso 8, `scripts/08_riesgo.py`). Resultados en docs/riesgo.md.

Módulos:
- `variables`: tabla comuna × día, objetivos (y24, y48) y bloques de variables (FIRMS, climatología, clima).
- `evaluar`: AUC, precisión media, captura del 10 % de mayor riesgo, calibración y curva de captura.

Decisiones (14-11-2026):
- Objetivo: al menos un foco VIIRS Suomi NPP (`uso_base`) en la comuna al día siguiente (el sensor estable).
- Partición temporal: entrena 2012-02..2019, calibra (isotónica, tope 95 %) 2020-2021, prueba 2022-2025.
- La climatología (comuna × mes) se calcula solo con años de entrenamiento: sin fuga del período de prueba.
- Se evalúa por separado propagación (comuna con focos en los últimos 3 días) e ignición (sin focos recientes).
- Para sumar fuentes, se crea un bloque con llave (region_id, fecha) y el script lo agrega a la comparación.
"""
